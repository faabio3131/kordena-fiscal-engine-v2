"""Optional vertical extension surface for FM Fiscal Core.

Restaurant-specific logic is intentionally not imported here. Consumers that need
that sector module must opt in with ``kordena_fiscal.verticals.restaurant``.
"""

from .base import (
    CapabilityVerticalModule,
    VerticalCapabilityError,
    VerticalModule,
    VerticalModuleDescriptor,
    VerticalModuleError,
    VerticalModuleNotFoundError,
    VerticalModuleRegistry,
    VerticalRegistrationError,
)
from .standard import (
    FITNESS_VERTICAL,
    SAAS_VERTICAL,
    SERVICE_VERTICAL,
    neutral_vertical_modules,
)

__all__ = [
    "CapabilityVerticalModule",
    "FITNESS_VERTICAL",
    "SAAS_VERTICAL",
    "SERVICE_VERTICAL",
    "VerticalCapabilityError",
    "VerticalModule",
    "VerticalModuleDescriptor",
    "VerticalModuleError",
    "VerticalModuleNotFoundError",
    "VerticalModuleRegistry",
    "VerticalRegistrationError",
    "neutral_vertical_modules",
]
