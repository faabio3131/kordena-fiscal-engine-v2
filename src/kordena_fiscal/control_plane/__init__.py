"""Public FM Fiscal Control Plane domain surface."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

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
from .service import (
    ControlPlaneAuthorizationError,
    ControlPlaneConflictError,
    ControlPlaneError,
    ControlPlaneFoundationService,
    ControlPlaneNotFoundError,
    InMemoryControlPlaneState,
)

if TYPE_CHECKING:
    from .capability import (
        CapabilityControlContext,
        GovernedCapabilityReadinessService,
    )
    from .durable import (
        DurableControlPlaneClock,
        DurableControlPlaneService,
        SystemDurableControlPlaneClock,
    )


def __getattr__(name: str) -> Any:
    if name in {
        "CapabilityControlContext",
        "GovernedCapabilityReadinessService",
    }:
        from .capability import (
            CapabilityControlContext,
            GovernedCapabilityReadinessService,
        )

        capability_values = {
            "CapabilityControlContext": CapabilityControlContext,
            "GovernedCapabilityReadinessService": GovernedCapabilityReadinessService,
        }
        return capability_values[name]
    if name in {
        "DurableControlPlaneClock",
        "DurableControlPlaneService",
        "SystemDurableControlPlaneClock",
    }:
        from .durable import (
            DurableControlPlaneClock,
            DurableControlPlaneService,
            SystemDurableControlPlaneClock,
        )

        durable_values = {
            "DurableControlPlaneClock": DurableControlPlaneClock,
            "DurableControlPlaneService": DurableControlPlaneService,
            "SystemDurableControlPlaneClock": SystemDurableControlPlaneClock,
        }
        return durable_values[name]
    raise AttributeError(name)


__all__ = [
    "AdminPrincipal",
    "CapabilityControlContext",
    "ControlPlaneAuditAction",
    "ControlPlaneAuditEvent",
    "ControlPlaneAuthorizationError",
    "ControlPlaneConflictError",
    "ControlPlaneError",
    "ControlPlaneFoundationService",
    "ControlPlaneNotFoundError",
    "ControlPlanePermission",
    "DurableControlPlaneClock",
    "DurableControlPlaneService",
    "FiscalOrganization",
    "FiscalUnitRegistration",
    "GovernedCapabilityReadinessService",
    "InMemoryControlPlaneState",
    "SecretReference",
    "SecretReferenceKind",
    "SystemDurableControlPlaneClock",
]
