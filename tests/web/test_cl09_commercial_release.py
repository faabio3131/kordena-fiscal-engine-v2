from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import timedelta
from decimal import Decimal
from typing import Any

from fastapi.testclient import TestClient

from kordena_fiscal.control_plane.commercial_release import (
    CommercialReleaseAdministrationService,
    InMemoryCommercialReleaseCatalog,
)
from kordena_fiscal.control_plane.pricing_admin import (
    CommercialPricingAdministrationService,
)
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

PASSWORD = "commercial-release-password-2026"


class ReleasePortalExecutor:
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
        price_id="nfcore-synthetic-monthly",
        currency="BRL",
        cadence=BillingCadence.MONTHLY,
        base_amount=Decimal("123.45"),
    )
    return CommercialPricingConfiguration(
        configuration_id="nfcore-synthetic-offer",
        version=version,
        prices=(price,),
        plans=(
            PlanDefinition(
                plan_id="nfcore-synthetic-plan",
                display_name="Synthetic NFCore",
                edition_id="synthetic",
                price_ids=(price.price_id,),
            ),
        ),
    )


def _client(*, platform_admin: bool) -> TestClient:
    hasher = ScryptPasswordHasher()
    account = HumanAccount(
        account_id="release-admin" if platform_admin else "tenant-owner",
        email="release@example.com" if platform_admin else "owner@example.com",
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
    return TestClient(
        create_app(
            human_identity=identity,
            portal_executor=ReleasePortalExecutor(),
            pricing_administration=pricing,
            commercial_release_administration=release,
        ),
        base_url="https://nfcore.test",
    )


def _login(web: TestClient, *, platform_admin: bool) -> str:
    response = web.post(
        "/v1/auth/login",
        json={
            "email": "release@example.com" if platform_admin else "owner@example.com",
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
            "configuration": _configuration(1).to_mapping(),
            "expected_version": None,
        },
    )
    assert response.status_code == 200


def test_public_offer_defaults_fail_closed() -> None:
    web = _client(platform_admin=False)

    response = web.get("/v1/commercial/offer")

    assert response.status_code == 200
    assert response.json() == {
        "product_id": "nfcore",
        "pricing": {"status": "unpriced", "catalog": None},
        "release": {
            "status": "unavailable",
            "version": None,
            "public_message": None,
            "commercially_approved": False,
        },
        "checkout": {"status": "unconfigured"},
        "purchase_enabled": False,
        "trial_enabled": False,
    }


def test_tenant_owner_cannot_access_release_admin() -> None:
    web = _client(platform_admin=False)
    _login(web, platform_admin=False)

    response = web.get("/v1/admin/commercial-release")

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "PLATFORM_ADMIN_REQUIRED"


def test_release_mutation_requires_csrf_and_explicit_human_reference_for_approval() -> None:
    web = _client(platform_admin=True)
    csrf = _login(web, platform_admin=True)

    without_csrf = web.post(
        "/v1/admin/commercial-release",
        json={
            "decision": {
                "version": 1,
                "status": "waitlist",
                "public_message": "Cadastro de interesse disponível.",
                "human_decision_reference": None,
            },
            "expected_version": None,
        },
    )
    assert without_csrf.status_code == 403

    missing_human_reference = web.post(
        "/v1/admin/commercial-release",
        headers={CSRF_HEADER: csrf},
        json={
            "decision": {
                "version": 1,
                "status": "commercial_approved",
                "public_message": "Oferta aprovada.",
                "human_decision_reference": None,
            },
            "expected_version": None,
        },
    )
    assert missing_human_reference.status_code == 400
    assert (
        missing_human_reference.json()["detail"]["code"]
        == "COMMERCIAL_RELEASE_REJECTED"
    )


def test_price_and_human_approval_still_do_not_enable_purchase_without_checkout() -> None:
    web = _client(platform_admin=True)
    csrf = _login(web, platform_admin=True)
    _publish_pricing(web, csrf)

    approved = web.post(
        "/v1/admin/commercial-release",
        headers={CSRF_HEADER: csrf, "X-Correlation-Id": "release-human-approval"},
        json={
            "decision": {
                "version": 1,
                "status": "commercial_approved",
                "public_message": "Oferta aprovada para configuração final.",
                "human_decision_reference": "human-go-no-go-2026-09-27",
            },
            "expected_version": None,
        },
    )
    assert approved.status_code == 200

    public = web.get("/v1/commercial/offer")
    assert public.status_code == 200
    body = public.json()
    assert body["pricing"]["status"] == "published"
    assert body["release"]["status"] == "commercial_approved"
    assert body["release"]["commercially_approved"] is True
    assert body["checkout"]["status"] == "unconfigured"
    assert body["purchase_enabled"] is False
    assert body["trial_enabled"] is False

    admin = web.get("/v1/admin/commercial-release")
    assert admin.status_code == 200
    assert admin.json()["history"][0]["actor_id"] == "release-admin"
    assert admin.json()["history"][0]["correlation_id"] == "release-human-approval"


def test_release_version_conflict_is_fail_closed() -> None:
    web = _client(platform_admin=True)
    csrf = _login(web, platform_admin=True)

    first = web.post(
        "/v1/admin/commercial-release",
        headers={CSRF_HEADER: csrf},
        json={
            "decision": {
                "version": 1,
                "status": "waitlist",
                "public_message": None,
                "human_decision_reference": None,
            },
            "expected_version": None,
        },
    )
    assert first.status_code == 200

    conflict = web.post(
        "/v1/admin/commercial-release",
        headers={CSRF_HEADER: csrf},
        json={
            "decision": {
                "version": 2,
                "status": "ready_for_commercial_review",
                "public_message": None,
                "human_decision_reference": None,
            },
            "expected_version": 0,
        },
    )
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "COMMERCIAL_RELEASE_REJECTED"


def test_portal_projects_release_workspace_only_when_mounted_for_platform_admin() -> None:
    tenant = _client(platform_admin=False)
    _login(tenant, platform_admin=False)
    tenant_bootstrap = tenant.get("/v1/portal/bootstrap")
    assert tenant_bootstrap.status_code == 200
    tenant_surfaces = tenant_bootstrap.json()["projection"]["available_surfaces"]
    assert "commercial-release" not in tenant_surfaces

    platform = _client(platform_admin=True)
    _login(platform, platform_admin=True)
    platform_bootstrap = platform.get("/v1/portal/bootstrap")
    assert platform_bootstrap.status_code == 200
    platform_surfaces = platform_bootstrap.json()["projection"]["available_surfaces"]
    assert "pricing-admin" in platform_surfaces
    assert "commercial-release" in platform_surfaces
