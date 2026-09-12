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
    from .operations import (
        ArchiveReferenceView,
        DeliveryAttemptView,
        DeliveryOperationView,
        OperationalControlPlaneService,
        ReconciliationControlView,
        ReconciliationIssueView,
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
    if name in {
        "ArchiveReferenceView",
        "DeliveryAttemptView",
        "DeliveryOperationView",
        "OperationalControlPlaneService",
        "ReconciliationControlView",
        "ReconciliationIssueView",
    }:
        from .operations import (
            ArchiveReferenceView,
            DeliveryAttemptView,
            DeliveryOperationView,
            OperationalControlPlaneService,
            ReconciliationControlView,
            ReconciliationIssueView,
        )

        operational_values = {
            "ArchiveReferenceView": ArchiveReferenceView,
            "DeliveryAttemptView": DeliveryAttemptView,
            "DeliveryOperationView": DeliveryOperationView,
            "OperationalControlPlaneService": OperationalControlPlaneService,
            "ReconciliationControlView": ReconciliationControlView,
            "ReconciliationIssueView": ReconciliationIssueView,
        }
        return operational_values[name]
    raise AttributeError(name)


__all__ = [
    "AdminPrincipal",
    "ArchiveReferenceView",
    "CapabilityControlContext",
    "ControlPlaneAuditAction",
    "ControlPlaneAuditEvent",
    "ControlPlaneAuthorizationError",
    "ControlPlaneConflictError",
    "ControlPlaneError",
    "ControlPlaneFoundationService",
    "ControlPlaneNotFoundError",
    "ControlPlanePermission",
    "DeliveryAttemptView",
    "DeliveryOperationView",
    "DurableControlPlaneClock",
    "DurableControlPlaneService",
    "FiscalOrganization",
    "FiscalUnitRegistration",
    "GovernedCapabilityReadinessService",
    "InMemoryControlPlaneState",
    "OperationalControlPlaneService",
    "ReconciliationControlView",
    "ReconciliationIssueView",
    "SecretReference",
    "SecretReferenceKind",
    "SystemDurableControlPlaneClock",
]
