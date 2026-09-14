"""Neutral vertical declarations that do not depend on sector classifiers."""

from __future__ import annotations

from .base import CapabilityVerticalModule, VerticalModuleDescriptor

SERVICE_VERTICAL = CapabilityVerticalModule(
    VerticalModuleDescriptor(
        module_id="service",
        version="1",
        capabilities=frozenset({"operation.service"}),
        description=(
            "Generic service-operation semantics only; document/tax readiness remains "
            "authority of the common fiscal Core."
        ),
    )
)

FITNESS_VERTICAL = CapabilityVerticalModule(
    VerticalModuleDescriptor(
        module_id="fitness",
        version="1",
        capabilities=frozenset(
            {
                "operation.service",
                "operation.membership",
                "operation.recurring",
            }
        ),
        description=(
            "Fitness/membership operation semantics without restaurant-specific tax logic."
        ),
    )
)

SAAS_VERTICAL = CapabilityVerticalModule(
    VerticalModuleDescriptor(
        module_id="saas",
        version="1",
        capabilities=frozenset(
            {
                "operation.service",
                "operation.subscription",
                "operation.recurring",
            }
        ),
        description=(
            "SaaS/subscription operation semantics without restaurant-specific tax logic."
        ),
    )
)


def neutral_vertical_modules() -> tuple[CapabilityVerticalModule, ...]:
    """Return built-in neutral modules without importing optional sector classifiers."""

    return (SERVICE_VERTICAL, FITNESS_VERTICAL, SAAS_VERTICAL)
