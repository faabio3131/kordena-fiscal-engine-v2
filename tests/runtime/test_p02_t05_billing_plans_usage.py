from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import psycopg
import pytest
from fastapi.testclient import TestClient

from kordena_fiscal.control_plane.models import (
    AdminPrincipal,
    ControlPlanePermission,
    FiscalOrganization,
)
from kordena_fiscal.persistence.commercial_fulfillment import (
    postgres_canonical_commercial_database,
)
from kordena_fiscal.persistence.postgres import PostgresFiscalDatabase
from kordena_fiscal.product.billing import (
    CommercialPlan,
    CommercialSubscription,
    SubscriptionStatus,
    UsageQuota,
)
from kordena_fiscal.product.commercial_fulfillment import (
    CommercialPurchaseRecord,
    CommercialPurchaseState,
    DurableCommercialSubscription,
)
from kordena_fiscal.product.pricing import (
    BillingCadence,
    CommercialPricingConfiguration,
    PlanDefinition,
    PriceDefinition,
)
from kordena_fiscal.runtime.composition import build_postgres_runtime_composition
from kordena_fiscal.security.human_identity import (
    HumanAccount,
    PortalRole,
    ScryptPasswordHasher,
)
from kordena_fiscal.web import create_app

DSN_ENV = "NFCORE_TEST_POSTGRES_DSN"
NOW = datetime(2026, 10, 7, 19, 0, tzinfo=UTC)
PASSWORD = "billing-surface-password-2026"


def _dsn() -> str:
    value = os.environ.get(DSN_ENV, "").strip()
    if not value:
        pytest.skip(f"{DSN_ENV} is required for PostgreSQL T05 certification")
    return value


@pytest.fixture
def database() -> PostgresFiscalDatabase:
    dsn = _dsn()
    with psycopg.connect(dsn, autocommit=True) as connection:
        connection.execute("DROP SCHEMA public CASCADE")
        connection.execute("CREATE SCHEMA public")
    database = PostgresFiscalDatabase(dsn)
    database.initialize()
    try:
        yield database
    finally:
        database.close()


def _human(
    name: str,
    role: PortalRole,
    hasher: ScryptPasswordHasher,
    *,
    tenant_id: str = "tenant-a",
) -> HumanAccount:
    return HumanAccount(
        account_id=f"account-{name}",
        email=f"{name}@example.com",
        password_hash=hasher.hash(PASSWORD),
        tenant_id=tenant_id,
        role=role,
    )


