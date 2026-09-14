from datetime import datetime, timezone
from decimal import Decimal

import pytest

from kordena_fiscal.product.pricing import (
    BillingCadence,
    CommercialPricingConfiguration,
    CommercialPricingError,
    CommercialPricingRegistry,
    DiscountKind,
    PriceDefinition,
    PromotionDefinition,
    TenantPriceOverride,
)

NOW = datetime(2026, 9, 14, 3, 0, tzinfo=timezone.utc)


def _configuration(*, version: int = 1) -> CommercialPricingConfiguration:
    return CommercialPricingConfiguration.from_mapping(
        {
            "configuration_id": "fm-fiscal-commercial",
            "version": version,
            "prices": [
                {
                    "price_id": "growth-monthly",
                    "currency": "BRL",
                    "cadence": "monthly",
                    "base_amount": "249.90",
                    "per_document_amount": "0.15",
                    "setup_amount": "0",
                    "external_price_reference": "gateway://prices/growth-monthly",
                },
                {
                    "price_id": "growth-annual",
                    "currency": "BRL",
                    "cadence": "annual",
                    "base_amount": "2399.00",
                },
                {
                    "price_id": "launch-package",
                    "currency": "BRL",
                    "cadence": "monthly",
                    "base_amount": "299.90",
                },
                {
                    "price_id": "priority-support",
                    "currency": "BRL",
                    "cadence": "monthly",
                    "base_amount": "79.90",
                },
            ],
            "plans": [
                {
                    "plan_id": "growth",
                    "display_name": "Growth",
                    "edition_id": "growth",
                    "price_ids": ["growth-monthly", "growth-annual"],
                    "trial_days": 14,
                    "tags": ["public", "recommended"],
                }
            ],
            "add_ons": [
                {
                    "add_on_id": "priority-support",
                    "display_name": "Priority Support",
                    "price_ids": ["priority-support"],
                    "entitlement_ids": ["support.premium"],
                }
            ],
            "packages": [
                {
                    "package_id": "launch",
                    "display_name": "Launch Package",
                    "plan_id": "growth",
                    "add_on_ids": ["priority-support"],
                    "price_ids": ["launch-package"],
                }
            ],
            "promotions": [
                {
                    "promotion_id": "launch-20",
                    "display_name": "Lançamento 20%",
                    "kind": "percentage",
                    "value": "20",
                    "eligible_price_ids": ["growth-monthly"],
                    "starts_at": "2026-09-01T00:00:00+00:00",
                    "ends_at": "2026-10-01T00:00:00+00:00",
                    "coupon_code": "LANCAMENTO20",
                },
                {
                    "promotion_id": "trial-plus-7",
                    "display_name": "Trial extra",
                    "kind": "free_days",
                    "value": "7",
                    "eligible_price_ids": ["growth-annual"],
                    "stackable": True,
                },
            ],
            "tenant_overrides": [
                {
                    "override_id": "enterprise-negotiated",
                    "tenant_id": "tenant-enterprise",
                    "price_id": "growth-monthly",
                    "base_amount": "199.90",
                    "contract_reference": "contract://tenant-enterprise/2026",
                }
            ],
        }
    )


def test_price_catalog_supports_plans_packages_addons_and_promotions() -> None:
    configuration = _configuration()

    assert configuration.version == 1
    assert configuration.plans[0].trial_days == 14
    assert configuration.packages[0].plan_id == "growth"
    assert configuration.add_ons[0].entitlement_ids == ("support.premium",)
    assert configuration.promotions[0].kind is DiscountKind.PERCENTAGE


def test_promotion_changes_price_without_code_change() -> None:
    configuration = _configuration()

    resolved = configuration.resolve_price(
        "growth-monthly",
        at=NOW,
        coupon_code="lancamento20",
    )

    assert resolved.base_amount == Decimal("199.92")
    assert resolved.per_document_amount == Decimal("0.12")
    assert resolved.applied_promotion_ids == ("launch-20",)


def test_tenant_override_and_promotion_can_be_resolved_from_configuration() -> None:
    configuration = _configuration()

    resolved = configuration.resolve_price(
        "growth-monthly",
        at=NOW,
        tenant_id="tenant-enterprise",
        coupon_code="LANCAMENTO20",
    )

    assert resolved.base_amount == Decimal("159.92")
    assert resolved.applied_override_id == "enterprise-negotiated"
    assert resolved.applied_promotion_ids == ("launch-20",)


def test_free_days_promotion_does_not_mutate_money() -> None:
    configuration = _configuration()

    resolved = configuration.resolve_price("growth-annual", at=NOW)

    assert resolved.base_amount == Decimal("2399.00")
    assert resolved.bonus_trial_days == 7


def test_registry_replaces_catalog_with_optimistic_versioning() -> None:
    registry = CommercialPricingRegistry()
    first = _configuration(version=1)
    second = _configuration(version=2)

    registry.publish(first, expected_version=None)
    registry.publish(second, expected_version=1)

    assert registry.current is second


def test_registry_rejects_stale_price_changes() -> None:
    registry = CommercialPricingRegistry()
    registry.publish(_configuration(version=1), expected_version=None)

    with pytest.raises(CommercialPricingError, match="version conflict"):
        registry.publish(_configuration(version=2), expected_version=0)


def test_configuration_rejects_unknown_package_references() -> None:
    with pytest.raises(CommercialPricingError, match="unknown plan"):
        CommercialPricingConfiguration.from_mapping(
            {
                "configuration_id": "broken",
                "version": 1,
                "prices": [
                    {
                        "price_id": "package",
                        "currency": "BRL",
                        "cadence": "monthly",
                        "base_amount": "100",
                    }
                ],
                "plans": [],
                "packages": [
                    {
                        "package_id": "broken-package",
                        "display_name": "Broken",
                        "plan_id": "missing-plan",
                        "add_on_ids": [],
                        "price_ids": ["package"],
                    }
                ],
            }
        )


def test_non_stackable_promotions_cannot_conflict() -> None:
    price = PriceDefinition(
        price_id="basic",
        currency="BRL",
        cadence=BillingCadence.MONTHLY,
        base_amount=Decimal("100"),
    )
    promotion_a = PromotionDefinition(
        promotion_id="a",
        display_name="A",
        kind=DiscountKind.PERCENTAGE,
        value=Decimal("10"),
        eligible_price_ids=("basic",),
    )
    promotion_b = PromotionDefinition(
        promotion_id="b",
        display_name="B",
        kind=DiscountKind.FIXED_AMOUNT,
        value=Decimal("5"),
        eligible_price_ids=("basic",),
    )
    configuration = CommercialPricingConfiguration(
        configuration_id="conflict",
        version=1,
        prices=(price,),
        plans=(),
        promotions=(promotion_a, promotion_b),
    )

    with pytest.raises(CommercialPricingError, match="multiple non-stackable"):
        configuration.resolve_price("basic", at=NOW)


def test_tenant_override_requires_an_amount_change() -> None:
    with pytest.raises(CommercialPricingError, match="replace at least one amount"):
        TenantPriceOverride(
            override_id="empty",
            tenant_id="tenant",
            price_id="price",
        )
