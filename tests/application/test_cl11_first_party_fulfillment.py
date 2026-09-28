from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from kordena_fiscal.application.commercial_fulfillment import CommercialFulfillmentService
from kordena_fiscal.product.commercial_fulfillment import (
    CommercialAcquisitionRecord,
    CommercialEventReceipt,
    CommercialEventType,
    CommercialFulfillmentError,
    CommercialPurchaseRecord,
    CommercialPurchaseState,
    ValidatedCommercialEvent,
)

NOW = datetime(2026, 9, 28, 14, 0, tzinfo=UTC)


class MemoryStore:
    def __init__(self) -> None:
        self.acquisitions: dict[str, CommercialAcquisitionRecord] = {}
        self.events: dict[tuple[str, str], CommercialEventReceipt] = {}
        self.purchases: dict[str, CommercialPurchaseRecord] = {}

    def get_acquisition(
        self,
        acquisition_id: str,
    ) -> CommercialAcquisitionRecord | None:
        return self.acquisitions.get(acquisition_id)

    def get_acquisition_by_idempotency(
        self,
        idempotency_sha256: str,
    ) -> CommercialAcquisitionRecord | None:
        return next(
            (
                value
                for value in self.acquisitions.values()
                if value.idempotency_sha256 == idempotency_sha256
            ),
            None,
        )

    def put_acquisition(
        self,
        acquisition: CommercialAcquisitionRecord,
    ) -> CommercialAcquisitionRecord:
        self.acquisitions[acquisition.acquisition_id] = acquisition
        return acquisition

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

    def get_purchase(self, purchase_id: str) -> CommercialPurchaseRecord | None:
        return self.purchases.get(purchase_id)

    def put_purchase(
        self,
        purchase: CommercialPurchaseRecord,
    ) -> CommercialPurchaseRecord:
        self.purchases[purchase.purchase_id] = purchase
        return purchase


class MemoryUow:
    def __init__(self, store: MemoryStore) -> None:
        self.commercial = store
        self._snapshot: tuple[object, object, object] | None = None
        self._committed = False

    def __enter__(self) -> MemoryUow:
        self._snapshot = (
            deepcopy(self.commercial.acquisitions),
            deepcopy(self.commercial.events),
            deepcopy(self.commercial.purchases),
        )
        self._committed = False
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        if exc_type is not None or not self._committed:
            assert self._snapshot is not None
            acquisitions, events, purchases = self._snapshot
            self.commercial.acquisitions = acquisitions  # type: ignore[assignment]
            self.commercial.events = events  # type: ignore[assignment]
            self.commercial.purchases = purchases  # type: ignore[assignment]

    def commit(self) -> None:
        self._committed = True


class MemoryDatabase:
    def __init__(self) -> None:
        self.store = MemoryStore()

    def __call__(self) -> MemoryUow:
        return MemoryUow(self.store)


def acquisition() -> CommercialAcquisitionRecord:
    return CommercialAcquisitionRecord(
        acquisition_id="acq-0123456789abcdef0123456789abcdef",
        idempotency_sha256="a" * 64,
        request_sha256="b" * 64,
        provider_id="synthetic",
        plan_id="growth",
        price_id="growth-monthly",
        buyer_email="owner@example.com",
        legal_name="ACME Tecnologia LTDA",
        created_at=NOW,
        expires_at=NOW.replace(hour=15),
    )


def event(
    *,
    provider_id: str = "synthetic",
    plan_id: str = "growth",
    price_id: str = "growth-monthly",
    buyer_email: str | None = None,
) -> ValidatedCommercialEvent:
    return ValidatedCommercialEvent(
        provider_id=provider_id,
        event_id="evt-first-party-sale",
        event_type=CommercialEventType.SALE_CONFIRMED,
        external_order_id="provider-order-1",
        plan_id=plan_id,
        price_id=price_id,
        buyer_email=buyer_email,
        acquisition_id=acquisition().acquisition_id,
        occurred_at=NOW,
    )


def test_validated_sale_links_nfcore_acquisition_without_creating_tenant() -> None:
    database = MemoryDatabase()
    original = acquisition()
    database.store.acquisitions[original.acquisition_id] = original
    fulfillment = CommercialFulfillmentService(database)

    result = fulfillment.process(event=event(), received_at=NOW)

    assert result.replay is False
    assert result.purchase.state is CommercialPurchaseState.UNCLAIMED
    assert result.purchase.buyer_email == original.buyer_email
    assert result.purchase.legal_name == original.legal_name
    assert result.purchase.tenant_id is None
    assert result.purchase.account_id is None
    linked = database.store.acquisitions[original.acquisition_id]
    assert linked.linked_purchase_id == result.purchase.purchase_id

    replay = fulfillment.process(event=event(), received_at=NOW)
    assert replay.replay is True
    assert replay.purchase == result.purchase


@pytest.mark.parametrize(
    ("candidate", "message"),
    (
        (event(provider_id="other"), "provider"),
        (event(plan_id="enterprise"), "plan"),
        (event(price_id="other-price"), "price"),
        (event(buyer_email="attacker@example.com"), "buyer email"),
    ),
)
def test_acquisition_identity_collision_rolls_back_event_and_purchase(
    candidate: ValidatedCommercialEvent,
    message: str,
) -> None:
    database = MemoryDatabase()
    original = acquisition()
    database.store.acquisitions[original.acquisition_id] = original
    fulfillment = CommercialFulfillmentService(database)

    with pytest.raises(CommercialFulfillmentError, match=message):
        fulfillment.process(event=candidate, received_at=NOW)

    assert database.store.events == {}
    assert database.store.purchases == {}
    assert database.store.acquisitions[original.acquisition_id] == original


def test_expired_acquisition_cannot_be_correlated_to_paid_event() -> None:
    database = MemoryDatabase()
    original = replace(
        acquisition(),
        created_at=NOW - timedelta(hours=1),
        expires_at=NOW - timedelta(minutes=1),
    )
    database.store.acquisitions[original.acquisition_id] = original
    fulfillment = CommercialFulfillmentService(database)

    with pytest.raises(CommercialFulfillmentError, match="expired"):
        fulfillment.process(event=event(), received_at=NOW)

    assert database.store.events == {}
    assert database.store.purchases == {}
    assert database.store.acquisitions[original.acquisition_id] == original


def test_acquisition_cannot_be_rebound_to_another_purchase() -> None:
    database = MemoryDatabase()
    original = replace(
        acquisition(),
        linked_purchase_id="commercial-purchase-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    )
    database.store.acquisitions[original.acquisition_id] = original
    fulfillment = CommercialFulfillmentService(database)

    with pytest.raises(CommercialFulfillmentError, match="another purchase"):
        fulfillment.process(event=event(), received_at=NOW)

    assert database.store.events == {}
    assert database.store.purchases == {}
