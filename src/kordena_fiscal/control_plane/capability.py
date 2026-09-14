"""Governed Control Plane facade over the certified Capability & Readiness authority."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from kordena_fiscal.compliance import (
    CapabilityReadinessService,
    CapabilityReadinessSnapshot,
    FiscalActionCapability,
)
from kordena_fiscal.domain import (
    BrazilianJurisdiction,
    FiscalDocumentKind,
    FiscalEnvironment,
    FiscalValidationError,
    HostNamespace,
)
from kordena_fiscal.persistence.ports import FiscalUnitOfWorkFactory

from .models import AdminPrincipal, ControlPlanePermission
from .service import ControlPlaneAuthorizationError, ControlPlaneNotFoundError


def _required(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise FiscalValidationError(f"{field_name} must not be blank")
    if len(normalized) > 128:
        raise FiscalValidationError(f"{field_name} exceeds max length 128")
    return normalized


@dataclass(frozen=True, slots=True)
class CapabilityControlContext:
    """Exact administrative context used to resolve central fiscal readiness."""

    host_namespace: str
    tenant_id: str
    unit_id: str
    environment: FiscalEnvironment
    document_kind: FiscalDocumentKind
    instant: datetime

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "host_namespace",
            HostNamespace(self.host_namespace).value,
        )
        object.__setattr__(self, "tenant_id", _required(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "unit_id", _required(self.unit_id, "unit_id"))
        if not isinstance(self.environment, FiscalEnvironment):
            raise FiscalValidationError("environment must be FiscalEnvironment")
        if not isinstance(self.document_kind, FiscalDocumentKind):
            raise FiscalValidationError("document_kind must be FiscalDocumentKind")
        if self.instant.tzinfo is None or self.instant.utcoffset() is None:
            raise FiscalValidationError("instant must be timezone-aware")


class GovernedCapabilityReadinessService:
    """Authorize Control Plane capability reads without creating readiness authority.

    Administrative state only proves that the tenant/unit/environment is onboarded
    and has an effective fiscal profile. The existing CapabilityReadinessService
    remains the sole authority for readiness levels and fiscal actions.
    """

    def __init__(
        self,
        *,
        unit_of_work_factory: FiscalUnitOfWorkFactory,
        readiness: CapabilityReadinessService,
    ) -> None:
        if not isinstance(readiness, CapabilityReadinessService):
            raise FiscalValidationError("readiness must be CapabilityReadinessService")
        self._unit_of_work_factory = unit_of_work_factory
        self._readiness = readiness

    def query(
        self,
        *,
        actor: AdminPrincipal,
        context: CapabilityControlContext,
    ) -> CapabilityReadinessSnapshot:
        jurisdiction = self._resolve_jurisdiction(actor=actor, context=context)
        return self._readiness.query(
            jurisdiction=jurisdiction,
            document_kind=context.document_kind,
            environment=context.environment,
            instant=context.instant,
        )

    def require_action(
        self,
        *,
        actor: AdminPrincipal,
        context: CapabilityControlContext,
        action: FiscalActionCapability,
    ) -> CapabilityReadinessSnapshot:
        if not isinstance(action, FiscalActionCapability):
            raise FiscalValidationError("action must be FiscalActionCapability")
        jurisdiction = self._resolve_jurisdiction(actor=actor, context=context)
        return self._readiness.require_action(
            jurisdiction=jurisdiction,
            document_kind=context.document_kind,
            environment=context.environment,
            instant=context.instant,
            action=action,
        )

    def _resolve_jurisdiction(
        self,
        *,
        actor: AdminPrincipal,
        context: CapabilityControlContext,
    ) -> BrazilianJurisdiction:
        if not isinstance(actor, AdminPrincipal):
            raise FiscalValidationError("actor must be AdminPrincipal")
        if not isinstance(context, CapabilityControlContext):
            raise FiscalValidationError("context must be CapabilityControlContext")
        if not actor.has_permission(ControlPlanePermission.CAPABILITY_READ):
            raise ControlPlaneAuthorizationError(
                "actor lacks required permission: capability.read"
            )
        if not actor.can_access_tenant(context.tenant_id):
            raise ControlPlaneAuthorizationError(
                f"actor cannot access tenant: {context.tenant_id}"
            )

        with self._unit_of_work_factory() as uow:
            if uow.control_plane.get_organization(context.tenant_id) is None:
                raise ControlPlaneNotFoundError(
                    f"organization is not onboarded: {context.tenant_id}"
                )
            unit = uow.control_plane.get_unit(context.tenant_id, context.unit_id)
            if unit is None:
                raise ControlPlaneNotFoundError(
                    f"unit is not onboarded: {context.tenant_id}/{context.unit_id}"
                )
            if context.environment not in unit.enabled_environments:
                raise ControlPlaneAuthorizationError(
                    "capability environment is not enabled for the target unit"
                )
            profile = uow.control_plane.resolve_profile(
                host_namespace=context.host_namespace,
                tenant_id=context.tenant_id,
                unit_id=context.unit_id,
                environment=context.environment,
                instant=context.instant,
            )
        if profile is None:
            raise ControlPlaneNotFoundError(
                "no effective fiscal profile exists for the capability context"
            )
        return profile.address.jurisdiction
