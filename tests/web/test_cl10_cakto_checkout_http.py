from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from kordena_fiscal.control_plane.cakto_checkout import (
    CaktoCheckoutAdministrationService,
)
from kordena_fiscal.control_plane.commercial_release import (
    CommercialReleaseAdministrationService,
    InMemoryCommercialReleaseCatalog,
)
from kordena_fiscal.control_plane.pricing_admin import (
    CommercialPricingAdministrationService,
)
from kordena_fiscal.persistence.cakto import SqliteCaktoCommercialDatabase
from kordena_fiscal.product.commercial_readiness import CommercialDeliveryPathReadiness
from kordena_fiscal.product.pricing import (
    BillingCadence,
    CommercialPricingConfiguration,
    CommercialPricingRegistry,
    PlanDefinition,
    PriceDefinition,
)
from kordena_fiscal.security.human_identity import (
    HumanAccount,
    HumanIdentityService,
    InMemoryHumanAccountRepository,
    InMemoryWebSessionRepository,
    PortalRole,
    ScryptPasswordHasher,
)
from kordena_fiscal.web import create_app
from kordena_fiscal.web.human_auth import CSRF_COOKIE, CSRF_HEADER

PASSWORD = "checkout-admin-password-2026"


FULL_DELIVERY_READINESS = CommercialDeliveryPathReadiness(
    canonical_commercial_persistence=True,
    fulfillment=True,
    provisioning=True,
    activation_delivery=True,
)


