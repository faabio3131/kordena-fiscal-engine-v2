"""Durable canonical lifecycle using synthetic SQLite; PostgreSQL HTTP certified separately."""

import sqlite3
from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from kordena_fiscal.application.commercial_fulfillment import CommercialFulfillmentService
from kordena_fiscal.persistence.commercial_fulfillment import CanonicalCommercialDatabase
from kordena_fiscal.persistence.commercial_period_schema import COMMERCIAL_PERIOD_SCHEMA
from kordena_fiscal.persistence.postgres import _COMMERCIAL_FULFILLMENT_SCHEMA
from kordena_fiscal.product.billing import (
    CommercialPlan,
    CommercialSubscription,
    SubscriptionStatus,
    UsageQuota,
)
from kordena_fiscal.product.commercial_fulfillment import (
    CommercialEventType as Event,
)
from kordena_fiscal.product.commercial_fulfillment import (
    CommercialFulfillmentError,
    DurableCommercialSubscription,
    ValidatedCommercialEvent,
)
from kordena_fiscal.product.commercial_lifecycle import (
    CommercialContract,
    PaidCommercialPeriod,
    period_end,
)
from kordena_fiscal.product.pricing import BillingCadence

NOW = datetime(2026, 1, 31, 12, tzinfo=UTC)
PLAN = CommercialPlan("growth", ("documents.issue",), (UsageQuota("documents", 3),))


@pytest.fixture
def canonical(tmp_path):
    path = tmp_path / "commercial.sqlite"
    with sqlite3.connect(path) as connection:
        for sql in _COMMERCIAL_FULFILLMENT_SCHEMA:
            connection.execute(sql)
        connection.execute("ALTER TABLE fm_commercial_purchases ADD COLUMN billing_status TEXT")
        connection.execute("ALTER TABLE fm_commercial_purchases ADD COLUMN legal_name TEXT")
        for sql in COMMERCIAL_PERIOD_SCHEMA:
            connection.execute(sql)

    @contextmanager
    def acquire():
        with sqlite3.connect(path) as connection:
            yield connection

    db = CanonicalCommercialDatabase(acquire)

    def factory(purchase, start, invoice):
        return CommercialContract(
            purchase.purchase_id,
            PLAN,
            BillingCadence.MONTHLY,
            0,
            "synthetic-pricing",
            1,
            (
                PaidCommercialPeriod(
                    invoice, start, start, period_end(start, BillingCadence.MONTHLY)
                ),
            ),
        )

    service = CommercialFulfillmentService(db, contract_factory=factory)
    sale = ValidatedCommercialEvent(
        "command",
        "sale-1",
        Event.SALE_CONFIRMED,
        "order-1",
        "growth",
        NOW,
        payment_reference="invoice-1",
    )
    service.process(event=sale, received_at=NOW)
    subscription = CommercialSubscription(
        tenant_id="tenant-synthetic",
        plan=PLAN,
        status=SubscriptionStatus.ACTIVE,
        period_start=NOW,
        period_end=datetime(2026, 2, 28, 12, tzinfo=UTC),
    )
    subscription.record_usage("documents", amount=2, at=NOW)
    with db() as uow:
        uow.commercial.put_subscription(
            DurableCommercialSubscription(
                "sub-1", sale.purchase_id, subscription.checkpoint(), "command", None, "sale-1", NOW
            )
        )
        uow.commit()
    return db, service, sale


def event(sale, kind, index, at=None, invoice=None):
    return replace(
        sale,
        event_id=f"event-{index}",
        event_type=kind,
        occurred_at=at or NOW + timedelta(minutes=index),
        payment_reference=invoice,
    )


def snapshot(db, sale):
    with db() as uow:
        return (
            uow.commercial.get_purchase(sale.purchase_id),
            uow.commercial.get_subscription_for_purchase(sale.purchase_id),
            uow.commercial.get_contract(sale.purchase_id),
        )


