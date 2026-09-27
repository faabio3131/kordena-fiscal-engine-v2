from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import timedelta
from typing import Any
from decimal import Decimal

from fastapi.testclient import TestClient

from kordena_fiscal.control_plane.pricing_admin import CommercialPricingAdministrationService
from kordena_fiscal.product.pricing import (
    BillingCadence,
    CommercialPricingConfiguration,
    CommercialPricingRegistry,
    PlanDefinition,
    PriceDefinition,
    TenantPriceOverride,
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

PASSWORD = "platform-admin-password-2026"


class PricingPortalExecutor:
    def snapshot(self, *, authority: object) -> Mapping[str, Any]:
        del authority
        return {"available_surfaces": ["overview", "plans"]}

    def surface(
        self,
        *,
        surface_id: str,
        authority: object,
    ) -> Sequence[Mapping[str, Any]]:
        del surface_id, authority
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


def _configuration(version: int) -> CommercialPricingConfiguration:
    price = PriceDefinition(
        price_id="synthetic-monthly",
        currency="BRL",
        cadence=BillingCadence.MONTHLY,
        base_amount=Decimal("123.45"),
        external_price_reference="synthetic-external-ref",
    )
    return CommercialPricingConfiguration(
        configuration_id="synthetic-web-pricing",
        version=version,
        prices=(price,),
        plans=(
            PlanDefinition(
                plan_id="synthetic-plan",
                display_name="Synthetic Plan",
                edition_id="synthetic",
                price_ids=(price.price_id,),
            ),
        ),
        tenant_overrides=(
            TenantPriceOverride(
                override_id="private-tenant-override",
                tenant_id="tenant-private",
                price_id=price.price_id,
                base_amount=Decimal("99.99"),
            ),
        ),
    )


def _client(*, platform_admin: bool) -> TestClient:
    hasher = ScryptPasswordHasher()
    account = HumanAccount(
        account_id="platform-admin" if platform_admin else "tenant-owner",
        email="platform@example.com" if platform_admin else "owner@example.com",
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
    return TestClient(
        create_app(
            human_identity=identity,
            portal_executor=PricingPortalExecutor(),
            pricing_administration=pricing,
        ),
        base_url="https://nfcore.test",
    )


def _login(web: TestClient, *, platform_admin: bool) -> None:
    response = web.post(
        "/v1/auth/login",
        json={
            "email": "platform@example.com" if platform_admin else "owner@example.com",
            "password": PASSWORD,
        },
    )
    assert response.status_code == 200
    assert response.json()["account"]["platform_admin"] is platform_admin


def test_public_pricing_supports_intentionally_unpriced_state() -> None:
    web = _client(platform_admin=False)

    response = web.get("/v1/commercial/pricing")

    assert response.status_code == 200
    assert response.json() == {
        "status": "unpriced",
        "catalog": None,
        "message": "Commercial pricing has not been published yet",
    }


def test_tenant_owner_cannot_access_platform_pricing_admin() -> None:
    web = _client(platform_admin=False)
    _login(web, platform_admin=False)

    response = web.get("/v1/admin/pricing")

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "PLATFORM_ADMIN_REQUIRED"


def test_platform_admin_publish_requires_csrf_and_exposes_sanitized_public_catalog() -> None:
    web = _client(platform_admin=True)
    _login(web, platform_admin=True)
    configuration = _configuration(1)

    without_csrf = web.post(
        "/v1/admin/pricing",
        json={"configuration": configuration.to_mapping(), "expected_version": None},
    )
    assert without_csrf.status_code == 403

    csrf = web.cookies.get(CSRF_COOKIE)
    assert csrf
    published = web.post(
        "/v1/admin/pricing",
        headers={CSRF_HEADER: csrf, "X-Correlation-Id": "pricing-web-test"},
        json={"configuration": configuration.to_mapping(), "expected_version": None},
    )
    assert published.status_code == 200
    assert published.json()["catalog"]["version"] == 1

    admin = web.get("/v1/admin/pricing")
    assert admin.status_code == 200
    assert admin.json()["history"][0]["actor_id"] == "platform-admin"
    assert admin.json()["history"][0]["correlation_id"] == "pricing-web-test"

    public = web.get("/v1/commercial/pricing")
    assert public.status_code == 200
    body = public.json()
    assert body["status"] == "published"
    assert body["catalog"]["version"] == 1
    assert body["catalog"]["prices"][0]["base_amount"] == "123.45"
    rendered = str(body)
    assert "private-tenant-override" not in rendered
    assert "tenant-private" not in rendered
    assert "synthetic-external-ref" not in rendered


def test_platform_admin_version_conflict_is_fail_closed() -> None:
    web = _client(platform_admin=True)
    _login(web, platform_admin=True)
    csrf = web.cookies.get(CSRF_COOKIE)
    assert csrf
    first = _configuration(1)
    assert web.post(
        "/v1/admin/pricing",
        headers={CSRF_HEADER: csrf},
        json={"configuration": first.to_mapping(), "expected_version": None},
    ).status_code == 200

    conflict = web.post(
        "/v1/admin/pricing",
        headers={CSRF_HEADER: csrf},
        json={"configuration": _configuration(2).to_mapping(), "expected_version": 0},
    )
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "PRICING_PUBLICATION_REJECTED"


def test_portal_bootstrap_exposes_pricing_workspace_only_to_platform_admin() -> None:
    tenant = _client(platform_admin=False)
    _login(tenant, platform_admin=False)
    tenant_bootstrap = tenant.get("/v1/portal/bootstrap")
    assert tenant_bootstrap.status_code == 200
    assert tenant_bootstrap.json()["platform_admin"] is False
    assert "pricing-admin" not in tenant_bootstrap.json()["projection"]["available_surfaces"]

    platform = _client(platform_admin=True)
    _login(platform, platform_admin=True)
    platform_bootstrap = platform.get("/v1/portal/bootstrap")
    assert platform_bootstrap.status_code == 200
    assert platform_bootstrap.json()["platform_admin"] is True
    assert "pricing-admin" in platform_bootstrap.json()["projection"]["available_surfaces"]
