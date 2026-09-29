from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import psycopg
import pytest

from kordena_fiscal.control_plane.models import AdminPrincipal, ControlPlanePermission
from kordena_fiscal.persistence.postgres import PostgresFiscalDatabase
from kordena_fiscal.product.billing import SubscriptionStatus
from kordena_fiscal.product.commercial_fulfillment import CommercialFulfillmentError
from kordena_fiscal.product.pricing import (
    BillingCadence,
    CommercialPricingConfiguration,
    PlanDefinition,
    PriceDefinition,
)
from kordena_fiscal.runtime.composition import build_postgres_runtime_composition
from kordena_fiscal.security.human_identity import PortalRole

DSN_ENV = "NFCORE_TEST_POSTGRES_DSN"
NOW = datetime(2026, 9, 29, 20, 30, tzinfo=UTC)


def _dsn() -> str:
    value = os.environ.get(DSN_ENV, "").strip()
    if not value:
        pytest.skip(f"{DSN_ENV} is required for PostgreSQL trial certification")
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


def _publish_trial_pricing(database: PostgresFiscalDatabase) -> None:
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
            configuration_id="cl12-trial-pricing",
            version=1,
            prices=(price,),
            plans=(
                PlanDefinition(
                    plan_id="growth",
                    display_name="Growth",
                    edition_id="growth",
                    price_ids=(price.price_id,),
                    trial_days=14,
                ),
            ),
        ),
        expected_version=None,
        correlation_id="cl12-trial-pricing",
        published_at=NOW,
    )


def test_trial_provisions_nfcore_identity_owner_temporary_subscription_and_replay(
    database: PostgresFiscalDatabase,
) -> None:
    _publish_trial_pricing(database)
    composition = build_postgres_runtime_composition(database)

    started = composition.commercial_trial.begin(
        plan_id="growth",
        price_id="growth-monthly",
        buyer_email="trial-owner@example.com",
        legal_name="Trial Customer LTDA",
        idempotency_key="cl12-trial-idempotency-0001",
        now=NOW,
    )

    assert started.replay is False
    assert started.purchase.provider_id == "nfcore-trial"
    assert started.purchase.tenant_id is not None
    assert started.purchase.tenant_id.startswith("tenant-")
    assert started.purchase.billing_status is SubscriptionStatus.TRIAL
    assert started.subscription.checkpoint.status is SubscriptionStatus.TRIAL
    assert started.subscription.checkpoint.period_start == NOW
    assert started.subscription.checkpoint.period_end == NOW + timedelta(days=14)
    assert started.activation_reset is not None
    assert started.activation_reset.reset_token not in repr(started)

    owner = database.human_accounts().by_email("trial-owner@example.com")
    assert owner is not None
    assert owner.tenant_id == started.purchase.tenant_id
    assert owner.role is PortalRole.OWNER

    with database.unit_of_work() as uow:
        organization = uow.control_plane.get_organization(started.purchase.tenant_id)
    assert organization is not None
    assert organization.legal_name == "Trial Customer LTDA"

    replay = composition.commercial_trial.begin(
        plan_id="growth",
        price_id="growth-monthly",
        buyer_email="trial-owner@example.com",
        legal_name="Trial Customer LTDA",
        idempotency_key="cl12-trial-idempotency-0001",
        now=NOW + timedelta(minutes=1),
    )
    assert replay.replay is True
    assert replay.purchase.purchase_id == started.purchase.purchase_id
    assert replay.subscription.subscription_id == started.subscription.subscription_id


def test_trial_duplicate_email_different_request_fails_closed(
    database: PostgresFiscalDatabase,
) -> None:
    _publish_trial_pricing(database)
    composition = build_postgres_runtime_composition(database)
    composition.commercial_trial.begin(
        plan_id="growth",
        price_id="growth-monthly",
        buyer_email="duplicate@example.com",
        legal_name="Duplicate Customer LTDA",
        idempotency_key="cl12-trial-idempotency-0002",
        now=NOW,
    )

    with pytest.raises(CommercialFulfillmentError, match="existing account"):
        composition.commercial_trial.begin(
            plan_id="growth",
            price_id="growth-monthly",
            buyer_email="duplicate@example.com",
            legal_name="Duplicate Customer LTDA",
            idempotency_key="cl12-trial-idempotency-0003",
            now=NOW + timedelta(minutes=1),
        )


def test_trial_requires_explicit_trial_days_and_never_grants_fiscal_production(
    database: PostgresFiscalDatabase,
) -> None:
    composition = build_postgres_runtime_composition(database)
    price = PriceDefinition(
        price_id="foundation-monthly",
        currency="BRL",
        cadence=BillingCadence.MONTHLY,
        base_amount=Decimal("99.00"),
    )
    composition.pricing_administration.publish(
        actor=AdminPrincipal(
            actor_id="pricing-admin",
            permissions=frozenset({ControlPlanePermission.COMMERCIAL_CONFIG_WRITE}),
            global_scope=True,
        ),
        configuration=CommercialPricingConfiguration(
            configuration_id="cl12-no-trial",
            version=1,
            prices=(price,),
            plans=(
                PlanDefinition(
                    plan_id="foundation",
                    display_name="Foundation",
                    edition_id="foundation",
                    price_ids=(price.price_id,),
                    trial_days=0,
                ),
            ),
        ),
        expected_version=None,
        correlation_id="cl12-no-trial",
        published_at=NOW,
    )

    with pytest.raises(CommercialFulfillmentError, match="not eligible for trial"):
        composition.commercial_trial.begin(
            plan_id="foundation",
            price_id="foundation-monthly",
            buyer_email="blocked@example.com",
            legal_name="Blocked Trial LTDA",
            idempotency_key="cl12-trial-idempotency-0004",
            now=NOW,
        )

    assert not hasattr(composition.commercial_trial, "production_approved")
    assert not hasattr(composition.commercial_trial, "fiscal_readiness")


def test_trial_expiry_suspends_usage_and_internal_conversion_activates(
    database: PostgresFiscalDatabase,
) -> None:
    _publish_trial_pricing(database)
    composition = build_postgres_runtime_composition(database)

    expiring = composition.commercial_trial.begin(
        plan_id="growth",
        price_id="growth-monthly",
        buyer_email="expire@example.com",
        legal_name="Expire Trial LTDA",
        idempotency_key="cl12-trial-idempotency-0005",
        now=NOW,
    )
    expired = composition.commercial_trial.expire(
        purchase_id=expiring.purchase.purchase_id,
        now=NOW + timedelta(days=14),
    )
    assert expired.checkpoint.status is SubscriptionStatus.SUSPENDED

    converting = composition.commercial_trial.begin(
        plan_id="growth",
        price_id="growth-monthly",
        buyer_email="convert@example.com",
        legal_name="Convert Trial LTDA",
        idempotency_key="cl12-trial-idempotency-0006",
        now=NOW,
    )
    converted = composition.commercial_trial.convert(
        purchase_id=converting.purchase.purchase_id,
        conversion_reference="canonical-paid-event-0001",
        now=NOW + timedelta(days=2),
    )
    assert converted.checkpoint.status is SubscriptionStatus.ACTIVE