def test_early_invoice_preserves_current_quota_history_and_future_period(canonical):
    db, service, sale = canonical
    renewal = event(sale, Event.SUBSCRIPTION_RENEWED, 1, invoice="invoice-2")
    service.process(event=renewal, received_at=renewal.occurred_at)
    purchase, durable, contract = snapshot(db, sale)
    assert durable.checkpoint.period_start == datetime(2026, 2, 28, 12, tzinfo=UTC)
    assert durable.checkpoint.period_end == datetime(2026, 3, 28, 12, tzinfo=UTC)
    assert durable.checkpoint.usage == ()
    assert durable.checkpoint.previous_periods[0].usage == (("documents", 2),)
    subscription = CommercialSubscription.restore(durable.checkpoint)
    assert subscription.accepts_operations_at(NOW + timedelta(days=1))
    assert subscription.record_usage("documents", at=NOW + timedelta(days=1)) == 3
    with pytest.raises(ValueError, match="quota"):
        subscription.record_usage("documents", at=NOW + timedelta(days=1))
    assert subscription.record_usage("documents", at=durable.checkpoint.period_start) == 1
    with db() as uow:
        uow.commercial.put_subscription(replace(durable, checkpoint=subscription.checkpoint()))
        uow.commit()
    repeated = service.process(
        event=replace(renewal, event_id="other-id"), received_at=renewal.occurred_at
    )
    assert repeated.replay
    _, after, contract = snapshot(db, sale)
    assert after.checkpoint.previous_periods[0].usage == (("documents", 3),)
    assert after.checkpoint.usage == (("documents", 1),)
    assert len(contract.periods) == 2
    assert purchase.purchase_id == sale.purchase_id


def test_invoice_conflict_stale_and_ambiguous_events_rollback(canonical):
    db, service, sale = canonical
    renewal = event(sale, Event.SUBSCRIPTION_RENEWED, 2, invoice="invoice-2")
    service.process(event=renewal, received_at=renewal.occurred_at)
    before = snapshot(db, sale)
    for bad in (
        replace(renewal, event_id="changed-content", occurred_at=NOW + timedelta(minutes=3)),
        replace(renewal, payment_reference="invoice-3"),
        event(sale, Event.SUBSCRIPTION_RENEWED, 1, invoice="invoice-3"),
        event(sale, Event.SUBSCRIPTION_RENEWED, 3, invoice="invoice-1"),
    ):
        with pytest.raises(CommercialFulfillmentError):
            service.process(event=bad, received_at=NOW + timedelta(days=1))
        assert snapshot(db, sale) == before


@pytest.mark.parametrize(
    "kind",
    [Event.SUBSCRIPTION_PAYMENT_LATE, Event.SUBSCRIPTION_PAUSED, Event.SUBSCRIPTION_RECOVERED],
)
def test_non_payment_events_preserve_time_and_usage(canonical, kind):
    db, service, sale = canonical
    _, old, contract = snapshot(db, sale)
    lifecycle = event(sale, kind, 1)
    service.process(event=lifecycle, received_at=lifecycle.occurred_at)
    _, new, after = snapshot(db, sale)
    assert new.checkpoint.period_start == old.checkpoint.period_start
    assert new.checkpoint.period_end == old.checkpoint.period_end
    assert new.checkpoint.usage == old.checkpoint.usage
    assert after == contract
    assert not CommercialSubscription.restore(new.checkpoint).accepts_operations_at(
        old.checkpoint.period_end
    )


@pytest.mark.parametrize(
    "kind", [Event.SUBSCRIPTION_CANCELED, Event.REFUND_CONFIRMED, Event.CHARGEBACK_CONFIRMED]
)
def test_terminal_events_preserve_identity_history_and_block_resurrection(canonical, kind):
    db, service, sale = canonical
    closing = event(sale, kind, 1)
    service.process(event=closing, received_at=closing.occurred_at)
    purchase, durable, contract = snapshot(db, sale)
    assert durable.subscription_id == "sub-1"
    assert durable.checkpoint.usage == (("documents", 2),)
    assert durable.checkpoint.status is SubscriptionStatus.CANCELED
    assert CommercialSubscription.restore(durable.checkpoint).preserves_existing_fiscal_state
    with pytest.raises(CommercialFulfillmentError, match="terminal"):
        service.process(
            event=event(sale, Event.SUBSCRIPTION_RENEWED, 2, invoice="invoice-2"),
            received_at=NOW + timedelta(days=1),
        )
    assert snapshot(db, sale) == (purchase, durable, contract)