class CheckoutPortalExecutor:
    def snapshot(self, *, authority: object) -> Mapping[str, Any]:
        del authority
        return {"available_surfaces": ["overview", "plans"]}

    def surface(
        self,
        *,
        surface_id: str,
        authority: object,
        unit_id: str | None = None,
        environment: object = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[Mapping[str, Any]]:
        del surface_id, authority, unit_id, environment, limit, offset
        return ()

    def execute(
        self,
        *,
        operation_id: str,
        authority: object,
        payload: Mapping[str, Any],
        idempotency_key: str | None,
    ) -> Mapping[str, Any]:
        del operation_id, authority, payload, idempotency_key
        return {}


def _configuration() -> CommercialPricingConfiguration:
    price = PriceDefinition(
        price_id="nfcore-monthly",
        currency="BRL",
        cadence=BillingCadence.MONTHLY,
        base_amount=Decimal("123.45"),
        external_price_reference="cakto://product-nfcore/offer-monthly",
    )
    return CommercialPricingConfiguration(
        configuration_id="nfcore-checkout-web",
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


def _client(
    tmp_path: Path,
    *,
    platform_admin: bool,
    processing_configured: bool,
    delivery_readiness: CommercialDeliveryPathReadiness | None = None,
) -> TestClient:
    hasher = ScryptPasswordHasher()
    account = HumanAccount(
        account_id="checkout-admin" if platform_admin else "tenant-owner",
        email="checkout@example.com" if platform_admin else "owner@example.com",
        password_hash=hasher.hash(PASSWORD),
        tenant_id="fm-platform" if platform_admin else "tenant-a",
        role=PortalRole.OWNER,
        platform_admin=platform_admin,
    )
    identity = HumanIdentityService(
        accounts=InMemoryHumanAccountRepository((account,)),
        sessions=InMemoryWebSessionRepository(),
        password_hasher=hasher,
        session_ttl=timedelta(hours=8),
    )
    pricing = CommercialPricingAdministrationService(CommercialPricingRegistry())
    release = CommercialReleaseAdministrationService(
        InMemoryCommercialReleaseCatalog()
    )
    cakto = SqliteCaktoCommercialDatabase(tmp_path / "checkout-http.sqlite3")
    cakto.initialize()
    checkout = CaktoCheckoutAdministrationService(cakto)
    return TestClient(
        create_app(
            human_identity=identity,
            portal_executor=CheckoutPortalExecutor(),
            pricing_administration=pricing,
            commercial_release_administration=release,
            commercial_checkout=checkout,
            commercial_checkout_processing_configured=processing_configured,
            commercial_delivery_readiness=delivery_readiness,
            cakto_checkout_administration=checkout,
        ),
        base_url="https://nfcore.test",
    )


def _login(web: TestClient, *, platform_admin: bool) -> str:
    response = web.post(
        "/v1/auth/login",
        json={
            "email": "checkout@example.com" if platform_admin else "owner@example.com",
            "password": PASSWORD,
        },
    )
    assert response.status_code == 200
    csrf = web.cookies.get(CSRF_COOKIE)
    assert csrf
    return csrf


def _publish_pricing(web: TestClient, csrf: str) -> None:
    response = web.post(
        "/v1/admin/pricing",
        headers={CSRF_HEADER: csrf},
        json={
            "configuration": _configuration().to_mapping(),
            "expected_version": None,
        },
    )
    assert response.status_code == 200


def _approve_release(web: TestClient, csrf: str) -> None:
    response = web.post(
        "/v1/admin/commercial-release",
        headers={CSRF_HEADER: csrf},
        json={
            "decision": {
                "version": 1,
                "status": "commercial_approved",
                "public_message": "Oferta sintética aprovada.",
                "human_decision_reference": "synthetic-human-release-evidence",
            },
            "expected_version": None,
        },
    )
    assert response.status_code == 200


def _configure_checkout(web: TestClient, csrf: str) -> None:
    response = web.post(
        "/v1/admin/checkout/cakto",
        headers={CSRF_HEADER: csrf},
        json={
            "external_product_id": "product-nfcore",
            "external_offer_id": "offer-monthly",
            "plan_id": "nfcore-pro",
            "entitlement_ids": ["portal", "fiscal-core"],
            "enabled": True,
        },
    )
    assert response.status_code == 200


def _configure_ready_offer(web: TestClient, csrf: str) -> None:
    _publish_pricing(web, csrf)
    _approve_release(web, csrf)
    _configure_checkout(web, csrf)


def test_tenant_owner_cannot_read_or_write_platform_checkout(
    tmp_path: Path,
) -> None:
    web = _client(
        tmp_path,
        platform_admin=False,
        processing_configured=False,
        delivery_readiness=FULL_DELIVERY_READINESS,
    )
    csrf = _login(web, platform_admin=False)

    assert web.get("/v1/admin/checkout/cakto").status_code == 403
    rejected = web.post(
        "/v1/admin/checkout/cakto",
        headers={CSRF_HEADER: csrf},
        json={
            "external_product_id": "product",
            "external_offer_id": "offer",
            "plan_id": "plan",
            "entitlement_ids": ["portal"],
            "enabled": True,
        },
    )
    assert rejected.status_code == 403


def test_checkout_write_requires_csrf_and_portal_surface_is_platform_only(
    tmp_path: Path,
) -> None:
    web = _client(
        tmp_path,
        platform_admin=True,
        processing_configured=False,
    )
    _login(web, platform_admin=True)

    without_csrf = web.post(
        "/v1/admin/checkout/cakto",
        json={
            "external_product_id": "product",
            "external_offer_id": "offer",
            "plan_id": "plan",
            "entitlement_ids": ["portal"],
            "enabled": True,
        },
    )
    assert without_csrf.status_code == 403

    bootstrap = web.get("/v1/portal/bootstrap")
    assert bootstrap.status_code == 200
    assert "checkout-admin" in bootstrap.json()["projection"]["available_surfaces"]


def test_complete_mapping_stays_blocked_when_cakto_processing_is_not_composed(
    tmp_path: Path,
) -> None:
    web = _client(
        tmp_path,
        platform_admin=True,
        processing_configured=False,
        delivery_readiness=FULL_DELIVERY_READINESS,
    )
    csrf = _login(web, platform_admin=True)
    _configure_ready_offer(web, csrf)

    public = web.get("/v1/commercial/offer")
    assert public.status_code == 200
    body = public.json()

    assert body["pricing"]["status"] == "published"
    assert body["release"]["commercially_approved"] is True
    assert body["checkout"]["status"] == "configured"
    assert body["checkout"]["processing_status"] == "unconfigured"
    assert body["checkout"]["items"] == [
        {
            "plan_id": "nfcore-pro",
            "price_id": "nfcore-monthly",
            "provider": "cakto",
            "checkout_url": None,
        }
    ]
    assert body["purchase_enabled"] is False
    assert body["trial_enabled"] is False
    assert "external_price_reference" not in str(body["pricing"])


def test_missing_pricing_blocks_purchase_with_other_dependencies_ready(
    tmp_path: Path,
) -> None:
    web = _client(
        tmp_path,
        platform_admin=True,
        processing_configured=True,
        delivery_readiness=FULL_DELIVERY_READINESS,
    )
    csrf = _login(web, platform_admin=True)
    _approve_release(web, csrf)
    _configure_checkout(web, csrf)

    body = web.get("/v1/commercial/offer").json()

    assert body["pricing"]["status"] == "unpriced"
    assert body["purchase_enabled"] is False
    assert body["checkout"]["items"] == []


def test_missing_release_blocks_purchase_with_other_dependencies_ready(
    tmp_path: Path,
) -> None:
    web = _client(
        tmp_path,
        platform_admin=True,
        processing_configured=True,
        delivery_readiness=FULL_DELIVERY_READINESS,
    )
    csrf = _login(web, platform_admin=True)
    _publish_pricing(web, csrf)
    _configure_checkout(web, csrf)

    body = web.get("/v1/commercial/offer").json()

    assert body["pricing"]["status"] == "published"
    assert body["release"]["commercially_approved"] is False
    assert body["checkout"]["status"] == "configured"
    assert body["purchase_enabled"] is False
    assert body["checkout"]["items"][0]["checkout_url"] is None


def test_missing_checkout_mapping_blocks_purchase_with_other_dependencies_ready(
    tmp_path: Path,
) -> None:
    web = _client(
        tmp_path,
        platform_admin=True,
        processing_configured=True,
        delivery_readiness=FULL_DELIVERY_READINESS,
    )
    csrf = _login(web, platform_admin=True)
    _publish_pricing(web, csrf)
    _approve_release(web, csrf)

    body = web.get("/v1/commercial/offer").json()

    assert body["checkout"]["status"] == "unconfigured"
    assert body["purchase_enabled"] is False


@pytest.mark.parametrize(
    ("processing_configured", "delivery_readiness"),
    (
        (False, FULL_DELIVERY_READINESS),
        (
            True,
            CommercialDeliveryPathReadiness(
                canonical_commercial_persistence=False,
                fulfillment=True,
                provisioning=True,
                activation_delivery=True,
            ),
        ),
        (
            True,
            CommercialDeliveryPathReadiness(
                canonical_commercial_persistence=True,
                fulfillment=False,
                provisioning=True,
                activation_delivery=True,
            ),
        ),
        (
            True,
            CommercialDeliveryPathReadiness(
                canonical_commercial_persistence=True,
                fulfillment=True,
                provisioning=False,
                activation_delivery=True,
            ),
        ),
        (
            True,
            CommercialDeliveryPathReadiness(
                canonical_commercial_persistence=True,
                fulfillment=True,
                provisioning=True,
                activation_delivery=False,
            ),
        ),
    ),
)
def test_each_missing_purchase_delivery_dependency_fails_closed(
    tmp_path: Path,
    processing_configured: bool,
    delivery_readiness: CommercialDeliveryPathReadiness,
) -> None:
    web = _client(
        tmp_path,
        platform_admin=True,
        processing_configured=processing_configured,
        delivery_readiness=delivery_readiness,
    )
    csrf = _login(web, platform_admin=True)
    _configure_ready_offer(web, csrf)

    body = web.get("/v1/commercial/offer").json()

    assert body["purchase_enabled"] is False
    assert body["checkout"]["items"][0]["checkout_url"] is None


def test_purchase_is_projected_only_after_release_mapping_and_processing_are_ready(
    tmp_path: Path,
) -> None:
    web = _client(
        tmp_path,
        platform_admin=True,
        processing_configured=True,
        delivery_readiness=FULL_DELIVERY_READINESS,
    )
    csrf = _login(web, platform_admin=True)
    _configure_ready_offer(web, csrf)

    public = web.get("/v1/commercial/offer")
    assert public.status_code == 200
    body = public.json()

    assert body["checkout"]["status"] == "configured"
    assert body["checkout"]["processing_status"] == "configured"
    assert body["purchase_enabled"] is True
    assert body["trial_enabled"] is False
    assert body["checkout"]["items"] == [
        {
            "plan_id": "nfcore-pro",
            "price_id": "nfcore-monthly",
            "provider": "cakto",
            "checkout_url": "https://pay.cakto.com.br/offer-monthly",
        }
    ]

    admin = web.get("/v1/admin/checkout/cakto")
    assert admin.status_code == 200
    assert admin.json()["bindings"][0]["checkout_url"] == (
        "https://pay.cakto.com.br/offer-monthly"
    )
