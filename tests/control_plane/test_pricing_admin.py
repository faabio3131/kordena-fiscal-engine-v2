from decimal import Decimal

import pytest

from kordena_fiscal.control_plane.models import AdminPrincipal, ControlPlanePermission
from kordena_fiscal.control_plane.pricing_admin import CommercialPricingAdministrationService
from kordena_fiscal.control_plane.service import ControlPlaneAuthorizationError
from kordena_fiscal.product.pricing import (
    BillingCadence,
    CommercialPricingConfiguration,
    CommercialPricingRegistry,
    PlanDefinition,
    PriceDefinition,
)

TEST_ONLY_AMOUNT = Decimal("123.45")


def _configuration(version: int) -> CommercialPricingConfiguration:
    price = PriceDefinition(
        price_id="synthetic-monthly",
        currency="BRL",
        cadence=BillingCadence.MONTHLY,
        base_amount=TEST_ONLY_AMOUNT,
    )
    plan = PlanDefinition(
        plan_id="synthetic-plan",
        display_name="Synthetic Test Plan",
        edition_id="synthetic",
        price_ids=(price.price_id,),
    )
    return CommercialPricingConfiguration(
        configuration_id="synthetic-admin-test",
        version=version,
        prices=(price,),
        plans=(plan,),
    )


def _platform_admin() -> AdminPrincipal:
    return AdminPrincipal(
        actor_id="fm-platform-pricing-admin",
        permissions=frozenset({ControlPlanePermission.COMMERCIAL_CONFIG_WRITE}),
        global_scope=True,
    )


def test_global_platform_admin_can_publish_pricing_without_code_change() -> None:
    service = CommercialPricingAdministrationService(CommercialPricingRegistry())

    first = service.publish(
        actor=_platform_admin(),
        configuration=_configuration(1),
        expected_version=None,
    )
    second = service.publish(
        actor=_platform_admin(),
        configuration=_configuration(2),
        expected_version=1,
    )

    assert first.version == 1
    assert second.version == 2
    assert service.current is second
    assert second.prices[0].base_amount == TEST_ONLY_AMOUNT


def test_tenant_admin_cannot_change_platform_prices() -> None:
    service = CommercialPricingAdministrationService(CommercialPricingRegistry())
    tenant_admin = AdminPrincipal(
        actor_id="tenant-owner-admin",
        permissions=frozenset({ControlPlanePermission.COMMERCIAL_CONFIG_WRITE}),
        tenant_ids=frozenset({"tenant-a"}),
    )

    with pytest.raises(ControlPlaneAuthorizationError, match="global FM platform administrator"):
        service.publish(
            actor=tenant_admin,
            configuration=_configuration(1),
            expected_version=None,
        )

    assert service.current is None


def test_global_admin_without_commercial_permission_cannot_change_prices() -> None:
    service = CommercialPricingAdministrationService(CommercialPricingRegistry())
    unrelated_admin = AdminPrincipal(
        actor_id="fm-unrelated-admin",
        permissions=frozenset({ControlPlanePermission.AUDIT_READ}),
        global_scope=True,
    )

    with pytest.raises(ControlPlaneAuthorizationError, match="commercial_config.write"):
        service.publish(
            actor=unrelated_admin,
            configuration=_configuration(1),
            expected_version=None,
        )

    assert service.current is None


def test_pricing_admin_keeps_optimistic_version_conflict_protection() -> None:
    service = CommercialPricingAdministrationService(CommercialPricingRegistry())
    service.publish(
        actor=_platform_admin(),
        configuration=_configuration(1),
        expected_version=None,
    )

    with pytest.raises(ValueError, match="version conflict"):
        service.publish(
            actor=_platform_admin(),
            configuration=_configuration(2),
            expected_version=0,
        )