def test_late_payment_does_not_cover_gap(canonical):
    db, service, sale = canonical
    at = NOW + timedelta(days=60)
    service.process(
        event=event(sale, Event.SUBSCRIPTION_RENEWED, 1, at, "invoice-2"), received_at=at
    )
    _, durable, _ = snapshot(db, sale)
    restored = CommercialSubscription.restore(durable.checkpoint)
    assert durable.checkpoint.period_start == at
    assert restored.accepts_operations_at(at)
    assert not restored.accepts_operations_at(NOW + timedelta(days=40))


@pytest.mark.parametrize("grace", [0, 3])
def test_expiry_and_explicit_grace_boundaries(grace):
    end = datetime(2026, 2, 28, 12, tzinfo=UTC)
    subscription = CommercialSubscription(
        tenant_id="tenant-synthetic",
        plan=PLAN,
        status=SubscriptionStatus.GRACE,
        period_start=NOW,
        period_end=end,
        grace_days=grace,
    )
    assert subscription.accepts_operations_at(end - timedelta(microseconds=1))
    assert subscription.accepts_operations_at(end) is bool(grace)
    assert not subscription.accepts_operations_at(end + timedelta(days=grace))
    subscription.transition(SubscriptionStatus.ACTIVE)
    assert not subscription.accepts_operations_at(end)
    with pytest.raises(ValueError, match="timezone-aware"):
        subscription.accepts_operations_at(end.replace(tzinfo=None))


@pytest.mark.parametrize(
    "start,cadence,end",
    [
        (
            datetime(2024, 2, 29, tzinfo=UTC),
            BillingCadence.ANNUAL,
            datetime(2025, 2, 28, tzinfo=UTC),
        ),
        (NOW, BillingCadence.MONTHLY, datetime(2026, 2, 28, 12, tzinfo=UTC)),
        (NOW, BillingCadence.QUARTERLY, datetime(2026, 4, 30, 12, tzinfo=UTC)),
        (NOW, BillingCadence.SEMIANNUAL, datetime(2026, 7, 31, 12, tzinfo=UTC)),
    ],
)
def test_calendar_cadence(start, cadence, end):
    assert period_end(start, cadence) == end


def test_one_time_invoice_cannot_renew():
    contract = CommercialContract(
        "purchase",
        PLAN,
        BillingCadence.ONE_TIME,
        0,
        "pricing",
        1,
        (PaidCommercialPeriod("initial", NOW, NOW, period_end(NOW, BillingCadence.ONE_TIME)),),
    )
    with pytest.raises(CommercialFulfillmentError, match="one-time"):
        contract.renew("renewal", NOW + timedelta(days=1))


def test_transaction_failure_does_not_credit_or_consume_event(canonical, monkeypatch):
    from kordena_fiscal.persistence.commercial_fulfillment import CommercialSqlStore

    db, service, sale = canonical
    original = CommercialSqlStore.put_contract
    before = snapshot(db, sale)
    renewal = event(sale, Event.SUBSCRIPTION_RENEWED, 1, invoice="invoice-2")

    def fail(*args):
        raise RuntimeError("synthetic-before-commit")

    monkeypatch.setattr(CommercialSqlStore, "put_contract", fail)
    with pytest.raises(RuntimeError):
        service.process(event=renewal, received_at=renewal.occurred_at)
    assert snapshot(db, sale) == before
    monkeypatch.setattr(CommercialSqlStore, "put_contract", original)
    assert not service.process(event=renewal, received_at=renewal.occurred_at).replay


def test_default_wall_clock_rejects_expired_entitlement_and_usage():
    end = datetime.now(UTC) - timedelta(days=1)
    subscription = CommercialSubscription(
        tenant_id="synthetic-tenant",
        plan=PLAN,
        status=SubscriptionStatus.ACTIVE,
        period_start=end - timedelta(days=30),
        period_end=end,
    )
    assert not subscription.accepts_new_commercial_operations
    with pytest.raises(ValueError, match="blocks"):
        subscription.require_entitlement("documents.issue")
    with pytest.raises(ValueError, match="does not accept"):
        subscription.record_usage("documents")


def test_paid_usage_cannot_be_erased_during_checkpoint_write(canonical):
    db, _, sale = canonical
    _, durable, contract = snapshot(db, sale)
    with db() as uow:
        with pytest.raises(CommercialFulfillmentError, match="cannot be erased"):
            uow.commercial.put_subscription(
                replace(durable, checkpoint=replace(durable.checkpoint, usage=()))
            )
    assert snapshot(db, sale)[2] == contract
