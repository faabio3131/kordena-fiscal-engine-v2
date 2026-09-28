from __future__ import annotations

import os
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal

import psycopg
import pytest

from kordena_fiscal.control_plane.models import AdminPrincipal, ControlPlanePermission
from kordena_fiscal.persistence.commercial_fulfillment import (
    postgres_canonical_commercial_database,
)
from kordena_fiscal.persistence.postgres import PostgresFiscalDatabase
from kordena_fiscal.product.billing import SubscriptionStatus
from kordena_fiscal.product.catalog import DEFAULT_COMMERCIAL_CATALOG
from kordena_fiscal.product.commercial_fulfillment import (
    CommercialFulfillmentError,
    CommercialPurchaseRecord,
    CommercialPurchaseState,
    commercial_purchase_id,
)
from kordena_fiscal.product.pricing import (
    BillingCadence,
    CommercialPricingConfiguration,
    PlanDefinition,
    PriceDefinition,
)
from kordena_fiscal.runtime.composition import build_postgres_runtime_composition
from kordena_fiscal.security.human_identity import PortalRole

DSN_ENV = "NFCORE_TEST_POSTGRES_DSN"
NOW = datetime(2026, 9, 28, 5, 0, tzinfo=UTC)
AFTER = datetime(2026, 9, 28, 6, 0, tzinfo=UTC)
NEW_PASSWORD = "commercial-owner-password-2026"


def _dsn() -> str:
    value = os.environ.get(DSN_ENV, "").strip()
    if not value:
        pytest.skip(f"{DSN_ENV} is required for PostgreSQL activation certification")
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


def _publish_growth_pricing(database: PostgresFiscalDatabase) -> None:
    composition = build_postgres_runtime_composition(database)
    price = PriceDefinition(
        price_id="growth-monthly",
        currency="BRL",
        cadence=BillingCadence.MONTHLY,
        base_amount=Decimal("199.00"),
    )
    composition.pricing_administration.publish(
        actor=AdminPrincipal(
            actor_id="pricing-admin",
            permissions=frozenset({ControlPlanePermission.COMMERCIAL_CONFIG_WRITE}),
            global_scope=True,
        ),
        configuration=CommercialPricingConfiguration(
            configuration_id="cl11-activation-pricing",
            version=1,
            prices=(price,),
            plans=(
                PlanDefinition(
                    plan_id="growth",
                    display_name="Growth",
                    edition_id="growth",
                    price_ids=(price.price_id,),
                ),
            ),
        ),
        expected_version=None,
        correlation_id="cl11-activation-pricing",
        published_at=NOW,
    )


def _publish_disabled_growth_pricing_v2(database: PostgresFiscalDatabase) -> None:
    composition = build_postgres_runtime_composition(database)
    price = PriceDefinition(
        price_id="growth-monthly",
        currency="BRL",
        cadence=BillingCadence.ANNUAL,
        base_amount=Decimal("999.00"),
        enabled=False,
    )
    composition.pricing_administration.publish(
        actor=AdminPrincipal(
            actor_id="pricing-admin",
            permissions=frozenset({ControlPlanePermission.COMMERCIAL_CONFIG_WRITE}),
            global_scope=True,
        ),
        configuration=CommercialPricingConfiguration(
            configuration_id="cl11-activation-pricing",
            version=2,
            prices=(price,),
            plans=(
                PlanDefinition(
                    plan_id="growth",
                    display_name="Growth",
                    edition_id="growth",
                    price_ids=(price.price_id,),
                    enabled=False,
                ),
            ),
        ),
        expected_version=1,
        correlation_id="cl11-activation-pricing-v2",
        published_at=AFTER,
    )


def _ready_purchase(database: PostgresFiscalDatabase) -> CommercialPurchaseRecord:
    purchase = CommercialPurchaseRecord(
        purchase_id=commercial_purchase_id("hotmart", "activation-order-1"),
        provider_id="hotmart",
        external_order_id="activation-order-1",
        plan_id="growth",
        price_id="growth-monthly",
        state=CommercialPurchaseState.READY_TO_PROVISION,
        created_at=NOW,
        updated_at=NOW,
        last_event_at=NOW,
        last_event_id="evt-approved",
        external_subscription_id="hotmart-sub-1",
        external_customer_id="hotmart-customer-1",
        buyer_email="owner@activation.example",
        legal_name="Activation Customer LTDA",
        tenant_id="tenant-cl11-activation",
    )
    commercial = postgres_canonical_commercial_database(database)
    with commercial() as uow:
        uow.commercial.put_purchase(purchase)
        uow.commit()
    return purchase


