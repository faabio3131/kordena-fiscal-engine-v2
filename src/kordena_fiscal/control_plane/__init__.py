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
    from .durable import (
        DurableControlPlaneClock,
        DurableControlPlaneService,
        SystemDurableControlPlaneClock,
    )


def __getattr__(name: str) -> Any:
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

        values = {
            "DurableControlPlaneClock": DurableControlPlaneClock,
            "DurableControlPlaneService": DurableControlPlaneService,
            "SystemDurableControlPlaneClock": SystemDurableControlPlaneClock,
        }
        return values[name]
    raise AttributeError(name)


__all__ = [
    "AdminPrincipal",
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
    "InMemoryControlPlaneState",
    "SecretReference",
    "SecretReferenceKind",
    "SystemDurableControlPlaneClock",
]
