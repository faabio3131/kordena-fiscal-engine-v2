"""Governed Cakto checkout adapter for FM NFCORE.

This provider-specific module maps configured Cakto product/offer bindings onto the
provider-neutral commercial checkout contract. Cakto remains an infrastructure boundary;
canonical pricing, release and public commercial-offer code must not depend on Cakto types.
"""

from __future__ import annotations

from urllib.parse import urlsplit

from kordena_fiscal.control_plane.models import AdminPrincipal, ControlPlanePermission
from kordena_fiscal.control_plane.service import ControlPlaneAuthorizationError
from kordena_fiscal.domain import FiscalValidationError
from kordena_fiscal.product.cakto import (
    CaktoPlanBinding,
    CaktoUnitOfWorkFactory,
)
from kordena_fiscal.product.checkout import (
    CommercialCheckoutItem,
    CommercialCheckoutProjection,
    CommercialCheckoutStatus,
)
from kordena_fiscal.product.pricing import CommercialPricingConfiguration

# Backward-compatible provider-local names. Canonical consumers must import
# the provider-neutral contract from kordena_fiscal.product.checkout.
CaktoCheckoutItem = CommercialCheckoutItem
CaktoCheckoutProjection = CommercialCheckoutProjection
CaktoCheckoutStatus = CommercialCheckoutStatus


def parse_cakto_external_price_reference(reference: str | None) -> tuple[str, str] | None:
    """Parse one Cakto adapter reference into external product and offer IDs."""

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
    """Configure Cakto bindings and project them through the canonical checkout port."""

    provider_id = "cakto"

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
    ) -> CommercialCheckoutProjection:
        if pricing is None:
            return CommercialCheckoutProjection(
                status=CommercialCheckoutStatus.UNCONFIGURED,
                provider=self.provider_id,
                expected_count=0,
                configured_count=0,
                items=(),
            )

        active_prices = {price.price_id: price for price in pricing.prices if price.enabled}
        expected: list[tuple[str, str]] = []
        projected: list[CommercialCheckoutItem] = []

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
                        CommercialCheckoutItem(
                            plan_id=plan.plan_id,
                            price_id=price.price_id,
                            provider=self.provider_id,
                            checkout_url=binding.checkout_url,
                        )
                    )

        expected_count = len(expected)
        configured_count = len(projected)
        if expected_count == 0 or configured_count == 0:
            status = CommercialCheckoutStatus.UNCONFIGURED
        elif configured_count == expected_count:
            status = CommercialCheckoutStatus.CONFIGURED
        else:
            status = CommercialCheckoutStatus.PARTIAL

        return CommercialCheckoutProjection(
            status=status,
            provider=self.provider_id,
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
