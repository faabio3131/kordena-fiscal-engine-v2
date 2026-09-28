from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime, timedelta

import pytest

from kordena_fiscal.application.commercial_fulfillment import CommercialFulfillmentService
from kordena_fiscal.product.commercial_fulfillment import (
    CommercialEventReceipt,
    CommercialEventType,
    CommercialFulfillmentError,
    CommercialPurchaseRecord,
    CommercialPurchaseState,
    DurableCommercialSubscription,
    ValidatedCommercialEvent,
)

NOW = datetime(2026, 9, 28, 2, 30, tzinfo=UTC)


class MemoryCommercialStore:
    def __init__(self) -> None:
        self.events: dict[tuple[str, str], CommercialEventReceipt] = {}
        self.purchases: dict[str, CommercialPurchaseRecord] = {}
        self.subscriptions: dict[str, DurableCommercialSubscription] = {}

    def receive_event(
        self,
        receipt: CommercialEventReceipt,
    ) -> tuple[CommercialEventReceipt, bool]:
        key = (receipt.provider_id, receipt.event_id)
        current = self.events.get(key)
        if current is not None:
            if current != receipt:
                raise CommercialFulfillmentError(
                    "commercial event identity was replayed with different content"
                )
            return current, True
        self.events[key] = receipt
        return receipt, False

    def get_event(self, provider_id: str, event_id: str) -> CommercialEventReceipt | None:
        return self.events.get((provider_id, event_id))

    def get_purchase(self, purchase_id: str) -> CommercialPurchaseRecord | None:
        return self.purchases.get(purchase_id)

    def get_purchase_by_external_order(
        self,
        provider_id: str,
        external_order_id: str,
    ) -> CommercialPurchaseRecord | None:
        return next(
            (
                item
                for item in self.purchases.values()
                if item.provider_id == provider_id
                and item.external_order_id == external_order_id
            ),
            None,
        )

    def put_purchase(self, purchase: CommercialPurchaseRecord) -> CommercialPurchaseRecord:
        self.purchases[purchase.purchase_id] = purchase
        return purchase

    def get_subscription(
        self,
        subscription_id: str,
    ) -> DurableCommercialSubscription | None:
        return self.subscriptions.get(subscription_id)

    def get_subscription_by_external_reference(
        self,
        provider_id: str,
        external_subscription_id: str,
    ) -> DurableCommercialSubscription | None:
        return next(
            (
                item
                for item in self.subscriptions.values()
                if item.provider_id == provider_id
                and item.external_subscription_id == external_subscription_id
            ),
            None,
        )

    def get_subscription_for_tenant(
        self,
        tenant_id: str,
    ) -> DurableCommercialSubscription | None:
        return next(
            (
                item
                for item in self.subscriptions.values()
                if item.checkpoint.tenant_id == tenant_id
            ),
            None,
        )

    def put_subscription(
        self,
        subscription: DurableCommercialSubscription,
    ) -> DurableCommercialSubscription:
        self.subscriptions[subscription.subscription_id] = subscription
        return subscription


class MemoryCommercialUow:
    def __init__(self, store: MemoryCommercialStore) -> None:
        self.commercial = store
        self._snapshot: tuple[object, object, object] | None = None
        self._committed = False

    def __enter__(self) -> MemoryCommercialUow:
        self._snapshot = (
            deepcopy(self.commercial.events),
            deepcopy(self.commercial.purchases),
            deepcopy(self.commercial.subscriptions),
        )
        self._committed = False
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        if exc_type is not None or not self._committed:
            assert self._snapshot is not None
            events, purchases, subscriptions = self._snapshot
            self.commercial.events = events  # type: ignore[assignment]
            self.commercial.purchases = purchases  # type: ignore[assignment]
            self.commercial.subscriptions = subscriptions  # type: ignore[assignment]

    def commit(self) -> None:
        self._committed = True


class MemoryCommercialDatabase:
    def __init__(self) -> None:
        self.store = MemoryCommercialStore()

    def __call__(self) -> MemoryCommercialUow:
        return MemoryCommercialUow(self.store)


def event(
    event_type: CommercialEventType = CommercialEventType.SALE_CONFIRMED,
    *,
    event_id: str = "evt-1",
    occurred_at: datetime = NOW,
    email: str | None = "owner@example.com",
    plan_id: str = "growth",
    price_id: str | None = "growth-monthly",
    external_customer_id: str | None = "customer-1",
    external_subscription_id: str | None = "subscription-1",
) -> ValidatedCommercialEvent:
    return ValidatedCommercialEvent(
        provider_id="hotmart",
        event_id=event_id,
        event_type=event_type,
        external_order_id="order-1",
        plan_id=plan_id,
        price_id=price_id,
        external_customer_id=external_customer_id,
        external_subscription_id=external_subscription_id,
        buyer_email=email,
        occurred_at=occurred_at,
    )


