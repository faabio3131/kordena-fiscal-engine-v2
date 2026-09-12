"""In-memory Control Plane foundation service used to certify V2-11 invariants."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol
from uuid import uuid4

from kordena_fiscal.domain import FiscalDomainError, FiscalEnvironment, FiscalValidationError

from .models import (
    AdminPrincipal,
    ControlPlaneAuditAction,
    ControlPlaneAuditEvent,
    ControlPlanePermission,
    FiscalOrganization,
    FiscalUnitRegistration,
    SecretReference,
    SecretReferenceKind,
)


class ControlPlaneError(FiscalDomainError):
    """Base error for governed administrative operations."""


class ControlPlaneAuthorizationError(ControlPlaneError):
    """Raised when an administrative actor lacks permission or scope."""


class ControlPlaneConflictError(ControlPlaneError):
    """Raised when an administrative identity or binding already exists."""


class ControlPlaneNotFoundError(ControlPlaneError):
    """Raised when an administrative target does not exist."""


class ControlPlaneClock(Protocol):
    def now(self) -> datetime:
        ...


class SystemControlPlaneClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


@dataclass(slots=True)
class InMemoryControlPlaneState:
    """Ephemeral foundation state; durable storage is deliberately a later block."""

    organizations: dict[str, FiscalOrganization] = field(default_factory=dict)
    units: dict[tuple[str, str], FiscalUnitRegistration] = field(default_factory=dict)
    secret_references: dict[
        tuple[str, str, FiscalEnvironment, SecretReferenceKind], SecretReference
    ] = field(default_factory=dict)
    audit_events: list[ControlPlaneAuditEvent] = field(default_factory=list)


class ControlPlaneFoundationService:
    """Governed administrative writes with RBAC, tenant isolation and audit facts."""

    def __init__(
        self,
        state: InMemoryControlPlaneState | None = None,
        *,
        clock: ControlPlaneClock | None = None,
    ) -> None:
        self._state = state or InMemoryControlPlaneState()
        self._clock = clock or SystemControlPlaneClock()

    @property
    def state(self) -> InMemoryControlPlaneState:
        return self._state

    def onboard_organization(
        self,
        *,
        actor: AdminPrincipal,
        tenant_id: str,
        legal_name: str,
        correlation_id: str,
    ) -> FiscalOrganization:
        self._require_permission(actor, ControlPlanePermission.ORGANIZATION_WRITE)
        if not actor.global_scope:
            raise ControlPlaneAuthorizationError(
                "organization onboarding requires a global-scope administrative actor"
            )
        organization = FiscalOrganization(tenant_id=tenant_id, legal_name=legal_name)
        if organization.tenant_id in self._state.organizations:
            raise ControlPlaneConflictError(
                f"organization already exists: {organization.tenant_id}"
            )
        self._state.organizations[organization.tenant_id] = organization
        self._append_audit(
            actor=actor,
            action=ControlPlaneAuditAction.ORGANIZATION_ONBOARDED,
            target_type="organization",
            target_id=organization.tenant_id,
            tenant_id=organization.tenant_id,
            unit_id=None,
            correlation_id=correlation_id,
        )
        return organization

    def onboard_unit(
        self,
        *,
        actor: AdminPrincipal,
        registration: FiscalUnitRegistration,
        correlation_id: str,
    ) -> FiscalUnitRegistration:
        if not isinstance(registration, FiscalUnitRegistration):
            raise FiscalValidationError("registration must be FiscalUnitRegistration")
        self._require_tenant_permission(
            actor,
            ControlPlanePermission.UNIT_WRITE,
            registration.tenant_id,
        )
        if registration.tenant_id not in self._state.organizations:
            raise ControlPlaneNotFoundError(
                f"organization is not onboarded: {registration.tenant_id}"
            )
        key = (registration.tenant_id, registration.unit_id)
        if key in self._state.units:
            raise ControlPlaneConflictError(
                "unit already exists: "
                f"{registration.tenant_id}/{registration.unit_id}"
            )
        self._state.units[key] = registration
        self._append_audit(
            actor=actor,
            action=ControlPlaneAuditAction.UNIT_ONBOARDED,
            target_type="unit",
            target_id=registration.unit_id,
            tenant_id=registration.tenant_id,
            unit_id=registration.unit_id,
            correlation_id=correlation_id,
        )
        return registration

    def bind_secret_reference(
        self,
        *,
        actor: AdminPrincipal,
        reference: SecretReference,
        correlation_id: str,
    ) -> SecretReference:
        if not isinstance(reference, SecretReference):
            raise FiscalValidationError("reference must be SecretReference")
        self._require_tenant_permission(
            actor,
            ControlPlanePermission.SECRET_REFERENCE_WRITE,
            reference.tenant_id,
        )
        unit_key = (reference.tenant_id, reference.unit_id)
        unit = self._state.units.get(unit_key)
        if unit is None:
            raise ControlPlaneNotFoundError(
                f"unit is not onboarded: {reference.tenant_id}/{reference.unit_id}"
            )
        if reference.environment not in unit.enabled_environments:
            raise ControlPlaneAuthorizationError(
                "secret reference environment is not enabled for the target unit"
            )
        key = (
            reference.tenant_id,
            reference.unit_id,
            reference.environment,
            reference.kind,
        )
        if key in self._state.secret_references:
            raise ControlPlaneConflictError(
                "secret reference kind is already bound for unit/environment"
            )
        self._state.secret_references[key] = reference
        self._append_audit(
            actor=actor,
            action=ControlPlaneAuditAction.SECRET_REFERENCE_BOUND,
            target_type="secret-reference",
            target_id=reference.reference_id,
            tenant_id=reference.tenant_id,
            unit_id=reference.unit_id,
            correlation_id=correlation_id,
        )
        return reference

    def list_audit(
        self,
        *,
        actor: AdminPrincipal,
        tenant_id: str | None = None,
    ) -> tuple[ControlPlaneAuditEvent, ...]:
        self._require_permission(actor, ControlPlanePermission.AUDIT_READ)
        if tenant_id is not None:
            if not actor.can_access_tenant(tenant_id):
                raise ControlPlaneAuthorizationError(
                    f"actor cannot access tenant audit: {tenant_id}"
                )
            return tuple(
                event for event in self._state.audit_events if event.tenant_id == tenant_id
            )
        if actor.global_scope:
            return tuple(self._state.audit_events)
        return tuple(
            event
            for event in self._state.audit_events
            if event.tenant_id in actor.tenant_ids
        )

    @staticmethod
    def _require_permission(
        actor: AdminPrincipal,
        permission: ControlPlanePermission,
    ) -> None:
        if not isinstance(actor, AdminPrincipal):
            raise FiscalValidationError("actor must be AdminPrincipal")
        if not actor.has_permission(permission):
            raise ControlPlaneAuthorizationError(
                f"actor lacks required permission: {permission.value}"
            )

    def _require_tenant_permission(
        self,
        actor: AdminPrincipal,
        permission: ControlPlanePermission,
        tenant_id: str,
    ) -> None:
        self._require_permission(actor, permission)
        if not actor.can_access_tenant(tenant_id):
            raise ControlPlaneAuthorizationError(
                f"actor cannot access tenant: {tenant_id}"
            )

    def _append_audit(
        self,
        *,
        actor: AdminPrincipal,
        action: ControlPlaneAuditAction,
        target_type: str,
        target_id: str,
        correlation_id: str,
        tenant_id: str,
        unit_id: str | None,
    ) -> None:
        event = ControlPlaneAuditEvent(
            event_id=f"audit-{uuid4().hex}",
            occurred_at=self._clock.now(),
            actor_id=actor.actor_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            correlation_id=correlation_id,
            tenant_id=tenant_id,
            unit_id=unit_id,
        )
        self._state.audit_events.append(event)