def _seed_commercial_state(database: PostgresFiscalDatabase) -> None:
    with database() as uow:
        uow.control_plane.add_organization(
            FiscalOrganization(tenant_id="tenant-a", legal_name="Tenant A")
        )
        uow.commit()

    hasher = ScryptPasswordHasher()
    accounts = database.human_accounts()
    for role in (
        PortalRole.OWNER,
        PortalRole.ADMIN,
        PortalRole.OPERATOR,
        PortalRole.AUDITOR,
        PortalRole.BILLING,
    ):
        accounts.save(_human(role.value, role, hasher))

    composition = build_postgres_runtime_composition(database)
    composition.pricing_administration.publish(
        actor=AdminPrincipal(
            actor_id="pricing-admin",
            permissions=frozenset({ControlPlanePermission.COMMERCIAL_CONFIG_WRITE}),
            global_scope=True,
        ),
        configuration=CommercialPricingConfiguration(
            configuration_id="t05-pricing",
            version=1,
            prices=(
                PriceDefinition(
                    price_id="growth-monthly",
                    currency="BRL",
                    cadence=BillingCadence.MONTHLY,
                    base_amount=Decimal("199.00"),
                    per_document_amount=Decimal("0.10"),
                ),
            ),
            plans=(
                PlanDefinition(
                    plan_id="growth",
                    display_name="Growth",
                    edition_id="growth",
                    price_ids=("growth-monthly",),
                ),
            ),
        ),
        expected_version=None,
        correlation_id="t05-pricing-v1",
        published_at=NOW,
    )

    purchase = CommercialPurchaseRecord(
        purchase_id="purchase-t05",
        provider_id="adapter-x",
        external_order_id="order-t05",
        plan_id="growth",
        price_id="growth-monthly",
        state=CommercialPurchaseState.ACTIVE,
        created_at=NOW,
        updated_at=NOW,
        last_event_at=NOW,
        last_event_id="event-t05",
        external_subscription_id="external-sub-t05",
        buyer_email="owner@example.com",
        legal_name="Tenant A",
        tenant_id="tenant-a",
        account_id="account-owner",
        billing_status=SubscriptionStatus.ACTIVE,
    )
    subscription = CommercialSubscription(
        tenant_id="tenant-a",
        plan=CommercialPlan(
            plan_id="growth",
            entitlement_ids=("documents.issue",),
            quotas=(UsageQuota("documents", 500),),
        ),
        status=SubscriptionStatus.ACTIVE,
        period_start=NOW,
        period_end=NOW + timedelta(days=30),
    )
    subscription.record_usage("documents", amount=42, at=NOW)
    durable = DurableCommercialSubscription(
        subscription_id="subscription-t05",
        purchase_id=purchase.purchase_id,
        checkpoint=subscription.checkpoint(),
        provider_id="adapter-x",
        external_subscription_id="external-sub-t05",
        last_event_id="event-t05",
        last_event_at=NOW,
    )
    commercial = postgres_canonical_commercial_database(database)
    with commercial() as uow:
        uow.commercial.put_purchase(purchase)
        uow.commercial.put_subscription(durable)
        uow.commit()


def _client(database: PostgresFiscalDatabase, role: PortalRole) -> TestClient:
    composition = build_postgres_runtime_composition(database)
    app = create_app(
        human_identity=composition.human_identity,
        portal_executor=composition.portal_executor,
    )
    http = TestClient(app, base_url="https://nfcore.test")
    response = http.post(
        "/v1/auth/login",
        json={"email": f"{role.value}@example.com", "password": PASSWORD},
    )
    assert response.status_code == 200, response.text
    return http


def test_postgres_portal_exposes_canonical_billing_plans_and_usage_with_existing_rbac(
    database: PostgresFiscalDatabase,
) -> None:
    _seed_commercial_state(database)

    for role in (PortalRole.OWNER, PortalRole.ADMIN, PortalRole.AUDITOR, PortalRole.BILLING):
        http = _client(database, role)
        bootstrap = http.get("/v1/portal/bootstrap")
        assert bootstrap.status_code == 200
        available = set(bootstrap.json()["projection"]["available_surfaces"])
        assert {"billing", "plans", "usage"} <= available

        billing = http.get("/v1/portal/surfaces/billing")
        assert billing.status_code == 200
        billing_row = billing.json()["rows"][0]
        assert billing_row["subscription_id"] == "subscription-t05"
        assert billing_row["status"] == "active"
        assert "provider_id" not in billing_row
        assert "external_subscription_id" not in billing_row

        usage = http.get("/v1/portal/surfaces/usage")
        assert usage.status_code == 200
        assert usage.json()["rows"][0]["used"] == 42
        assert usage.json()["rows"][0]["limit"] == 500

        plans = http.get("/v1/portal/surfaces/plans")
        assert plans.status_code == 200
        plan = plans.json()["rows"][0]
        assert plan["plan_id"] == "growth"
        assert plan["base_amount"] == "199.00"
        assert plan["current"] is True
        assert "external_price_reference" not in plan

    operator = _client(database, PortalRole.OPERATOR)
    bootstrap = operator.get("/v1/portal/bootstrap")
    assert bootstrap.status_code == 200
    available = set(bootstrap.json()["projection"]["available_surfaces"])
    assert not {"billing", "plans", "usage"} & available
    for surface in ("billing", "plans", "usage"):
        assert operator.get(f"/v1/portal/surfaces/{surface}").status_code == 403
