"""Governed Cakto checkout configuration and projection for FM NFCORE.

This module composes existing authorities instead of introducing a second checkout
store. Pricing owns the external reference, CaktoPlanBinding owns provider mapping,
commercial release owns human sale approval and the Cakto runtime owns webhook
processing readiness.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from urllib.parse import urlsplit

from kordena_fiscal.control_plane.models import AdminPrincipal, ControlPlanePermission
from kordena_fiscal.control_plane.service import ControlPlaneAuthorizationError
from kordena_fiscal.domain import FiscalValidationError
from kordena_fiscal.product.cakto import (
    CaktoPlanBinding,
    CaktoUnitOfWorkFactory,
)
from kordena_fiscal.product.pricing import CommercialPricingConfiguration


class CaktoCheckoutStatus(StrEnum):
    UNCONFIGURED = "unconfigured"
    PARTIAL = "partial"
    CONFIGURED = "configured"


@dataclass(frozen=True, slots=True)
class CaktoCheckoutItem:
    plan_id: str
    price_id: str
    checkout_url: str

    def to_mapping(self, *, expose_url: bool) -> dict[str, object]:
        return {
            "plan_id": self.plan_id,
            "price_id": self.price_id,
            "provider": "cakto",
            "checkout_url": self.checkout_url if expose_url else None,
        }


@dataclass(frozen=True, slots=True)
class CaktoCheckoutProjection:
    status: CaktoCheckoutStatus
    expected_count: int
    configured_count: int
    items: tuple[CaktoCheckoutItem, ...]

    def __post_init__(self) -> None:
        if self.expected_count < 0 or self.configured_count < 0:
            raise FiscalValidationError("checkout projection counts cannot be negative")
        if self.configured_count > self.expected_count:
            raise FiscalValidationError(
                "configured checkout count cannot exceed expected count"
            )
        if self.configured_count != len(self.items):
            raise FiscalValidationError(
                "configured checkout count must match projected items"
            )

    def to_public_mapping(
        self,
        *,
        processing_configured: bool,
        expose_urls: bool,
    ) -> dict[str, object]:
        return {
            "status": self.status.value,
            "provider": "cakto",
            "processing_status": (
                "configured" if processing_configured else "unconfigured"
            ),
            "items": [
                item.to_mapping(expose_url=expose_urls)
                for item in self.items
            ],
        }


def parse_cakto_external_price_reference(reference: str | None) -> tuple[str, str] | None:
    """Parse the provider-neutral pricing reference into the canonical Cakto IDs."""

    if reference is None:
        return None
    normalized = reference.strip()
    if not normalized:
        return None
    parsed = urlsplit(normalized)
    if parsed.scheme.casefold() != "cakto":
        return None
    if (
        not parsed.netloc
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        return None
    segments = tuple(segment for segment in parsed.path.split("/") if segment)
    if len(segments) != 1:
        return None
    product_id = parsed.netloc.strip()
    offer_id = segments[0].strip()
    if not product_id or not offer_id:
        return None
    if len(product_id) > 256 or len(offer_id) > 256:
        return None
    return product_id, offer_id


class CaktoCheckoutAdministrationService:
    """Configure and resolve Cakto checkout using the existing durable binding store."""

    def __init__(self, unit_of_work_factory: CaktoUnitOfWorkFactory) -> None:
        self._unit_of_work_factory = unit_of_work_factory

    def bindings(self, *, actor: AdminPrincipal) -> tuple[CaktoPlanBinding, ...]:
        self._require_platform_admin(actor)
        with self._unit_of_work_factory() as uow:
            return uow.commercial.list_cakto_plan_bindings()

    def set_binding(
        self,
        *,
        actor: AdminPrincipal,
        binding: CaktoPlanBinding,
    ) -> CaktoPlanBinding:
        self._require_platform_admin(actor)
        if not isinstance(binding, CaktoPlanBinding):
            raise FiscalValidationError("binding must be CaktoPlanBinding")
        with self._unit_of_work_factory() as uow:
            persisted = uow.commercial.put_cakto_plan_binding(binding)
            uow.commit()
            return persisted

    def project(
        self,
        pricing: CommercialPricingConfiguration | None,
    ) -> CaktoCheckoutProjection:
        if pricing is None:
            return CaktoCheckoutProjection(
                status=CaktoCheckoutStatus.UNCONFIGURED,
                expected_count=0,
                configured_count=0,
                items=(),
            )

        active_prices = {price.price_id: price for price in pricing.prices if price.enabled}
        expected: list[tuple[str, str]] = []
        projected: list[CaktoCheckoutItem] = []

        with self._unit_of_work_factory() as uow:
            for plan in pricing.plans:
                if not plan.enabled:
                    continue
                for price_id in plan.price_ids:
                    price = active_prices.get(price_id)
                    if price is None:
                        continue
                    expected.append((plan.plan_id, price.price_id))
                    external = parse_cakto_external_price_reference(
                        price.external_price_reference
                    )
                    if external is None:
                        continue
                    external_product_id, external_offer_id = external
                    binding = uow.commercial.resolve_cakto_plan_binding(
                        external_product_id,
                        external_offer_id,
                    )
                    if (
                        binding is None
                        or not binding.enabled
                        or binding.plan_id != plan.plan_id
                    ):
                        continue
                    projected.append(
                        CaktoCheckoutItem(
                            plan_id=plan.plan_id,
                            price_id=price.price_id,
                            checkout_url=binding.checkout_url,
                        )
                    )

        expected_count = len(expected)
        configured_count = len(projected)
        if expected_count == 0 or configured_count == 0:
            status = CaktoCheckoutStatus.UNCONFIGURED
        elif configured_count == expected_count:
            status = CaktoCheckoutStatus.CONFIGURED
        else:
            status = CaktoCheckoutStatus.PARTIAL

        return CaktoCheckoutProjection(
            status=status,
            expected_count=expected_count,
            configured_count=configured_count,
            items=tuple(projected),
        )

    @staticmethod
    def _require_platform_admin(actor: AdminPrincipal) -> None:
        if not isinstance(actor, AdminPrincipal):
            raise FiscalValidationError("actor must be AdminPrincipal")
        permission = ControlPlanePermission.COMMERCIAL_CONFIG_WRITE
        if not actor.has_permission(permission):
            raise ControlPlaneAuthorizationError(
                f"actor lacks required permission: {permission.value}"
            )
        if not actor.global_scope:
            raise ControlPlaneAuthorizationError(
                "Cakto checkout configuration requires global FM platform authority"
            )


__all__ = [
    "CaktoCheckoutAdministrationService",
    "CaktoCheckoutItem",
    "CaktoCheckoutProjection",
    "CaktoCheckoutStatus",
    "parse_cakto_external_price_reference",
]
