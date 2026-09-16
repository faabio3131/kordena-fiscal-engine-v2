"""Governed HOMOLOGATION-only controlled-pilot gate for V2-15 B5.

The module composes existing durable commercial configuration, S2S authorization
and homologation-readiness boundaries. It never performs an external fiscal call,
never promotes production readiness and stores no secret material.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from kordena_fiscal.control_plane import (
    AdminPrincipal,
    CommercialConfigurationService,
    ControlPlaneAuditAction,
    ControlPlaneAuditEvent,
    ControlPlanePermission,
    UnitModuleBinding,
)
from kordena_fiscal.control_plane.service import ControlPlaneAuthorizationError
from kordena_fiscal.domain import (
    BrazilianJurisdiction,
    ExecutionScope,
    FiscalDocumentKind,
    FiscalEnvironment,
    FiscalValidationError,
)
from kordena_fiscal.gateway import ProviderOperation
from kordena_fiscal.persistence.ports import FiscalUnitOfWorkFactory
from kordena_fiscal.security import AuthorizedFiscalRequest, FiscalCapability

from .homologation_readiness import DurableHomologationEnvironmentReadinessService


class PilotDecisionStatus(StrEnum):
    GO_INTERNAL = "go_internal"
    NO_GO = "no_go"
    BLOCKED_EXTERNAL = "blocked_external"


_OPERATION_CAPABILITY: dict[ProviderOperation, FiscalCapability] = {
    ProviderOperation.AUTHORIZE: FiscalCapability.ISSUE,
    ProviderOperation.QUERY: FiscalCapability.QUERY,
    ProviderOperation.STATUS: FiscalCapability.QUERY,
    ProviderOperation.CANCEL: FiscalCapability.CANCEL,
    ProviderOperation.INUTILIZE: FiscalCapability.INUTILIZE,
}


def _token(value: str, field_name: str) -> str:
    normalized = value.strip().lower()
    allowed = set("abcdefghijklmnopqrstuvwxyz0123456789._-")
    if not normalized or len(normalized) > 96 or any(char not in allowed for char in normalized):
        raise FiscalValidationError(f"{field_name} must be a safe non-blank token <= 96 chars")
    return normalized


@dataclass(frozen=True, slots=True)
class ControlledPilotScope:
    """Explicit allowlist for one controlled pilot partition."""

    pilot_id: str
    scope: ExecutionScope
    document_kind: FiscalDocumentKind
    jurisdiction: BrazilianJurisdiction
    provider_id: str
    allowed_operations: frozenset[ProviderOperation]

    def __post_init__(self) -> None:
        object.__setattr__(self, "pilot_id", _token(self.pilot_id, "pilot_id"))
        if not isinstance(self.scope, ExecutionScope) or self.scope.host_namespace is None:
            raise FiscalValidationError("pilot requires bound ExecutionScope")
        if self.scope.environment is not FiscalEnvironment.HOMOLOGATION:
            raise FiscalValidationError("controlled pilot requires HOMOLOGATION scope")
        if not isinstance(self.document_kind, FiscalDocumentKind):
            raise FiscalValidationError("document_kind must be FiscalDocumentKind")
        if not isinstance(self.jurisdiction, BrazilianJurisdiction):
            raise FiscalValidationError("jurisdiction must be BrazilianJurisdiction")
        if self.document_kind is FiscalDocumentKind.NFSE:
            if self.jurisdiction.municipality_ibge_code is None:
                raise FiscalValidationError("NFSe controlled pilot requires municipality IBGE code")
        object.__setattr__(self, "provider_id", _token(self.provider_id, "provider_id"))
        if not isinstance(self.allowed_operations, frozenset) or not self.allowed_operations:
            raise FiscalValidationError("allowed_operations must be a non-empty frozenset")
        if not all(isinstance(item, ProviderOperation) for item in self.allowed_operations):
            raise FiscalValidationError("allowed_operations contain invalid values")

    @property
    def module_id(self) -> str:
        return f"pilot.{self.pilot_id}"


@dataclass(frozen=True, slots=True)
class PilotDecision:
    pilot_id: str
    operation: ProviderOperation
    status: PilotDecisionStatus
    reasons: tuple[str, ...]
    provider_id: str | None
    internal_ready: bool
    official_evidence_present: bool


@dataclass(frozen=True, slots=True)
class PilotScopeReadiness:
    """Read-only readiness of every operation explicitly included in one pilot."""

    pilot_id: str
    internal_reasons: tuple[str, ...]
    external_reasons: tuple[str, ...]

    @property
    def internal_ready(self) -> bool:
        return not self.internal_reasons

    @property
    def official_evidence_complete(self) -> bool:
        return self.internal_ready and not self.external_reasons


class ControlledPilotGovernanceService:
    """Fail-closed pilot activation, kill-switch and deterministic go/no-go decision."""

    def __init__(
        self,
        unit_of_work_factory: FiscalUnitOfWorkFactory,
        *,
        readiness: DurableHomologationEnvironmentReadinessService,
    ) -> None:
        self._uow_factory = unit_of_work_factory
        self._readiness = readiness

    def activate(
        self,
        *,
        actor: AdminPrincipal,
        pilot: ControlledPilotScope,
        correlation_id: str,
        now: datetime,
    ) -> None:
        self._set_enabled(
            actor=actor,
            pilot=pilot,
            enabled=True,
            correlation_id=correlation_id,
            now=now,
        )

    def deactivate(
        self,
        *,
        actor: AdminPrincipal,
        pilot: ControlledPilotScope,
        correlation_id: str,
        now: datetime,
    ) -> None:
        self._set_enabled(
            actor=actor,
            pilot=pilot,
            enabled=False,
            correlation_id=correlation_id,
            now=now,
        )

    def record_scope_change(
        self,
        *,
        actor: AdminPrincipal,
        previous: ControlledPilotScope,
        current: ControlledPilotScope,
        correlation_id: str,
        now: datetime,
    ) -> None:
        if previous.pilot_id != current.pilot_id:
            raise FiscalValidationError("pilot scope change must preserve pilot_id")
        if previous.scope.tenant_id != current.scope.tenant_id:
            raise FiscalValidationError("pilot scope change cannot cross tenants")
        self._require_admin(actor, current.scope.tenant_id)
        self._append_audit(
            actor_id=actor.actor_id,
            action=ControlPlaneAuditAction.PILOT_SCOPE_CHANGED,
            pilot=current,
            correlation_id=correlation_id,
            now=now,
            detail="scope_changed",
        )

    def assess_external_scope(self, *, pilot: ControlledPilotScope) -> PilotScopeReadiness:
        """Require every explicitly allowlisted pilot operation to be ready.

        A successful cell never certifies another operation. This assessment does
        not perform provider calls and does not mutate pilot or fiscal authority.
        """

        internal_reasons: list[str] = []
        external_reasons: list[str] = []
        for required_operation in sorted(
            pilot.allowed_operations,
            key=lambda item: item.value,
        ):
            assessment = self._readiness.assess(
                scope=pilot.scope,
                document_kind=pilot.document_kind,
                jurisdiction=pilot.jurisdiction,
                operation=required_operation,
            )
            if assessment.provider_id != pilot.provider_id:
                internal_reasons.append(
                    f"pilot_provider_mismatch:{required_operation.value}"
                )
                continue
            if not assessment.internally_ready:
                details = assessment.missing_configuration or (
                    "technical_gate_not_ready",
                )
                internal_reasons.extend(
                    f"pilot_operation_not_internally_ready:{required_operation.value}:{detail}"
                    for detail in details
                )
                continue
            if not assessment.officially_homologated:
                external_reasons.append(
                    f"external_official_evidence_missing:{required_operation.value}"
                )

        return PilotScopeReadiness(
            pilot_id=pilot.pilot_id,
            internal_reasons=tuple(dict.fromkeys(internal_reasons)),
            external_reasons=tuple(dict.fromkeys(external_reasons)),
        )

    def decide(
        self,
        *,
        pilot: ControlledPilotScope,
        authorized_request: AuthorizedFiscalRequest,
        operation: ProviderOperation,
        correlation_id: str,
        now: datetime,
        require_external: bool = False,
    ) -> PilotDecision:
        if operation not in pilot.allowed_operations:
            return self._decision(
                pilot=pilot,
                authorized_request=authorized_request,
                operation=operation,
                status=PilotDecisionStatus.NO_GO,
                reasons=("operation_not_allowlisted",),
                provider_id=None,
                internal_ready=False,
                official=False,
                correlation_id=correlation_id,
                now=now,
            )
        required_capability = _OPERATION_CAPABILITY[operation]
        if authorized_request.capability is not required_capability:
            return self._decision(
                pilot=pilot,
                authorized_request=authorized_request,
                operation=operation,
                status=PilotDecisionStatus.NO_GO,
                reasons=("s2s_capability_mismatch",),
                provider_id=None,
                internal_ready=False,
                official=False,
                correlation_id=correlation_id,
                now=now,
            )
        if authorized_request.scope != pilot.scope:
            return self._decision(
                pilot=pilot,
                authorized_request=authorized_request,
                operation=operation,
                status=PilotDecisionStatus.NO_GO,
                reasons=("s2s_scope_mismatch",),
                provider_id=None,
                internal_ready=False,
                official=False,
                correlation_id=correlation_id,
                now=now,
            )
        if not self._pilot_enabled(pilot):
            return self._decision(
                pilot=pilot,
                authorized_request=authorized_request,
                operation=operation,
                status=PilotDecisionStatus.NO_GO,
                reasons=("pilot_kill_switch_disabled",),
                provider_id=None,
                internal_ready=False,
                official=False,
                correlation_id=correlation_id,
                now=now,
            )

        assessment = self._readiness.assess(
            scope=pilot.scope,
            document_kind=pilot.document_kind,
            jurisdiction=pilot.jurisdiction,
            operation=operation,
        )
        reasons: list[str] = []
        if assessment.provider_id != pilot.provider_id:
            reasons.append("provider_mismatch")
        if not assessment.internally_ready:
            reasons.extend(assessment.missing_configuration or ("technical_gate_not_ready",))
        if reasons:
            return self._decision(
                pilot=pilot,
                authorized_request=authorized_request,
                operation=operation,
                status=PilotDecisionStatus.NO_GO,
                reasons=tuple(dict.fromkeys(reasons)),
                provider_id=assessment.provider_id,
                internal_ready=False,
                official=assessment.officially_homologated,
                correlation_id=correlation_id,
                now=now,
            )

        status = PilotDecisionStatus.GO_INTERNAL
        decision_reasons: tuple[str, ...] = ("internal_pilot_ready",)
        official = assessment.officially_homologated
        if require_external:
            pilot_scope = self.assess_external_scope(pilot=pilot)
            if not pilot_scope.internal_ready:
                return self._decision(
                    pilot=pilot,
                    authorized_request=authorized_request,
                    operation=operation,
                    status=PilotDecisionStatus.NO_GO,
                    reasons=pilot_scope.internal_reasons,
                    provider_id=assessment.provider_id,
                    internal_ready=False,
                    official=False,
                    correlation_id=correlation_id,
                    now=now,
                )
            if not pilot_scope.official_evidence_complete:
                status = PilotDecisionStatus.BLOCKED_EXTERNAL
                decision_reasons = (
                    ("external_official_evidence_missing",)
                    if len(pilot.allowed_operations) == 1
                    else pilot_scope.external_reasons
                )
                official = False
            else:
                official = True
        return self._decision(
            pilot=pilot,
            authorized_request=authorized_request,
            operation=operation,
            status=status,
            reasons=decision_reasons,
            provider_id=assessment.provider_id,
            internal_ready=True,
            official=official,
            correlation_id=correlation_id,
            now=now,
        )

    def _set_enabled(
        self,
        *,
        actor: AdminPrincipal,
        pilot: ControlledPilotScope,
        enabled: bool,
        correlation_id: str,
        now: datetime,
    ) -> None:
        CommercialConfigurationService(self._uow_factory).set_module_binding(
            actor=actor,
            binding=UnitModuleBinding(
                tenant_id=pilot.scope.tenant_id,
                unit_id=pilot.scope.unit_id,
                environment=pilot.scope.environment,
                module_id=pilot.module_id,
                enabled=enabled,
            ),
        )
        self._append_audit(
            actor_id=actor.actor_id,
            action=(
                ControlPlaneAuditAction.PILOT_ACTIVATED
                if enabled
                else ControlPlaneAuditAction.PILOT_DEACTIVATED
            ),
            pilot=pilot,
            correlation_id=correlation_id,
            now=now,
            detail="enabled" if enabled else "disabled",
        )

    def _pilot_enabled(self, pilot: ControlledPilotScope) -> bool:
        with self._uow_factory() as uow:
            bindings = uow.commercial.list_module_bindings(
                tenant_id=pilot.scope.tenant_id,
                unit_id=pilot.scope.unit_id,
                environment=pilot.scope.environment,
            )
        return any(item.module_id == pilot.module_id and item.enabled for item in bindings)

    def _decision(
        self,
        *,
        pilot: ControlledPilotScope,
        authorized_request: AuthorizedFiscalRequest,
        operation: ProviderOperation,
        status: PilotDecisionStatus,
        reasons: tuple[str, ...],
        provider_id: str | None,
        internal_ready: bool,
        official: bool,
        correlation_id: str,
        now: datetime,
    ) -> PilotDecision:
        decision = PilotDecision(
            pilot_id=pilot.pilot_id,
            operation=operation,
            status=status,
            reasons=reasons,
            provider_id=provider_id,
            internal_ready=internal_ready,
            official_evidence_present=official,
        )
        self._append_audit(
            actor_id=authorized_request.caller.identity.caller_id,
            action=ControlPlaneAuditAction.PILOT_DECISION_RECORDED,
            pilot=pilot,
            correlation_id=correlation_id,
            now=now,
            detail=f"{status.value}:{','.join(reasons)}",
        )
        return decision

    def _append_audit(
        self,
        *,
        actor_id: str,
        action: ControlPlaneAuditAction,
        pilot: ControlledPilotScope,
        correlation_id: str,
        now: datetime,
        detail: str,
    ) -> None:
        digest = hashlib.sha256(
            f"{pilot.pilot_id}|{action.value}|{actor_id}|{correlation_id}|{now.isoformat()}".encode()
        ).hexdigest()[:32]
        event = ControlPlaneAuditEvent(
            event_id=f"pilot-{digest}",
            occurred_at=now,
            actor_id=actor_id,
            action=action,
            target_type="controlled_pilot",
            target_id=f"{pilot.pilot_id}|{detail}"[:256],
            correlation_id=correlation_id,
            tenant_id=pilot.scope.tenant_id,
            unit_id=pilot.scope.unit_id,
        )
        with self._uow_factory() as uow:
            uow.control_plane.append_audit(event)
            uow.commit()

    @staticmethod
    def _require_admin(actor: AdminPrincipal, tenant_id: str) -> None:
        if not actor.has_permission(ControlPlanePermission.COMMERCIAL_CONFIG_WRITE):
            raise ControlPlaneAuthorizationError("actor lacks commercial configuration permission")
        if not actor.can_access_tenant(tenant_id):
            raise ControlPlaneAuthorizationError("actor cannot access pilot tenant")
