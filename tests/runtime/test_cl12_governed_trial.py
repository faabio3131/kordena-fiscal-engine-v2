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


def test_trial_new_request_key_recovers_exact_pending_reservation_without_renewal(
    database: PostgresFiscalDatabase,
) -> None:
    _publish_trial_pricing(database)
    composition = build_postgres_runtime_composition(database)
    first = composition.commercial_trial.begin(
        plan_id="growth",
        price_id="growth-monthly",
        buyer_email="duplicate@example.com",
        legal_name="Duplicate Customer LTDA",
        idempotency_key="cl12-trial-idempotency-0002",
        now=NOW,
    )
    retry = composition.commercial_trial.begin(
        plan_id="growth",
        price_id="growth-monthly",
        buyer_email="duplicate@example.com",
        legal_name="Duplicate Customer LTDA",
        idempotency_key="cl12-trial-idempotency-0003",
        now=NOW + timedelta(minutes=1),
    )
    assert retry.replay is True
    assert retry.purchase.purchase_id == first.purchase.purchase_id
    assert retry.purchase.tenant_id == first.purchase.tenant_id
    assert retry.subscription.subscription_id == first.subscription.subscription_id
    assert retry.expires_at == first.expires_at == NOW + timedelta(days=14)
    assert retry.activation_reset is not None
    assert first.activation_reset is not None
    assert retry.activation_reset.reset_token != first.activation_reset.reset_token
    with database.connection() as conn:
        purchases = conn.execute(
            "SELECT count(*) FROM fm_commercial_purchases "
            "WHERE provider_id = ? AND buyer_email = ?",
            ("nfcore-trial", "duplicate@example.com"),
        ).fetchone()
    assert purchases is not None and purchases[0] == 1


def test_trial_new_request_key_never_changes_existing_company_or_plan(
    database: PostgresFiscalDatabase,
) -> None:
    _publish_trial_pricing(database)
    composition = build_postgres_runtime_composition(database)
    original = composition.commercial_trial.begin(
        plan_id="growth",
        price_id="growth-monthly",
        buyer_email="conflict@example.com",
        legal_name="Canonical Customer LTDA",
        idempotency_key="cl12-trial-original-0001",
        now=NOW,
    )
    for kwargs in (
        {"legal_name": "Other Customer LTDA"},
        {"plan_id": "foundation"},
        {"price_id": "different-monthly"},
    ):
        candidate = dict(
            plan_id="growth",
            price_id="growth-monthly",
            buyer_email="conflict@example.com",
            legal_name="Canonical Customer LTDA",
            idempotency_key="cl12-trial-different-0001",
            now=NOW + timedelta(minutes=1),
        )
        candidate.update(kwargs)
        with pytest.raises(CommercialFulfillmentError):
            composition.commercial_trial.begin(**candidate)
    with database.unit_of_work() as uow:
        org = uow.control_plane.get_organization(original.purchase.tenant_id or "")
    assert org is not None and org.legal_name == "Canonical Customer LTDA"



