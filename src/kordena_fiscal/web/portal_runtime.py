"""Durable server-side portal projections for the commercial NFCORE runtime.

The browser never chooses tenant authority. Every read is scoped from the authenticated
human session and backed by the canonical fiscal/control-plane unit of work. Fiscal
mutations remain delegated to an explicitly configured operation executor and fail
closed when that execution boundary is not yet present.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from typing import Any, Protocol

from fastapi import HTTPException, status

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
    ControlPlaneConflictError,
    ControlPlaneNotFoundError,
)
from kordena_fiscal.domain import FiscalEnvironment, FiscalValidationError
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
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._operation_executor = operation_executor

    def snapshot(self, *, authority: AuthenticatedHuman) -> Mapping[str, Any]:
        organization, units, _events = self._tenant_state(authority)
        environments = sorted(
            {
                environment.value
                for unit in units
                for environment in unit.enabled_environments
            }
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
            "unit_scope": "all" if authority.account.unit_ids is None else "restricted",
            "enabled_environments": environments,
            "fiscal_operations_configured": self._operation_executor is not None,
            "onboarding_stage": onboarding_stage,
            "basic_onboarding_complete": organization is not None and bool(units),
            "available_surfaces": sorted(self._DURABLE_SURFACES),
        }

    def surface(
        self,
        *,
        surface_id: str,
        authority: AuthenticatedHuman,
    ) -> Sequence[Mapping[str, Any]]:
        if surface_id not in self._DURABLE_SURFACES:
            raise _runtime_unavailable(
                f"Durable projection is not configured for portal surface {surface_id}"
            )

        organization, units, events = self._tenant_state(authority)
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
            )

        row = dict(self.snapshot(authority=authority))
        row["tenant_id"] = authority.tenant_id
        row["surface"] = surface_id
        return (row,)

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
