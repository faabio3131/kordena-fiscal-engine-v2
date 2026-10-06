"""Durable server-side portal projections for the commercial NFCORE runtime.

The browser never chooses tenant authority. Every read is scoped from the authenticated
human session and backed by the canonical fiscal/control-plane unit of work. Fiscal
mutations remain delegated to an explicitly configured operation executor and fail
closed when that execution boundary is not yet present.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any, Protocol

from fastapi import HTTPException, status

from kordena_fiscal.compliance import CapabilityReadinessService, JurisdictionCapabilityError
from kordena_fiscal.compliance.capability_api import CapabilityReadinessError
from kordena_fiscal.contingency import FiscalOutboxStatus
from kordena_fiscal.control_plane.capability import (
    CapabilityControlContext,
    GovernedCapabilityReadinessService,
)
from kordena_fiscal.control_plane.durable import DurableControlPlaneService
from kordena_fiscal.control_plane.models import (
    AdminPrincipal,
    ControlPlaneAuditAction,
    ControlPlaneAuditEvent,
    ControlPlanePermission,
    FiscalOrganization,
    FiscalUnitRegistration,
)
from kordena_fiscal.control_plane.service import (
    ControlPlaneAuthorizationError,
    ControlPlaneConflictError,
    ControlPlaneNotFoundError,
)
from kordena_fiscal.domain import (
    ExecutionScope,
    FiscalDocumentKind,
    FiscalEnvironment,
    FiscalValidationError,
)
from kordena_fiscal.lifecycle import FiscalDocumentState
from kordena_fiscal.persistence.ports import FiscalUnitOfWorkFactory
from kordena_fiscal.security.human_identity import AuthenticatedHuman


class PortalOperationExecutor(Protocol):
    """Already-authorized fiscal operation boundary used by the human portal."""

    def execute(
        self,
        *,
        operation_id: str,
        authority: AuthenticatedHuman,
        payload: Mapping[str, Any],
        idempotency_key: str | None,
    ) -> Mapping[str, Any]: ...


def _runtime_unavailable(message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail={"code": "PORTAL_RUNTIME_NOT_READY", "message": message},
    )


def _portal_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message},
    )


class DurableHumanPortalExecutor:
    """Read canonical durable state and execute safe self-service configuration."""

    _DURABLE_SURFACES = frozenset(
        {
            "overview",
            "documents",
            "issuances",
            "errors",
            "reconciliation",
            "capabilities",
            "onboarding",
            "companies",
            "units",
            "environments",
            "audit",
            "settings",
        }
    )

    def __init__(
        self,
        unit_of_work_factory: FiscalUnitOfWorkFactory,
        *,
        operation_executor: PortalOperationExecutor | None = None,
        capability_readiness: CapabilityReadinessService | None = None,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._operation_executor = operation_executor
        self._capabilities = (
            GovernedCapabilityReadinessService(
                unit_of_work_factory=unit_of_work_factory,
                readiness=capability_readiness,
            )
            if capability_readiness is not None
            else None
        )

    def snapshot(self, *, authority: AuthenticatedHuman) -> Mapping[str, Any]:
        organization, units, _events = self._tenant_state(authority)
        configured_operations = tuple(
            getattr(self._operation_executor, "configured_operations", ())
        )
        environments = sorted(
            {environment.value for unit in units for environment in unit.enabled_environments}
        )
        if organization is None:
            onboarding_stage = "commercial_provisioning_required"
        elif not units:
            onboarding_stage = "unit_setup_required"
        else:
            onboarding_stage = "basic_setup_complete"
        return {
            "organization_onboarded": organization is not None,
            "legal_name": None if organization is None else organization.legal_name,
            "unit_count": len(units),
            "authorized_units": [
                {
                    "unit_id": unit.unit_id,
                    "display_name": unit.display_name,
                    "environments": sorted(env.value for env in unit.enabled_environments),
                }
                for unit in units
            ],
            "capability_readiness_configured": self._capabilities is not None,
            "legacy_unscoped_lifecycle_visibility": "excluded_unconfirmed",
            "unit_scope": "all" if authority.account.unit_ids is None else "restricted",
            "enabled_environments": environments,
            "fiscal_operation_executor_configured": self._operation_executor is not None,
            "fiscal_operations_configured": bool(configured_operations),
            "configured_fiscal_operations": list(configured_operations),
            "onboarding_stage": onboarding_stage,
            "basic_onboarding_complete": organization is not None and bool(units),
            "available_surfaces": sorted(self._DURABLE_SURFACES),
        }

    def surface(
        self,
        *,
        surface_id: str,
        authority: AuthenticatedHuman,
        unit_id: str | None = None,
        environment: FiscalEnvironment | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[Mapping[str, Any]]:
        if surface_id not in self._DURABLE_SURFACES:
            raise _runtime_unavailable(
                f"Durable projection is not configured for portal surface {surface_id}"
            )

        organization, units, events = self._tenant_state(authority)
        if unit_id is not None:
            units = tuple(unit for unit in units if unit.unit_id == unit_id)
            if not units:
                raise _portal_error(409, "UNIT_NOT_CONFIGURED", "Selected unit is not configured")
        if surface_id in {"documents", "issuances", "errors", "reconciliation", "capabilities"}:
            if not units:
                return ()
            if len(units) != 1:
                raise _portal_error(409, "UNIT_SELECTION_REQUIRED", "Select an authorized unit")
            selected_environment = environment or FiscalEnvironment.HOMOLOGATION
            if selected_environment not in units[0].enabled_environments:
                raise _portal_error(
                    409, "ENVIRONMENT_NOT_ENABLED", "Selected environment is not enabled"
                )
            scope = ExecutionScope(
                host_namespace="fm-nfcore",
                tenant_id=authority.tenant_id,
                unit_id=units[0].unit_id,
                environment=selected_environment,
                correlation_id="portal-projection",
            )
            return self._fiscal_surface(surface_id, authority, scope, limit, offset)

        if surface_id == "companies":
            if organization is None:
                return ()
            return (
                {
                    "tenant_id": organization.tenant_id,
                    "legal_name": organization.legal_name,
                    "status": "onboarded",
                },
            )
        if surface_id == "units":
            return tuple(
                {
                    "unit_id": unit.unit_id,
                    "display_name": unit.display_name,
                    "enabled_environments": sorted(
                        environment.value for environment in unit.enabled_environments
                    ),
                }
                for unit in units
            )
        if surface_id == "environments":
            return tuple(
                {
                    "unit_id": unit.unit_id,
                    "environment": environment.value,
                    "enabled": True,
                }
                for unit in units
                for environment in sorted(
                    unit.enabled_environments,
                    key=lambda item: item.value,
                )
            )
        if surface_id == "audit":
            return tuple(
                {
                    "event_id": event.event_id,
                    "occurred_at": event.occurred_at.isoformat(),
                    "action": event.action.value,
                    "target_type": event.target_type,
                    "target_id": event.target_id,
                    "correlation_id": event.correlation_id,
                    "unit_id": event.unit_id,
                }
                for event in events
                if (
                    (authority.account.unit_ids is None and unit_id is None)
                    or event.unit_id in {unit.unit_id for unit in units}
                )
            )

        row = dict(self.snapshot(authority=authority))
        row["tenant_id"] = authority.tenant_id
        row["surface"] = surface_id
        return (row,)

    def _fiscal_surface(
        self,
        surface_id: str,
        authority: AuthenticatedHuman,
        scope: ExecutionScope,
        limit: int,
        offset: int,
    ) -> Sequence[Mapping[str, Any]]:
        base = {"unit_id": scope.unit_id, "environment": scope.environment.value}
        if surface_id == "capabilities":
            return self._capability_rows(authority, scope)[offset : offset + limit]
        rows: list[Mapping[str, Any]] = []
        with self._unit_of_work_factory() as uow:
            if surface_id in {"documents", "issuances", "errors"}:
                for snapshot in uow.lifecycle.list_for_scope(
                    scope,
                    limit=limit,
                    offset=offset,
                    states=(
                        frozenset({FiscalDocumentState.ERROR, FiscalDocumentState.REJECTED})
                        if surface_id == "errors"
                        else None
                    ),
                ):
                    if surface_id == "errors" and snapshot.state not in {
                        FiscalDocumentState.ERROR,
                        FiscalDocumentState.REJECTED,
                    }:
                        continue
                    attempt = (
                        uow.idempotency.latest_for_document(snapshot.document_id)
                        if surface_id == "issuances"
                        else None
                    )
                    rows.append(
                        {
                            **base,
                            **(
                                {
                                    "attempt_status": attempt.status.value,
                                    "attempt_generation": attempt.generation,
                                }
                                if attempt
                                else {}
                            ),
                            "record_type": "lifecycle",
                            "document_id": snapshot.document_id,
                            "state": snapshot.state.value,
                            "version": snapshot.version,
                            "updated_at": snapshot.updated_at.isoformat(),
                        }
                    )
            if surface_id == "documents":
                for entry in uow.archive.list_for_scope(scope, limit=limit, offset=offset):
                    rows.append(
                        {
                            **base,
                            "record_type": "archive",
                            "entry_id": entry.entry_id,
                            "document_reference": entry.document_reference,
                            "kind": entry.kind.value,
                            "archived_at": entry.archived_at.isoformat(),
                            "content_sha256": entry.content_sha256,
                            "media_type": entry.media_type,
                        }
                    )
            if surface_id in {"issuances", "errors"}:
                for queued in uow.outbox.list_for_scope(
                    scope,
                    limit=limit,
                    offset=offset,
                    statuses=(
                        frozenset({FiscalOutboxStatus.RETRY_WAIT, FiscalOutboxStatus.DEAD_LETTER})
                        if surface_id == "errors"
                        else None
                    ),
                ):
                    if surface_id == "errors" and queued.status not in {
                        FiscalOutboxStatus.RETRY_WAIT,
                        FiscalOutboxStatus.DEAD_LETTER,
                    }:
                        continue
                    rows.append(
                        {
                            **base,
                            "record_type": "outbox",
                            "entry_id": queued.entry_id,
                            "operation": queued.operation,
                            "status": queued.status.value,
                            "attempt_count": queued.attempt_count,
                            "created_at": queued.created_at.isoformat(),
                            "available_at": queued.available_at.isoformat(),
                            "correlation_id": queued.scope.correlation_id,
                        }
                    )
            if surface_id == "reconciliation":
                for result in uow.reconciliations.list_for_scope(scope, limit=limit, offset=offset):
                    rows.append(
                        {
                            **base,
                            "record_type": "reconciliation",
                            "source_type": result.source.source_type,
                            "source_id": result.source.source_id,
                            "status": result.status.value,
                            "document_id": result.selected_document_id,
                            "issue_codes": [issue.code.value for issue in result.issues],
                            "correlation_id": result.scope.correlation_id,
                        }
                    )
        return tuple(rows)

    def _capability_rows(
        self,
        authority: AuthenticatedHuman,
        scope: ExecutionScope,
    ) -> tuple[Mapping[str, Any], ...]:
        rows: list[Mapping[str, Any]] = []
        actor = AdminPrincipal(
            actor_id="portal-" + hashlib.sha256(authority.account.account_id.encode()).hexdigest(),
            permissions=frozenset({ControlPlanePermission.CAPABILITY_READ}),
            tenant_ids=frozenset({authority.tenant_id}),
        )
        for kind in FiscalDocumentKind:
            row: dict[str, Any] = {
                "unit_id": scope.unit_id,
                "environment": scope.environment.value,
                "document_kind": kind.value,
            }
            if self._capabilities is None:
                row.update(status="blocked", code="CAPABILITY_AUTHORITY_NOT_CONFIGURED")
            else:
                try:
                    snapshot = self._capabilities.query(
                        actor=actor,
                        context=CapabilityControlContext(
                            host_namespace="fm-nfcore",
                            tenant_id=scope.tenant_id,
                            unit_id=scope.unit_id,
                            environment=scope.environment,
                            document_kind=kind,
                            instant=datetime.now(UTC),
                        ),
                    )
                    row.update(
                        status="declared",
                        readiness=snapshot.readiness.name,
                        capability_version=snapshot.capability_version,
                        actions=[action.value for action in snapshot.actions],
                        effective_from=snapshot.effective_from.isoformat(),
                        effective_to=(
                            snapshot.effective_to.isoformat() if snapshot.effective_to else None
                        ),
                    )
                except (
                    CapabilityReadinessError,
                    JurisdictionCapabilityError,
                    ControlPlaneNotFoundError,
                    FiscalValidationError,
                ):
                    row.update(status="blocked", code="CAPABILITY_OR_PROFILE_NOT_CONFIGURED")
                except ControlPlaneAuthorizationError as exc:
                    raise _portal_error(
                        403, "PORTAL_FORBIDDEN", "Capability scope is not authorized"
                    ) from exc
            rows.append(row)
        return tuple(rows)

    def execute(
        self,
        *,
        operation_id: str,
        authority: AuthenticatedHuman,
        payload: Mapping[str, Any],
        idempotency_key: str | None,
    ) -> Mapping[str, Any]:
        if operation_id == "onboardUnit":
            return self._onboard_unit(
                authority=authority,
                payload=payload,
                idempotency_key=idempotency_key,
            )
        if self._operation_executor is None:
            raise _runtime_unavailable("Fiscal portal operation executor is not configured")
        return self._operation_executor.execute(
            operation_id=operation_id,
            authority=authority,
            payload=payload,
            idempotency_key=idempotency_key,
        )

    def _onboard_unit(
        self,
        *,
        authority: AuthenticatedHuman,
        payload: Mapping[str, Any],
        idempotency_key: str | None,
    ) -> Mapping[str, Any]:
        unit_id = payload.get("unit_id")
        display_name = payload.get("display_name")
        if not isinstance(unit_id, str) or not isinstance(display_name, str):
            raise _portal_error(
                status.HTTP_400_BAD_REQUEST,
                "INVALID_UNIT_ONBOARDING",
                "unit_id and display_name are required",
            )
        if not idempotency_key:
            raise _portal_error(
                status.HTTP_400_BAD_REQUEST,
                "MISSING_IDEMPOTENCY_KEY",
                "Idempotency-Key is required",
            )

        registration = FiscalUnitRegistration(
            tenant_id=authority.tenant_id,
            unit_id=unit_id,
            display_name=display_name,
            enabled_environments=frozenset({FiscalEnvironment.HOMOLOGATION}),
        )
        with self._unit_of_work_factory() as uow:
            organization = uow.control_plane.get_organization(authority.tenant_id)
            existing = uow.control_plane.get_unit(authority.tenant_id, registration.unit_id)
        if organization is None:
            raise _portal_error(
                status.HTTP_409_CONFLICT,
                "COMMERCIAL_PROVISIONING_REQUIRED",
                "Commercial tenant organization must be provisioned before unit setup",
            )
        if existing is not None:
            if existing == registration:
                return {
                    "status": "already_onboarded",
                    "unit_id": existing.unit_id,
                    "environment": FiscalEnvironment.HOMOLOGATION.value,
                }
            raise _portal_error(
                status.HTTP_409_CONFLICT,
                "UNIT_ALREADY_EXISTS",
                "Unit already exists with different configuration",
            )

        actor_digest = hashlib.sha256(authority.account.account_id.encode("utf-8")).hexdigest()
        actor = AdminPrincipal(
            actor_id=f"human-{actor_digest[:24]}",
            permissions=frozenset({ControlPlanePermission.UNIT_WRITE}),
            tenant_ids=frozenset({authority.tenant_id}),
        )
        service = DurableControlPlaneService(self._unit_of_work_factory)
        try:
            created = service.onboard_unit(
                actor=actor,
                registration=registration,
                correlation_id=idempotency_key,
            )
        except ControlPlaneNotFoundError as exc:
            raise _portal_error(
                status.HTTP_409_CONFLICT,
                "COMMERCIAL_PROVISIONING_REQUIRED",
                "Commercial tenant organization must be provisioned before unit setup",
            ) from exc
        except ControlPlaneConflictError as exc:
            raise _portal_error(
                status.HTTP_409_CONFLICT,
                "UNIT_ONBOARDING_CONFLICT",
                "Unit onboarding conflicts with existing state",
            ) from exc
        except FiscalValidationError as exc:
            raise _portal_error(
                status.HTTP_400_BAD_REQUEST,
                "INVALID_UNIT_ONBOARDING",
                "Unit onboarding payload is invalid",
            ) from exc
        return {
            "status": "onboarded",
            "unit_id": created.unit_id,
            "environment": FiscalEnvironment.HOMOLOGATION.value,
        }

    def _tenant_state(
        self,
        authority: AuthenticatedHuman,
    ) -> tuple[
        FiscalOrganization | None,
        tuple[FiscalUnitRegistration, ...],
        tuple[ControlPlaneAuditEvent, ...],
    ]:
        tenant_id = authority.tenant_id
        with self._unit_of_work_factory() as uow:
            organization = uow.control_plane.get_organization(tenant_id)
            events = uow.control_plane.list_audit(tenant_id)
            discovered_unit_ids = {
                event.target_id
                for event in events
                if event.action is ControlPlaneAuditAction.UNIT_ONBOARDED
            }
            if authority.account.unit_ids is not None:
                discovered_unit_ids &= set(authority.account.unit_ids)
            units = tuple(
                unit
                for unit_id in sorted(discovered_unit_ids)
                if (unit := uow.control_plane.get_unit(tenant_id, unit_id)) is not None
            )
        return organization, units, events