def test_trial_recovery_denies_foreign_or_elevated_owner_even_with_matching_offer(
    database: PostgresFiscalDatabase,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from dataclasses import replace
    from types import SimpleNamespace

    _publish_trial_pricing(database)
    composition = build_postgres_runtime_composition(database)
    first = composition.commercial_trial.begin(
        plan_id="growth",
        price_id="growth-monthly",
        buyer_email="isolated@example.com",
        legal_name="Isolated Customer LTDA",
        idempotency_key="cl12-trial-isolated-0001",
        now=NOW,
    )
    owner = database.human_accounts().by_email("isolated@example.com")
    assert owner is not None
    assert first.purchase.tenant_id == owner.tenant_id

    for forged in (
        replace(owner, tenant_id="another-tenant"),
        replace(owner, platform_admin=True),
        replace(owner, enabled=False),
    ):
        monkeypatch.setattr(
            composition.commercial_trial,
            "_accounts",
            SimpleNamespace(by_email=lambda _email, forged=forged: forged),
        )
        with pytest.raises(CommercialFulfillmentError):
            composition.commercial_trial.begin(
                plan_id="growth",
                price_id="growth-monthly",
                buyer_email="isolated@example.com",
                legal_name="Isolated Customer LTDA",
                idempotency_key="cl12-trial-isolated-0002",
                now=NOW + timedelta(minutes=1),
            )



def test_trial_recovers_committed_reservation_after_interrupted_provisioning(
    database: PostgresFiscalDatabase,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _publish_trial_pricing(database)
    composition = build_postgres_runtime_composition(database)
    original_provision = composition.commercial_trial._activation.provision

    def interrupted(*, purchase_id: str, now: datetime) -> None:
        del purchase_id, now
        raise RuntimeError("synthetic interrupted after reservation commit")

    monkeypatch.setattr(composition.commercial_trial._activation, "provision", interrupted)
    with pytest.raises(RuntimeError, match="synthetic interrupted"):
        composition.commercial_trial.begin(
            plan_id="growth",
            price_id="growth-monthly",
            buyer_email="interrupted@example.com",
            legal_name="Interrupted Customer LTDA",
            idempotency_key="cl12-trial-interrupted-0001",
            now=NOW,
        )
    monkeypatch.setattr(
        composition.commercial_trial._activation, "provision", original_provision,
    )
    retry = composition.commercial_trial.begin(
        plan_id="growth",
        price_id="growth-monthly",
        buyer_email="interrupted@example.com",
        legal_name="Interrupted Customer LTDA",
        idempotency_key="cl12-trial-interrupted-0002",
        now=NOW + timedelta(minutes=1),
    )
    assert retry.replay is True
    assert retry.purchase.state.value == "activation_pending"
    assert retry.expires_at == NOW + timedelta(days=14)
    assert retry.activation_reset is not None
    with database.connection() as conn:
        purchases = conn.execute(
            "SELECT count(*) FROM fm_commercial_purchases "
            "WHERE provider_id = ? AND buyer_email = ?",
            ("nfcore-trial", "interrupted@example.com"),
        ).fetchone()
    assert purchases is not None and purchases[0] == 1



def test_trial_retries_after_activation_committed_but_http_response_lost(
    database: PostgresFiscalDatabase,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _publish_trial_pricing(database)
    composition = build_postgres_runtime_composition(database)
    actual_provision = composition.commercial_trial._activation.provision
    first_purchase_id: list[str] = []

    def lost_response(*, purchase_id: str, now: datetime) -> None:
        result = actual_provision(purchase_id=purchase_id, now=now)
        first_purchase_id.append(result.purchase.purchase_id)
        raise RuntimeError("synthetic response lost after durable activation")

    monkeypatch.setattr(composition.commercial_trial._activation, "provision", lost_response)
    with pytest.raises(RuntimeError, match="response lost"):
        composition.commercial_trial.begin(
            plan_id="growth", price_id="growth-monthly",
            buyer_email="committed@example.com", legal_name="Committed Customer LTDA",
            idempotency_key="cl12-trial-committed-0001", now=NOW,
        )
    monkeypatch.setattr(
        composition.commercial_trial._activation, "provision", actual_provision,
    )
    recovered = composition.commercial_trial.begin(
        plan_id="growth", price_id="growth-monthly",
        buyer_email="committed@example.com", legal_name="Committed Customer LTDA",
        idempotency_key="cl12-trial-committed-0002",
        now=NOW + timedelta(minutes=1),
    )
    assert recovered.replay is True
    assert recovered.purchase.purchase_id == first_purchase_id[0]
    assert recovered.expires_at == NOW + timedelta(days=14)
    assert recovered.activation_reset is not None
    owner = database.human_accounts().by_email("committed@example.com")
    assert owner is not None
    assert owner.role is PortalRole.OWNER
    assert owner.tenant_id == recovered.purchase.tenant_id
    with database.connection() as conn:
        purchases = conn.execute(
            "SELECT count(*) FROM fm_commercial_purchases "
            "WHERE provider_id = ? AND buyer_email = ?",
            ("nfcore-trial", "committed@example.com"),
        ).fetchone()
    assert purchases is not None and purchases[0] == 1


def test_trial_cannot_restart_after_activation_or_expiry(
    database: PostgresFiscalDatabase,
) -> None:
    _publish_trial_pricing(database)
    composition = build_postgres_runtime_composition(database)
    started = composition.commercial_trial.begin(
        plan_id="growth",
        price_id="growth-monthly",
        buyer_email="closed@example.com",
        legal_name="Closed Customer LTDA",
        idempotency_key="cl12-trial-closed-0001",
        now=NOW,
    )
    assert started.purchase.account_id is not None
    composition.commercial_activation.mark_active(
        account_id=started.purchase.account_id,
        now=NOW + timedelta(minutes=1),
    )
    with pytest.raises(CommercialFulfillmentError):
        composition.commercial_trial.begin(
            plan_id="growth",
            price_id="growth-monthly",
            buyer_email="closed@example.com",
            legal_name="Closed Customer LTDA",
            idempotency_key="cl12-trial-closed-0002",
            now=NOW + timedelta(minutes=2),
        )
    expiring = composition.commercial_trial.begin(
        plan_id="growth",
        price_id="growth-monthly",
        buyer_email="elapsed@example.com",
        legal_name="Elapsed Customer LTDA",
        idempotency_key="cl12-trial-expiring-0001",
        now=NOW,
    )
    composition.commercial_trial.expire(
        purchase_id=expiring.purchase.purchase_id, now=NOW + timedelta(days=14),
    )
    with pytest.raises(CommercialFulfillmentError):
        composition.commercial_trial.begin(
            plan_id="growth",
            price_id="growth-monthly",
            buyer_email="elapsed@example.com",
            legal_name="Elapsed Customer LTDA",
            idempotency_key="cl12-trial-expiring-0002",
            now=NOW + timedelta(days=14, minutes=1),
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
