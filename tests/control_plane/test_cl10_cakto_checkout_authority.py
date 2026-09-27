from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from kordena_fiscal.control_plane.cakto_checkout import (
    CaktoCheckoutAdministrationService,
    CaktoCheckoutStatus,
    parse_cakto_external_price_reference,
)
from kordena_fiscal.control_plane.models import AdminPrincipal, ControlPlanePermission
from kordena_fiscal.control_plane.service import ControlPlaneAuthorizationError
from kordena_fiscal.persistence.cakto import SqliteCaktoCommercialDatabase
from kordena_fiscal.product.cakto import CaktoPlanBinding
from kordena_fiscal.product.pricing import (
    BillingCadence,
    CommercialPricingConfiguration,
    PlanDefinition,
    PriceDefinition,
)


def _actor(*, global_scope: bool = True) -> AdminPrincipal:
    return AdminPrincipal(
        actor_id="fm-platform-admin",
        permissions=frozenset({ControlPlanePermission.COMMERCIAL_CONFIG_WRITE}),
        global_scope=global_scope,
        tenant_ids=frozenset() if global_scope else frozenset({"tenant-a"}),
    )


def _database(tmp_path: Path) -> SqliteCaktoCommercialDatabase:
    database = SqliteCaktoCommercialDatabase(tmp_path / "cl10-cakto.sqlite3")
    assert database.initialize() is True
    return database


def _configuration(
    *references: str | None,
) -> CommercialPricingConfiguration:
    prices = tuple(
        PriceDefinition(
            price_id=f"nfcore-price-{index}",
            currency="BRL",
            cadence=BillingCadence.MONTHLY,
            base_amount=Decimal("100.00") + index,
            external_price_reference=reference,
        )
        for index, reference in enumerate(references, start=1)
    )
    return CommercialPricingConfiguration(
        configuration_id="nfcore-checkout-test",
        version=1,
        prices=prices,
        plans=(
            PlanDefinition(
                plan_id="nfcore-pro",
                display_name="NFCore Pro",
                edition_id="pro",
                price_ids=tuple(price.price_id for price in prices),
            ),
        ),
    )


def test_cakto_reference_parser_is_strict_and_provider_specific() -> None:
    assert parse_cakto_external_price_reference(
        "cakto://product-1/offer-1"
    ) == ("product-1", "offer-1")
    assert parse_cakto_external_price_reference(None) is None
    assert parse_cakto_external_price_reference("gateway://product/offer") is None
    assert parse_cakto_external_price_reference("cakto://product") is None
    assert parse_cakto_external_price_reference(
        "cakto://product/offer?token=secret"
    ) is None
    assert parse_cakto_external_price_reference(
        "cakto://user:pass@product/offer"
    ) is None


def test_checkout_projection_is_unconfigured_partial_then_configured(
    tmp_path: Path,
) -> None:
    database = _database(tmp_path)
    service = CaktoCheckoutAdministrationService(database)
    pricing = _configuration(
        "cakto://product-1/offer-1",
        "cakto://product-1/offer-2",
    )

    empty = service.project(pricing)
    assert empty.status is CaktoCheckoutStatus.UNCONFIGURED
    assert empty.expected_count == 2
    assert empty.configured_count == 0

    first = CaktoPlanBinding(
        external_product_id="product-1",
        external_offer_id="offer-1",
        plan_id="nfcore-pro",
        entitlement_ids=("portal", "fiscal-core"),
    )
    service.set_binding(actor=_actor(), binding=first)

    partial = service.project(pricing)
    assert partial.status is CaktoCheckoutStatus.PARTIAL
    assert partial.expected_count == 2
    assert partial.configured_count == 1
    assert partial.items[0].checkout_url == "https://pay.cakto.com.br/offer-1"

    second = CaktoPlanBinding(
        external_product_id="product-1",
        external_offer_id="offer-2",
        plan_id="nfcore-pro",
        entitlement_ids=("portal", "fiscal-core"),
    )
    service.set_binding(actor=_actor(), binding=second)

    configured = service.project(pricing)
    assert configured.status is CaktoCheckoutStatus.CONFIGURED
    assert configured.expected_count == 2
    assert configured.configured_count == 2
    assert service.bindings(actor=_actor()) == (first, second)


def test_checkout_projection_rejects_plan_mismatch_and_disabled_binding(
    tmp_path: Path,
) -> None:
    database = _database(tmp_path)
    service = CaktoCheckoutAdministrationService(database)
    pricing = _configuration("cakto://product-1/offer-1")

    service.set_binding(
        actor=_actor(),
        binding=CaktoPlanBinding(
            external_product_id="product-1",
            external_offer_id="offer-1",
            plan_id="other-plan",
            entitlement_ids=("portal",),
        ),
    )
    mismatch = service.project(pricing)
    assert mismatch.status is CaktoCheckoutStatus.UNCONFIGURED

    service.set_binding(
        actor=_actor(),
        binding=CaktoPlanBinding(
            external_product_id="product-1",
            external_offer_id="offer-1",
            plan_id="nfcore-pro",
            entitlement_ids=("portal",),
            enabled=False,
        ),
    )
    disabled = service.project(pricing)
    assert disabled.status is CaktoCheckoutStatus.UNCONFIGURED


def test_checkout_binding_write_requires_global_platform_authority(
    tmp_path: Path,
) -> None:
    service = CaktoCheckoutAdministrationService(_database(tmp_path))
    binding = CaktoPlanBinding(
        external_product_id="product-1",
        external_offer_id="offer-1",
        plan_id="nfcore-pro",
        entitlement_ids=("portal",),
    )

    with pytest.raises(ControlPlaneAuthorizationError, match="global"):
        service.set_binding(actor=_actor(global_scope=False), binding=binding)
