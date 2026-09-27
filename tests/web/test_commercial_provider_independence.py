from __future__ import annotations

from decimal import Decimal
from inspect import getsource
from typing import cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from kordena_fiscal.control_plane.commercial_release import (
    CommercialReleaseAdministrationService,
    InMemoryCommercialReleaseCatalog,
)
from kordena_fiscal.control_plane.models import (
    AdminPrincipal,
    ControlPlanePermission,
)
from kordena_fiscal.control_plane.pricing_admin import (
    CommercialPricingAdministrationService,
)
from kordena_fiscal.domain import FiscalValidationError
from kordena_fiscal.product.checkout import (
    CommercialCheckoutItem,
    CommercialCheckoutProjection,
    CommercialCheckoutStatus,
)
from kordena_fiscal.product.commercial_release import (
    CommercialReleaseDecision,
    CommercialReleaseStatus,
)
from kordena_fiscal.product.pricing import (
    BillingCadence,
    CommercialPricingConfiguration,
    CommercialPricingRegistry,
    PlanDefinition,
    PriceDefinition,
)
from kordena_fiscal.security.human_identity import HumanIdentityService
from kordena_fiscal.web import commercial_release as commercial_release_module
from kordena_fiscal.web.commercial_release import create_commercial_release_router


class SyntheticExternalCheckout:
    provider_id = "hotmart"

    def project(
        self,
        pricing: CommercialPricingConfiguration | None,
    ) -> CommercialCheckoutProjection:
        assert pricing is not None
        return CommercialCheckoutProjection(
            status=CommercialCheckoutStatus.CONFIGURED,
            provider=self.provider_id,
            expected_count=1,
            configured_count=1,
            items=(
                CommercialCheckoutItem(
                    plan_id="nfcore-pro",
                    price_id="nfcore-monthly",
                    provider=self.provider_id,
                    checkout_url="https://pay.hotmart.com/example?src=nfcore",
                ),
            ),
        )


def _platform_admin() -> AdminPrincipal:
    return AdminPrincipal(
        actor_id="platform-admin",
        permissions=frozenset({ControlPlanePermission.COMMERCIAL_CONFIG_WRITE}),
        global_scope=True,
    )


def _pricing() -> CommercialPricingConfiguration:
    price = PriceDefinition(
        price_id="nfcore-monthly",
        currency="BRL",
        cadence=BillingCadence.MONTHLY,
        base_amount=Decimal("199.00"),
        external_price_reference="hotmart://nfcore-pro/monthly",
    )
    return CommercialPricingConfiguration(
        configuration_id="provider-neutral-checkout",
        version=1,
        prices=(price,),
        plans=(
            PlanDefinition(
                plan_id="nfcore-pro",
                display_name="NFCore Pro",
                edition_id="pro",
                price_ids=(price.price_id,),
            ),
        ),
    )


def test_canonical_commercial_offer_has_no_cakto_dependency() -> None:
    source = getsource(commercial_release_module).casefold()
    assert "cakto" not in source


def test_non_cakto_checkout_can_enable_canonical_public_purchase() -> None:
    actor = _platform_admin()
    pricing = CommercialPricingAdministrationService(CommercialPricingRegistry())
    release = CommercialReleaseAdministrationService(
        InMemoryCommercialReleaseCatalog()
    )
    pricing.publish(
        actor=actor,
        configuration=_pricing(),
        expected_version=None,
        correlation_id="provider-neutral-pricing",
    )
    release.publish(
        actor=actor,
        decision=CommercialReleaseDecision(
            version=1,
            status=CommercialReleaseStatus.COMMERCIAL_APPROVED,
            human_decision_reference="human-provider-neutral-release",
        ),
        expected_version=None,
        correlation_id="provider-neutral-release",
    )

    app = FastAPI()
    app.include_router(
        create_commercial_release_router(
            cast(HumanIdentityService, object()),
            pricing,
            release,
            SyntheticExternalCheckout(),
            checkout_processing_configured=True,
        )
    )

    response = TestClient(app).get("/v1/commercial/offer")
    assert response.status_code == 200
    body = response.json()
    assert body["purchase_enabled"] is True
    assert body["checkout"]["provider"] == "hotmart"
    assert body["checkout"]["processing_status"] == "configured"
    assert body["checkout"]["items"] == [
        {
            "plan_id": "nfcore-pro",
            "price_id": "nfcore-monthly",
            "provider": "hotmart",
            "checkout_url": "https://pay.hotmart.com/example?src=nfcore",
        }
    ]


def test_checkout_projection_rejects_status_count_mismatch() -> None:
    with pytest.raises(FiscalValidationError, match="status is inconsistent"):
        CommercialCheckoutProjection(
            status=CommercialCheckoutStatus.CONFIGURED,
            provider="hotmart",
            expected_count=1,
            configured_count=0,
            items=(),
        )