def test_paid_claim_provisions_org_owner_subscription_activation_and_login(
    database: PostgresFiscalDatabase,
) -> None:
    _publish_growth_pricing(database)
    original = _ready_purchase(database)
    composition = build_postgres_runtime_composition(database)

    first = composition.commercial_activation.provision(
        purchase_id=original.purchase_id,
        now=NOW,
    )

    assert first.purchase.state is CommercialPurchaseState.ACTIVATION_PENDING
    assert first.purchase.tenant_id == original.tenant_id
    assert first.purchase.account_id is not None
    assert first.activation_reset.reset_token not in repr(first)

    expected_entitlements = DEFAULT_COMMERCIAL_CATALOG.edition("growth").entitlement_ids
    assert first.subscription.checkpoint.plan.entitlement_ids == expected_entitlements
    assert first.subscription.checkpoint.status is SubscriptionStatus.ACTIVE
    assert first.subscription.checkpoint.tenant_id == original.tenant_id

    with database.unit_of_work() as uow:
        organization = uow.control_plane.get_organization(original.tenant_id or "")
    assert organization is not None
    assert organization.legal_name == "Activation Customer LTDA"

    owner = database.human_accounts().by_email("owner@activation.example")
    assert owner is not None
    assert owner.tenant_id == original.tenant_id
    assert owner.role is PortalRole.OWNER

    repeated = composition.commercial_activation.provision(
        purchase_id=original.purchase_id,
        now=NOW,
    )
    assert repeated.purchase.account_id == first.purchase.account_id
    assert repeated.subscription.subscription_id == first.subscription.subscription_id
    assert repeated.activation_reset.reset_token != first.activation_reset.reset_token

    account_id = composition.password_recovery.complete_reset(
        reset_token=repeated.activation_reset.reset_token,
        new_password=NEW_PASSWORD,
        now=NOW,
    )
    activated = composition.commercial_activation.mark_active(
        account_id=account_id,
        now=NOW,
    )
    assert activated is not None
    assert activated.state is CommercialPurchaseState.ACTIVE

    session = composition.human_identity.login(
        email="owner@activation.example",
        password=NEW_PASSWORD,
        now=NOW,
    )
    assert session.account.account_id == account_id
    assert session.account.tenant_id == original.tenant_id


def test_activation_fails_closed_without_published_pricing_before_provisioning(
    database: PostgresFiscalDatabase,
) -> None:
    original = _ready_purchase(database)
    composition = build_postgres_runtime_composition(database)

    with pytest.raises(CommercialFulfillmentError, match="pricing is not published"):
        composition.commercial_activation.provision(
            purchase_id=original.purchase_id,
            now=NOW,
        )

    assert database.human_accounts().by_email("owner@activation.example") is None
    with database.unit_of_work() as uow:
        assert uow.control_plane.get_organization(original.tenant_id or "") is None


def test_activation_preserves_sale_time_pricing_when_catalog_changes_after_purchase(
    database: PostgresFiscalDatabase,
) -> None:
    _publish_growth_pricing(database)
    original = _ready_purchase(database)
    _publish_disabled_growth_pricing_v2(database)

    commercial = postgres_canonical_commercial_database(database)
    with commercial() as uow:
        uow.commercial.put_purchase(
            replace(
                original,
                updated_at=AFTER,
                last_event_at=AFTER,
                last_event_id="evt-renewed-after-pricing-change",
            )
        )
        uow.commit()

    composition = build_postgres_runtime_composition(database)
    activated = composition.commercial_activation.provision(
        purchase_id=original.purchase_id,
        now=AFTER,
    )

    assert activated.purchase.state is CommercialPurchaseState.ACTIVATION_PENDING
    assert activated.subscription.checkpoint.plan.plan_id == "growth"
    assert activated.subscription.checkpoint.period_start == AFTER
    assert activated.subscription.checkpoint.period_end.month == 10
    assert activated.subscription.checkpoint.period_end.year == 2026
