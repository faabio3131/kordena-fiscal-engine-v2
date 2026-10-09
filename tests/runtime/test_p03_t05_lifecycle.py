"""Nine commercial facts through authenticated HTTP + real PostgreSQL in CI."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from test_p03_t03_command import ACTOR, begin, count, post, setup
from test_p03_t03_command import settings as postgres_settings

from kordena_fiscal.persistence.commercial_fulfillment import (
    CommercialSqlStore,
    postgres_canonical_commercial_database,
)
from kordena_fiscal.product.billing import CommercialSubscription, SubscriptionStatus
from kordena_fiscal.product.commercial_fulfillment import CommercialFulfillmentError
from kordena_fiscal.product.pricing import BillingCadence
from kordena_fiscal.runtime import api as runtime_api

settings = postgres_settings


def event(payload, kind, index, *, invoice=None, occurred_at=None):
    return {
        **payload,
        "event_id": f"evt-lifecycle-{index}",
        "event_type": kind,
        "occurred_at": occurred_at
        or (datetime.fromisoformat(payload["occurred_at"]) + timedelta(seconds=index)).isoformat(),
        "command_invoice_id": invoice or payload["command_invoice_id"],
    }


def snapshot(app, purchase_id):
    database = postgres_canonical_commercial_database(app.state.nfcore_runtime.database)
    with database() as uow:
        return (
            uow.commercial.get_purchase(purchase_id),
            uow.commercial.get_subscription_for_purchase(purchase_id),
            uow.commercial.get_contract(purchase_id),
        )


def claim(app, purchase_id, at=None):
    service = app.state.nfcore_runtime_composition.commercial_claim
    now = at or datetime.now(UTC)
    issued = service.issue(purchase_id=purchase_id, now=now)
    service.complete(claim_token=issued.claim_token, legal_name=snapshot(app, purchase_id)[0].legal_name, now=now)


def activate(client, app, payload):
    response = post(client, payload)
    assert response.status_code == 202, response.text
    purchase_id = response.json()["purchase_id"]
    claim(app, purchase_id)
    activated = event(payload, "subscription_activated", 1)
    assert post(client, activated).status_code == 202
    return purchase_id


def test_nine_events_keep_one_identity_and_no_repeated_delivery(settings):
    app, _, _, delivery = setup(settings)
    with TestClient(app, base_url="https://testserver") as client:
        payload = begin(client)
        purchase_id = activate(client, app, payload)
        purchase, durable, original = snapshot(app, purchase_id)
        assert len(delivery.calls) == 1
        for index, kind in enumerate(
            (
                "subscription_renewed",
                "subscription_payment_late",
                "subscription_paused",
                "subscription_recovered",
                "subscription_canceled",
                "refund_confirmed",
                "chargeback_confirmed",
            ),
            start=2,
        ):
            invoice = "invoice-renewal" if kind == "subscription_renewed" else None
            response = post(client, event(payload, kind, index, invoice=invoice))
            assert response.status_code == 202, response.text
            assert post(client, event(payload, kind, index, invoice=invoice)).status_code == 200
            current, subscription, contract = snapshot(app, purchase_id)
            assert subscription.subscription_id == durable.subscription_id
            assert current.tenant_id == purchase.tenant_id
            assert current.account_id == purchase.account_id
            assert len(delivery.calls) == 1
        assert subscription.checkpoint.status is SubscriptionStatus.CANCELED
        assert len(contract.periods) == 2
        assert contract.periods[0].start == original.periods[0].start
        assert count(app, "fm_human_accounts") == count(app, "fm_control_plane_organizations") == 1
        assert count(app, "fm_commercial_subscriptions") == 1
        assert count(app, "fm_password_resets") == 1
        assert post(client, event(payload, "subscription_recovered", 10)).status_code == 409
        assert snapshot(app, purchase_id) == (current, subscription, contract)


def test_renewal_before_claim_uses_original_snapshot_after_new_pricing(settings):
    app, _, _, delivery = setup(settings)
    with TestClient(app, base_url="https://testserver") as client:
        payload = begin(client)
        first = post(client, payload)
        purchase_id = first.json()["purchase_id"]
        services = app.state.nfcore_runtime_composition
        configuration = services.pricing_administration.history()[-1].configuration
        changed = replace(
            configuration,
            version=configuration.version + 1,
            prices=tuple(replace(p, cadence=BillingCadence.ANNUAL) for p in configuration.prices),
            plans=tuple(replace(p, grace_days=90) for p in configuration.plans),
        )
        services.pricing_administration.publish(
            actor=ACTOR,
            configuration=changed,
            expected_version=configuration.version,
            correlation_id="synthetic-lifecycle-pricing",
            published_at=datetime.now(UTC),
        )
        renewal = event(payload, "subscription_renewed", 2, invoice="paid-invoice-2")
        assert post(client, renewal).status_code == 202
        _, _, contract = snapshot(app, purchase_id)
        assert contract.cadence is BillingCadence.MONTHLY
        assert contract.grace_days == 0
        assert len(contract.periods) == 2
        assert count(app, "fm_human_accounts") == 0
        assert len(delivery.calls) == 0
        claim(app, purchase_id)
        assert post(client, event(payload, "subscription_activated", 3)).status_code == 202
        _, subscription, contract = snapshot(app, purchase_id)
        assert subscription.checkpoint.period_end == contract.periods[-1].end
        assert subscription.checkpoint.period_start == contract.periods[-1].start
        assert CommercialSubscription.restore(subscription.checkpoint).accepts_operations_at(
            datetime.now(UTC)
        )
        assert len(delivery.calls) == 1


def test_same_invoice_new_ids_concurrency_restart_and_conflicts(settings):
    app, options, _, _ = setup(settings)
    with TestClient(app, base_url="https://testserver") as client:
        payload = begin(client)
        purchase_id = activate(client, app, payload)
        renewal = event(payload, "subscription_renewed", 2, invoice="invoice-renewal")
        other = {**renewal, "event_id": "evt-lifecycle-other"}
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda body: post(client, body), (renewal, other)))
        assert sorted(r.status_code for r in results) == [200, 202]
        before = snapshot(app, purchase_id)
        assert len(before[2].periods) == 2
        assert (
            post(
                client, event(payload, "subscription_renewed", 3, invoice="invoice-renewal")
            ).status_code
            == 409
        )
        assert snapshot(app, purchase_id) == before
    restarted = runtime_api.create_runtime_app(settings, **options)
    with TestClient(restarted, base_url="https://testserver") as client:
        assert post(client, {**renewal, "event_id": "evt-restarted-invoice"}).status_code == 200
        assert snapshot(restarted, purchase_id) == before
        assert count(restarted, "fm_human_accounts") == 1


@pytest.mark.parametrize("stage", ["before-commit", "after-commit"])
def test_paid_period_failure_is_recoverable_once(settings, monkeypatch, stage):
    app, _, _, _ = setup(settings)
    with TestClient(app, base_url="https://testserver") as client:
        payload = begin(client)
        purchase_id = activate(client, app, payload)
        renewal = event(payload, "subscription_renewed", 2, invoice="invoice-failure")
        if stage == "before-commit":
            target, method = CommercialSqlStore, "put_contract"
        else:
            target, method = app.state.nfcore_command_commercial.store, "processed"
        original = getattr(target, method)

        def fail(*args, **kwargs):
            raise RuntimeError("synthetic-private-failure")

        monkeypatch.setattr(target, method, fail)
        response = post(client, renewal)
        assert response.status_code == 503 and "private" not in response.text
        _, _, contract = snapshot(app, purchase_id)
        assert len(contract.periods) == (1 if stage == "before-commit" else 2)
        monkeypatch.setattr(target, method, original)
        assert post(client, renewal).status_code == (202 if stage == "before-commit" else 200)
        assert len(snapshot(app, purchase_id)[2].periods) == 2
        assert count(app, "fm_human_accounts") == 1


@pytest.mark.parametrize(
    "kind",
    ["subscription_paused", "subscription_canceled", "refund_confirmed", "chargeback_confirmed"],
)
def test_lifecycle_before_claim_blocks_identity_creation(settings, kind):
    app, _, _, delivery = setup(settings)
    with TestClient(app, base_url="https://testserver") as client:
        payload = begin(client)
        first = post(client, payload)
        purchase_id = first.json()["purchase_id"]
        assert post(client, event(payload, kind, 2)).status_code == 202
        with pytest.raises(CommercialFulfillmentError):
            claim(app, purchase_id)
        assert count(app, "fm_human_accounts") == count(app, "fm_commercial_subscriptions") == 0
        assert len(delivery.calls) == 0
        if kind == "subscription_paused":
            assert post(client, event(payload, "subscription_recovered", 3)).status_code == 202
            claim(app, purchase_id)
            assert post(client, event(payload, "subscription_activated", 4)).status_code == 202
            assert count(app, "fm_human_accounts") == 1


def test_expired_contract_recovery_cannot_create_free_time_or_claim(settings):
    app, _, _, _ = setup(settings)
    with TestClient(app, base_url="https://testserver") as client:
        payload = begin(client)
        payload["occurred_at"] = (datetime.now(UTC) - timedelta(days=40)).isoformat()
        first = post(client, payload)
        purchase_id = first.json()["purchase_id"]
        assert first.status_code == 202
        original = snapshot(app, purchase_id)[2]
        for index, kind in enumerate(
            ("subscription_payment_late", "subscription_paused", "subscription_recovered"), start=2
        ):
            changed = event(
                payload,
                kind,
                index,
                occurred_at=(datetime.now(UTC) - timedelta(seconds=10 - index)).isoformat(),
            )
            assert post(client, changed).status_code == 202
            with pytest.raises(CommercialFulfillmentError):
                claim(app, purchase_id)
            assert snapshot(app, purchase_id)[2] == original
        paid = event(
            payload,
            "subscription_renewed",
            6,
            invoice="late-paid-invoice",
            occurred_at=(datetime.now(UTC) - timedelta(seconds=1)).isoformat(),
        )
        assert post(client, paid).status_code == 202
        claim(app, purchase_id)
        assert count(app, "fm_human_accounts") == 0


def test_migration_16_upgrades_15_and_preserves_legacy_subscription(settings):
    app, _, _, _ = setup(settings)
    with TestClient(app, base_url="https://testserver") as client:
        payload = begin(client)
        purchase_id = activate(client, app, payload)
        before = snapshot(app, purchase_id)
        database = app.state.nfcore_runtime.database
        with database.connection() as connection:
            connection.execute("DROP TABLE fm_commercial_contracts")
            connection.execute(
                "ALTER TABLE fm_commercial_event_receipts DROP COLUMN payment_reference"
            )
            connection.execute("DELETE FROM fm_schema_migrations WHERE version=16")
            connection.commit()
        assert database.initialize() == (16,)
        assert database.initialize() == ()
        purchase, subscription, contract = snapshot(app, purchase_id)
        assert purchase == before[0]
        assert subscription.checkpoint.period_start == before[1].checkpoint.period_start
        assert subscription.checkpoint.period_end == before[1].checkpoint.period_end
        assert subscription.checkpoint.usage == before[1].checkpoint.usage
        assert contract is None
        # The original authenticated receipt and historical pricing reconstruct terms.
        renewal = event(payload, "subscription_renewed", 2, invoice="invoice-upgrade-renewal")
        assert post(client, renewal).status_code == 202
        assert len(snapshot(app, purchase_id)[2].periods) == 2
        assert count(app, "fm_human_accounts") == 1


def test_governed_grace_and_quotas_snapshot_survives_activation(settings):
    from kordena_fiscal.product.billing import UsageQuota

    app, _, _, _ = setup(settings)
    with TestClient(app, base_url="https://testserver") as client:
        services = app.state.nfcore_runtime_composition
        configuration = services.pricing_administration.history()[-1].configuration
        configured = replace(
            configuration,
            version=configuration.version + 1,
            plans=tuple(
                replace(plan, grace_days=3, periodic_quotas=(UsageQuota("documents", 2),))
                for plan in configuration.plans
            ),
        )
        services.pricing_administration.publish(
            actor=ACTOR,
            configuration=configured,
            expected_version=configuration.version,
            correlation_id="synthetic-grace-quotas",
            published_at=datetime.now(UTC),
        )
        payload = begin(client)
        first = post(client, payload)
        purchase_id = first.json()["purchase_id"]
        assert post(client, event(payload, "subscription_payment_late", 2)).status_code == 202
        contract = snapshot(app, purchase_id)[2]
        at = contract.periods[-1].end + timedelta(days=1)
        assert contract.grace_days == 3
        claim(app, purchase_id, at)
        services.commercial_activation.provision(purchase_id=purchase_id, now=at)
        durable = snapshot(app, purchase_id)[1]
        subscription = CommercialSubscription.restore(durable.checkpoint)
        assert subscription.accepts_operations_at(at)
        assert subscription.record_usage("documents", at=at, amount=2) == 2
        with pytest.raises(ValueError, match="quota"):
            subscription.record_usage("documents", at=at)
        assert not subscription.accepts_operations_at(contract.periods[-1].end + timedelta(days=3))


def test_pause_blocks_pending_activation_and_reset_retry(settings):
    app, _, _, delivery = setup(settings)
    with TestClient(app, base_url="https://testserver") as client:
        payload = begin(client)
        purchase_id = activate(client, app, payload)
        services = app.state.nfcore_runtime_composition
        purchase, _, _ = snapshot(app, purchase_id)
        assert post(client, event(payload, "subscription_paused", 2)).status_code == 202
        with pytest.raises(CommercialFulfillmentError, match="coverage"):
            services.commercial_activation.provision(purchase_id=purchase_id, now=datetime.now(UTC))
        with pytest.raises(CommercialFulfillmentError, match="coverage"):
            services.commercial_activation.mark_active(
                account_id=purchase.account_id, now=datetime.now(UTC)
            )
        assert len(delivery.calls) == 1
        assert count(app, "fm_password_resets") == 1
        assert post(client, event(payload, "subscription_activated", 3)).status_code == 409


def test_legacy_committed_event_recovers_pending_inbox_without_new_credit(settings):
    app, _, _, delivery = setup(settings)
    with TestClient(app, base_url="https://testserver") as client:
        payload = begin(client)
        purchase_id = activate(client, app, payload)
        before = snapshot(app, purchase_id)
        database = app.state.nfcore_runtime.database
        with database.connection() as connection:
            connection.execute(
                "UPDATE fm_command_commercial_inbox SET processed_at = NULL WHERE event_id = ?",
                (payload["event_id"],),
            )
            connection.execute(
                "UPDATE fm_commercial_event_receipts SET payment_reference = NULL "
                "WHERE event_type = ?",
                ("sale_confirmed",),
            )
            connection.commit()
        bad = {**payload, "command_invoice_id": "invoice-tampered"}
        assert post(client, bad).status_code == 409
        assert post(client, payload).status_code == 200
        assert snapshot(app, purchase_id) == before
        assert len(delivery.calls) == 1
        assert count(app, "fm_human_accounts") == 1
