"""Governed platform-only administration for the commercial pricing catalog.

Pricing is business configuration, never source-code policy. This module owns the
single application write boundary for publishing pricing catalog versions. Durable
storage implementations plug into the same boundary; no parallel billing authority
is introduced.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from kordena_fiscal.domain import FiscalValidationError
from kordena_fiscal.product.pricing import (
    CommercialPricingConfiguration,
    CommercialPricingError,
    CommercialPricingRegistry,
)

from .models import AdminPrincipal, ControlPlanePermission
from .service import ControlPlaneAuthorizationError


@dataclass(frozen=True, slots=True)
class PricingCatalogPublication:
    """Immutable audit metadata for one published pricing catalog version."""

    configuration: CommercialPricingConfiguration
    actor_id: str
    correlation_id: str
    published_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.configuration, CommercialPricingConfiguration):
            raise FiscalValidationError("configuration must be CommercialPricingConfiguration")
        if not self.actor_id.strip():
            raise FiscalValidationError("actor_id must not be blank")
        if not self.correlation_id.strip():
            raise FiscalValidationError("correlation_id must not be blank")
        if self.published_at.tzinfo is None or self.published_at.utcoffset() is None:
            raise FiscalValidationError("published_at must be timezone-aware")


class CommercialPricingCatalog(Protocol):
    """Persistence-neutral catalog contract used by the sole administration service."""

    @property
    def current(self) -> CommercialPricingConfiguration | None: ...

    def history(self) -> tuple[PricingCatalogPublication, ...]: ...

    def publish(
        self,
        configuration: CommercialPricingConfiguration,
        *,
        expected_version: int | None,
        actor_id: str,
        correlation_id: str,
        published_at: datetime,
    ) -> PricingCatalogPublication: ...


class _RegistryPricingCatalog:
    """Compatibility adapter for the existing in-memory product registry."""

    def __init__(self, registry: CommercialPricingRegistry) -> None:
        self._registry = registry
        self._history: list[PricingCatalogPublication] = []

    @property
    def current(self) -> CommercialPricingConfiguration | None:
        return self._registry.current

    def history(self) -> tuple[PricingCatalogPublication, ...]:
        return tuple(reversed(self._history))

    def publish(
        self,
        configuration: CommercialPricingConfiguration,
        *,
        expected_version: int | None,
        actor_id: str,
        correlation_id: str,
        published_at: datetime,
    ) -> PricingCatalogPublication:
        published = self._registry.publish(configuration, expected_version=expected_version)
        publication = PricingCatalogPublication(
            configuration=published,
            actor_id=actor_id,
            correlation_id=correlation_id,
            published_at=published_at,
        )
        self._history.append(publication)
        return publication


class CommercialPricingAdministrationService:
    """Publish versioned pricing only from a global FM platform administrator.

    The concrete human allowed to receive platform administration authority is an
    operational IAM decision. No person's email, username or identifier is hardcoded
    into the product.
    """

    def __init__(
        self,
        catalog: CommercialPricingCatalog | CommercialPricingRegistry,
    ) -> None:
        if isinstance(catalog, CommercialPricingRegistry):
            self._catalog: CommercialPricingCatalog = _RegistryPricingCatalog(catalog)
        else:
            self._catalog = catalog

    @property
    def current(self) -> CommercialPricingConfiguration | None:
        """Return the current catalog for read-only consumers."""

        return self._catalog.current

    def history(self) -> tuple[PricingCatalogPublication, ...]:
        """Return newest-first immutable publication history."""

        return self._catalog.history()

    def publish(
        self,
        *,
        actor: AdminPrincipal,
        configuration: CommercialPricingConfiguration,
        expected_version: int | None,
        correlation_id: str = "pricing-admin",
        published_at: datetime | None = None,
    ) -> CommercialPricingConfiguration:
        """Publish a catalog version without any source-code or fiscal-authority change."""

        self._require_platform_pricing_admin(actor)
        if not isinstance(configuration, CommercialPricingConfiguration):
            raise FiscalValidationError("configuration must be CommercialPricingConfiguration")
        normalized_correlation = correlation_id.strip()
        if not normalized_correlation:
            raise FiscalValidationError("correlation_id must not be blank")
        instant = published_at or datetime.now(UTC)
        publication = self._catalog.publish(
            configuration,
            expected_version=expected_version,
            actor_id=actor.actor_id,
            correlation_id=normalized_correlation,
            published_at=instant,
        )
        return publication.configuration

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


__all__ = [
    "CommercialPricingAdministrationService",
    "CommercialPricingCatalog",
    "PricingCatalogPublication",
    "CommercialPricingError",
]