def test_confirmed_sale_creates_unclaimed_purchase_and_replay_is_idempotent() -> None:
    database = MemoryCommercialDatabase()
    service = CommercialFulfillmentService(database)

    first = service.process(event=event(), received_at=NOW)
    replay = service.process(event=event(), received_at=NOW)

    assert first.replay is False
    assert first.purchase.state is CommercialPurchaseState.UNCLAIMED
    assert first.purchase.tenant_id is None
    assert first.purchase.account_id is None
    assert replay.replay is True
    assert replay.purchase == first.purchase
    assert len(database.store.purchases) == 1
    assert len(database.store.events) == 1


def test_sale_without_contact_enters_identity_required() -> None:
    service = CommercialFulfillmentService(MemoryCommercialDatabase())
    result = service.process(event=event(email=None), received_at=NOW)
    assert result.purchase.state is CommercialPurchaseState.IDENTITY_REQUIRED


def test_lifecycle_event_cannot_create_unknown_purchase_and_receipt_rolls_back() -> None:
    database = MemoryCommercialDatabase()
    service = CommercialFulfillmentService(database)

    with pytest.raises(CommercialFulfillmentError, match="cannot create"):
        service.process(
            event=event(
                CommercialEventType.SUBSCRIPTION_RENEWED,
                event_id="evt-renewal-orphan",
            ),
            received_at=NOW,
        )

    assert database.store.events == {}
    assert database.store.purchases == {}


def test_stale_and_conflicting_identity_events_fail_closed_without_durable_receipt() -> None:
    database = MemoryCommercialDatabase()
    service = CommercialFulfillmentService(database)
    service.process(event=event(), received_at=NOW)

    with pytest.raises(CommercialFulfillmentError, match="buyer email"):
        service.process(
            event=event(
                CommercialEventType.SUBSCRIPTION_RENEWED,
                event_id="evt-email-conflict",
                occurred_at=NOW + timedelta(seconds=1),
                email="attacker@example.com",
            ),
            received_at=NOW + timedelta(seconds=1),
        )
    assert ("hotmart", "evt-email-conflict") not in database.store.events

    with pytest.raises(CommercialFulfillmentError, match="stale"):
        service.process(
            event=event(
                CommercialEventType.SUBSCRIPTION_RENEWED,
                event_id="evt-stale",
                occurred_at=NOW - timedelta(seconds=1),
            ),
            received_at=NOW + timedelta(seconds=2),
        )
    assert ("hotmart", "evt-stale") not in database.store.events


def test_cancel_and_refund_are_terminal_for_automatic_provider_reactivation() -> None:
    database = MemoryCommercialDatabase()
    service = CommercialFulfillmentService(database)
    service.process(event=event(), received_at=NOW)

    canceled = service.process(
        event=event(
            CommercialEventType.SUBSCRIPTION_CANCELED,
            event_id="evt-cancel",
            occurred_at=NOW + timedelta(seconds=1),
        ),
        received_at=NOW + timedelta(seconds=1),
    )
    assert canceled.purchase.state is CommercialPurchaseState.CANCELED

    with pytest.raises(CommercialFulfillmentError, match="cannot be reactivated"):
        service.process(
            event=event(
                CommercialEventType.SUBSCRIPTION_RECOVERED,
                event_id="evt-recover-after-cancel",
                occurred_at=NOW + timedelta(seconds=2),
            ),
            received_at=NOW + timedelta(seconds=2),
        )

    refunded = service.process(
        event=event(
            CommercialEventType.REFUND_CONFIRMED,
            event_id="evt-refund",
            occurred_at=NOW + timedelta(seconds=3),
        ),
        received_at=NOW + timedelta(seconds=3),
    )
    assert refunded.purchase.state is CommercialPurchaseState.REFUNDED


def test_plan_price_subscription_and_customer_identity_cannot_be_rewritten() -> None:
    for kwargs, message in (
        ({"plan_id": "enterprise"}, "plan"),
        ({"price_id": "other-price"}, "price"),
        ({"external_subscription_id": "other-subscription"}, "subscription"),
        ({"external_customer_id": "other-customer"}, "customer"),
    ):
        database = MemoryCommercialDatabase()
        service = CommercialFulfillmentService(database)
        service.process(event=event(), received_at=NOW)

        with pytest.raises(CommercialFulfillmentError, match=message):
            service.process(
                event=event(
                    CommercialEventType.SUBSCRIPTION_RENEWED,
                    event_id=f"evt-conflict-{message}",
                    occurred_at=NOW + timedelta(seconds=1),
                    **kwargs,
                ),
                received_at=NOW + timedelta(seconds=1),
            )


def test_naive_received_at_fails_closed_before_persistence() -> None:
    database = MemoryCommercialDatabase()
    service = CommercialFulfillmentService(database)

    with pytest.raises(CommercialFulfillmentError, match="timezone-aware"):
        service.process(
            event=event(),
            received_at=datetime(2026, 9, 28, 2, 30),
        )

    assert database.store.events == {}
