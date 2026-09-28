from datetime import UTC, datetime

import pytest

from kordena_fiscal.product.commercial_fulfillment import (
    CommercialEventReceipt,
    CommercialEventType,
    CommercialFulfillmentError,
    CommercialPurchaseRecord,
    CommercialPurchaseState,
    ValidatedCommercialEvent,
    commercial_purchase_id,
)

NOW = datetime(2026, 9, 28, 1, 30, tzinfo=UTC)


def test_purchase_identity_is_provider_scoped_and_does_not_expose_external_order() -> None:
    first = commercial_purchase_id("cakto", "order-123")
    second = commercial_purchase_id("hotmart", "order-123")

    assert first != second
    assert "order-123" not in first
    assert first.startswith("commercial-purchase-")


def test_validated_sale_event_is_provider_neutral_and_contains_no_tenant_authority() -> None:
    event = ValidatedCommercialEvent(
        provider_id="HotMart",
        event_id="evt-001",
        event_type=CommercialEventType.SALE_CONFIRMED,
        external_order_id="order-001",
        plan_id="growth",
        price_id="growth-monthly",
        buyer_email=" OWNER@EXAMPLE.COM ",
        occurred_at=NOW,
    )

    assert event.provider_id == "hotmart"
    assert event.buyer_email == "owner@example.com"
    assert event.purchase_id == commercial_purchase_id("hotmart", "order-001")
    assert not hasattr(event, "tenant_id")
    assert not hasattr(event, "entitlement_ids")
    assert not hasattr(event, "payment_approved")


def test_event_receipt_deliberately_excludes_customer_pii() -> None:
    receipt = CommercialEventReceipt(
        provider_id="cakto",
        event_id="evt-002",
        event_type=CommercialEventType.SALE_CONFIRMED,
        external_order_id="order-002",
        purchase_id=commercial_purchase_id("cakto", "order-002"),
        occurred_at=NOW,
        received_at=NOW,
    )

    assert not hasattr(receipt, "buyer_email")
    assert not hasattr(receipt, "external_customer_id")


def test_invalid_provider_email_and_naive_datetime_fail_closed() -> None:
    with pytest.raises(CommercialFulfillmentError, match="provider_id"):
        ValidatedCommercialEvent(
            provider_id="https://provider.example",
            event_id="evt",
            event_type=CommercialEventType.SALE_CONFIRMED,
            external_order_id="order",
            plan_id="growth",
            occurred_at=NOW,
        )

    with pytest.raises(CommercialFulfillmentError, match="buyer_email"):
        ValidatedCommercialEvent(
            provider_id="cakto",
            event_id="evt",
            event_type=CommercialEventType.SALE_CONFIRMED,
            external_order_id="order",
            plan_id="growth",
            buyer_email="invalid",
            occurred_at=NOW,
        )

    with pytest.raises(CommercialFulfillmentError, match="timezone-aware"):
        ValidatedCommercialEvent(
            provider_id="cakto",
            event_id="evt",
            event_type=CommercialEventType.SALE_CONFIRMED,
            external_order_id="order",
            plan_id="growth",
            occurred_at=datetime(2026, 9, 28, 1, 30),
        )


def test_purchase_record_keeps_provider_reference_separate_from_canonical_tenant() -> None:
    purchase = CommercialPurchaseRecord(
        purchase_id=commercial_purchase_id("cakto", "order-tenant-boundary"),
        provider_id="cakto",
        external_order_id="order-tenant-boundary",
        plan_id="growth",
        state=CommercialPurchaseState.UNCLAIMED,
        created_at=NOW,
        updated_at=NOW,
        last_event_at=NOW,
        last_event_id="evt-tenant-boundary",
        external_customer_id="external-customer-42",
    )

    assert purchase.tenant_id is None
    assert purchase.external_customer_id == "external-customer-42"
