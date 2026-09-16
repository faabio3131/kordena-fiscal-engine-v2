"""Governed platform-only administration for the commercial pricing catalog.

Pricing is business configuration, never source-code policy.  This boundary is the
only application-facing write service for publishing a new pricing catalog version.
Tenant administrators and customer portal identities must not use it.
"""

from __future__ import annotations

from kordena_fiscal.domain import FiscalValidationError
from kordena_fiscal.product.pricing import (
    CommercialPricingConfiguration,
    CommercialPricingRegistry,
)

from .models import AdminPrincipal, ControlPlanePermission
from .service import ControlPlaneAuthorizationError


class CommercialPricingAdministrationService:
    """Publish versioned pricing only from a global FM platform administrator.

    The concrete identity allowed to receive the global administrative principal is
    an operational IAM decision.  No person's email, username or identifier is
    hardcoded into the product.  In production, only explicitly designated FM
    platform administration accounts should receive this authority.
    """

    def __init__(self, registry: CommercialPricingRegistry) -> None:
        if not isinstance(registry, CommercialPricingRegistry):
            raise FiscalValidationError("registry must be CommercialPricingRegistry")
        self._registry = registry

    @property
    def current(self) -> CommercialPricingConfiguration | None:
        """Return the current catalog for read-only consumers."""

        return self._registry.current

    def publish(
        self,
        *,
        actor: AdminPrincipal,
        configuration: CommercialPricingConfiguration,
        expected_version: int | None,
    ) -> CommercialPricingConfiguration:
        """Publish a catalog version without any code or fiscal-authority change."""

        self._require_platform_pricing_admin(actor)
        return self._registry.publish(
            configuration,
            expected_version=expected_version,
        )

    @staticmethod
    def _require_platform_pricing_admin(actor: AdminPrincipal) -> None:
        if not isinstance(actor, AdminPrincipal):
            raise FiscalValidationError("actor must be AdminPrincipal")
        permission = ControlPlanePermission.COMMERCIAL_CONFIG_WRITE
        if not actor.has_permission(permission):
            raise ControlPlaneAuthorizationError(
                f"actor lacks required permission: {permission.value}"
            )
        if not actor.global_scope:
            raise ControlPlaneAuthorizationError(
                "pricing publication requires a global FM platform administrator"
            )
