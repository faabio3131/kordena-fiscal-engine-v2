from __future__ import annotations

import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta

import pytest

from kordena_fiscal.persistence.cakto import SqliteCaktoCommercialDatabase
from kordena_fiscal.product.cakto import (
    CaktoAuthenticationError,
    CaktoCommercialEntitlement,
    CaktoCommercialProcessor,
    CaktoCommercialTenant,
    CaktoEntitlementStatus,
    CaktoExternalSubscriptionStatus,
    CaktoInboxStatus,
    CaktoPayloadError,
    CaktoPlanBinding,
    CaktoReconciliationSnapshot,
    CaktoStateConflictError,
    CaktoWebhookEvent,
    CaktoWebhookReceiver,
    CaktoWebhookVerifier,
    commercial_tenant_id,
)

NOW = datetime(2026, 9, 15, 20, 10, tzinfo=UTC)
SECRET = b"test-only-cakto-webhook-secret"
PRODUCT_ID = "cd287b31-d4b7-4e94-858a-96e05ce2f4a2"
OFFER_ID = "a8BcHrY"


def _order(
    *,
    order_id: str = "order-1",
    customer_id: int = 481920,
    status: str = "paid",
    created_at: datetime = NOW - timedelta(seconds=5),
    paid_at: datetime | None = NOW - timedelta(seconds=4),
) -> dict[str, object]:
    return {
        "id": order_id,
        "refId": "4852F91",
        "status": status,
        "offer_type": "main",
        "checkoutUrl": f"https://pay.cakto.com.br/{OFFER_ID}",
        "customer": {"id": customer_id, "name": "Test Customer"},
        "product": {"id": PRODUCT_ID, "short_id": "42bruPi", "name": "Kordena"},
        "offer": {"id": OFFER_ID, "name": "Kordena SaaS", "price": 100.0},
        "subscription": {"status": "active"},
        "createdAt": created_at.isoformat(),
        "paidAt": None if paid_at is None else paid_at.isoformat(),
        "refundedAt": None,
        "chargedbackAt": None,
        "canceledAt": None,
    }


def _body(event: str, data: object, *, body_secret: str = "secret-must-not-persist") -> bytes:
    return json.dumps(
        {"secret": body_secret, "event": event, "data": data},
        separators=(",", ":"),
    ).encode()


def _headers(body: bytes, *, timestamp: datetime = NOW) -> tuple[str, str]:
    raw_timestamp = str(int(timestamp.timestamp()))
    digest = hmac.new(SECRET, raw_timestamp.encode() + b"." + body, hashlib.sha256).hexdigest()
    return raw_timestamp, f"v1={digest}"


def _database(tmp_path) -> SqliteCaktoCommercialDatabase:
    database = SqliteCaktoCommercialDatabase(tmp_path / "cakto.sqlite3")
    assert database.initialize() is True
    assert database.initialize() is False
    return database


def _binding() -> CaktoPlanBinding:
    return CaktoPlanBinding(
        external_product_id=PRODUCT_ID,
        external_offer_id=OFFER_ID,
        plan_id="kordena-pro",
        entitlement_ids=("portal", "fiscal-core"),
    )


def _receiver(database: SqliteCaktoCommercialDatabase) -> CaktoWebhookReceiver:
    return CaktoWebhookReceiver(
        verifier=CaktoWebhookVerifier(SECRET),
        unit_of_work_factory=database,
    )


def _receive(
    database: SqliteCaktoCommercialDatabase,
    event: str,
    data: object,
    *,
    timestamp: datetime = NOW,
) -> None:
    body = _body(event, data)
    timestamp_header, signature = _headers(body, timestamp=timestamp)
    _receiver(database).receive(
        raw_body=body,
        timestamp_header=timestamp_header,
        signature_header=signature,
        received_at=timestamp,
    )


def test_verifier_rejects_invalid_signature_replay_and_unknown_event(tmp_path) -> None:
    database = _database(tmp_path)
    body = _body("purchase_approved", _order())
    timestamp, signature = _headers(body)
    receiver = _receiver(database)

    with pytest.raises(CaktoAuthenticationError, match="signature"):
        receiver.receive(
            raw_body=body,
            timestamp_header=timestamp,
            signature_header="v1=bad",
            received_at=NOW,
        )

    with pytest.raises(CaktoAuthenticationError, match="replay tolerance"):
        receiver.receive(
            raw_body=body,
            timestamp_header=timestamp,
            signature_header=signature,
            received_at=NOW + timedelta(minutes=6),
        )

    unknown = _body("made_up_event", _order())
    unknown_timestamp, unknown_signature = _headers(unknown)
    with pytest.raises(CaktoPayloadError, match="unsupported"):
        receiver.receive(
            raw_body=unknown,
            timestamp_header=unknown_timestamp,
            signature_header=unknown_signature,
            received_at=NOW,
        )


def test_durable_inbox_is_idempotent_and_never_persists_body_secret(tmp_path) -> None:
    database = _database(tmp_path)
    body = _body("purchase_approved", _order(), body_secret="NEVER-PERSIST-THIS-SECRET")
    timestamp, signature = _headers(body)
    receiver = _receiver(database)

    first = receiver.receive(
        raw_body=body,
        timestamp_header=timestamp,
        signature_header=signature,
        received_at=NOW,
    )
    second = receiver.receive(
        raw_body=body,
        timestamp_header=timestamp,
        signature_header=signature,
        received_at=NOW,
    )

    assert first[0].event_key == "purchase_approved:order-1"
    assert second[0].event_key == first[0].event_key
    assert b"NEVER-PERSIST-THIS-SECRET" not in database.path.read_bytes()

    changed = _body("purchase_approved", {**_order(), "status": "refunded"})
    changed_timestamp, changed_signature = _headers(changed)
    with pytest.raises(CaktoStateConflictError, match="different content"):
        receiver.receive(
            raw_body=changed,
            timestamp_header=changed_timestamp,
            signature_header=changed_signature,
            received_at=NOW,
        )


def test_v2_batch_and_abandonment_contract_are_accepted(tmp_path) -> None:
    database = _database(tmp_path)
    batch = [_order(order_id="order-1"), _order(order_id="order-2", customer_id=481921)]
    body = _body("purchase_approved", batch)
    timestamp, signature = _headers(body)
    accepted = _receiver(database).receive(
        raw_body=body,
        timestamp_header=timestamp,
        signature_header=signature,
        received_at=NOW,
    )
    assert {entry.order_id for entry in accepted} == {"order-1", "order-2"}

    abandonment = {
        "offer": {"id": OFFER_ID, "name": "Offer", "price": 100},
        "product": {"id": PRODUCT_ID, "name": "Kordena"},
        "customerName": "Abandoned",
        "customerEmail": "abandoned@example.com",
        "customerCellphone": None,
        "checkoutUrl": f"https://pay.cakto.com.br/{OFFER_ID}",
        "createdAt": NOW.isoformat(),
    }
    abandonment_body = _body("checkout_abandonment", abandonment)
    abandonment_timestamp, abandonment_signature = _headers(abandonment_body)
    accepted_abandonment = _receiver(database).receive(
        raw_body=abandonment_body,
        timestamp_header=abandonment_timestamp,
        signature_header=abandonment_signature,
        received_at=NOW,
    )
    assert accepted_abandonment[0].event_type is CaktoWebhookEvent.CHECKOUT_ABANDONMENT
    assert "abandoned@example.com" not in accepted_abandonment[0].event_key


def test_confirmed_purchase_provisions_commercial_tenant_and_entitlement_only(tmp_path) -> None:
    database = _database(tmp_path)
    binding = _binding()
    with database() as uow:
        uow.commercial.put_cakto_plan_binding(binding)
        uow.commit()
    assert binding.checkout_url == f"https://pay.cakto.com.br/{OFFER_ID}"

    _receive(database, "purchase_approved", _order())
    result = CaktoCommercialProcessor(unit_of_work_factory=database).process_due(now=NOW)
    assert result.claimed == 1
    assert result.succeeded == 1

    tenant_id = commercial_tenant_id("481920")
    with database() as uow:
        tenant = uow.commercial.get_cakto_tenant_by_customer("481920")
        entitlement = uow.commercial.get_cakto_entitlement(tenant_id, "kordena-pro")
        event = uow.commercial.get_cakto_event("purchase_approved:order-1")
    assert tenant is not None and tenant.tenant_id == tenant_id
    assert entitlement is not None
    assert entitlement.status is CaktoEntitlementStatus.ACTIVE
    assert entitlement.entitlement_ids == ("portal", "fiscal-core")
    assert event is not None and event.status is CaktoInboxStatus.PROCESSED


def test_unpaid_grant_event_cannot_activate_entitlement(tmp_path) -> None:
    database = _database(tmp_path)
    with database() as uow:
        uow.commercial.put_cakto_plan_binding(_binding())
        uow.commit()
    _receive(database, "subscription_created", _order(status="waiting_payment", paid_at=None))
    result = CaktoCommercialProcessor(unit_of_work_factory=database).process_due(now=NOW)
    assert result.succeeded == 1
    with database() as uow:
        assert uow.commercial.get_cakto_tenant_by_customer("481920") is None
        event = uow.commercial.get_cakto_event("subscription_created:order-1")
    assert event is not None
    assert event.outcome_reference == "no_entitlement_change"


def test_out_of_order_event_is_ignored_without_reversing_newer_state(tmp_path) -> None:
    database = _database(tmp_path)
    with database() as uow:
        uow.commercial.put_cakto_plan_binding(_binding())
        uow.commit()

    purchase = _order(created_at=NOW - timedelta(minutes=10), paid_at=NOW - timedelta(minutes=9))
    _receive(database, "purchase_approved", purchase)
    processor = CaktoCommercialProcessor(unit_of_work_factory=database)
    processor.process_due(now=NOW)

    canceled = _order(order_id="order-2", created_at=NOW - timedelta(minutes=2))
    canceled["canceledAt"] = (NOW - timedelta(minutes=1)).isoformat()
    _receive(database, "subscription_canceled", canceled)
    processor.process_due(now=NOW)

    stale_resumed = _order(
        order_id="order-3",
        created_at=NOW - timedelta(minutes=5),
        paid_at=NOW - timedelta(minutes=5),
    )
    _receive(database, "subscription_resumed", stale_resumed)
    result = processor.process_due(now=NOW)
    assert result.stale_ignored == 1

    with database() as uow:
        entitlement = uow.commercial.get_cakto_entitlement(
            commercial_tenant_id("481920"), "kordena-pro"
        )
    assert entitlement is not None
    assert entitlement.status is CaktoEntitlementStatus.CANCELED


def test_missing_mapping_retries_then_dead_letters(tmp_path) -> None:
    database = _database(tmp_path)
    _receive(database, "purchase_approved", _order())
    processor = CaktoCommercialProcessor(unit_of_work_factory=database)

    now = NOW
    for expected_attempt in range(1, 6):
        result = processor.process_due(now=now)
        with database() as uow:
            event = uow.commercial.get_cakto_event("purchase_approved:order-1")
        assert event is not None
        assert event.attempt_count == expected_attempt
        if expected_attempt < 5:
            assert result.retry_wait == 1
            assert event.status is CaktoInboxStatus.RETRY_WAIT
            assert event.next_attempt_at is not None
            now = event.next_attempt_at
        else:
            assert result.dead_letter == 1
            assert event.status is CaktoInboxStatus.DEAD_LETTER


def test_cross_tenant_identity_conflict_fails_closed_to_dead_letter(tmp_path) -> None:
    database = _database(tmp_path)
    with database() as uow:
        uow.commercial.put_cakto_plan_binding(_binding())
        uow.commercial.put_cakto_tenant(
            CaktoCommercialTenant(
                tenant_id="wrong-tenant",
                external_customer_id="481920",
                created_at=NOW - timedelta(days=1),
            )
        )
        uow.commit()
    _receive(database, "purchase_approved", _order())
    result = CaktoCommercialProcessor(unit_of_work_factory=database).process_due(now=NOW)
    assert result.dead_letter == 1
    with database() as uow:
        event = uow.commercial.get_cakto_event("purchase_approved:order-1")
    assert event is not None and event.status is CaktoInboxStatus.DEAD_LETTER


def test_reconciliation_maps_only_documented_external_subscription_states(tmp_path) -> None:
    database = _database(tmp_path)
    with database() as uow:
        uow.commercial.put_cakto_plan_binding(_binding())
        uow.commit()
    processor = CaktoCommercialProcessor(unit_of_work_factory=database)
    active = processor.reconcile(
        CaktoReconciliationSnapshot(
            external_customer_id="481920",
            external_product_id=PRODUCT_ID,
            external_offer_id=OFFER_ID,
            status=CaktoExternalSubscriptionStatus.ACTIVE,
            observed_at=NOW,
        )
    )
    assert active.status is CaktoEntitlementStatus.ACTIVE
    paused = processor.reconcile(
        CaktoReconciliationSnapshot(
            external_customer_id="481920",
            external_product_id=PRODUCT_ID,
            external_offer_id=OFFER_ID,
            status=CaktoExternalSubscriptionStatus.PAUSED,
            observed_at=NOW + timedelta(minutes=1),
        )
    )
    assert paused.status is CaktoEntitlementStatus.SUSPENDED


def test_commercial_models_have_no_fiscal_activation_surface() -> None:
    assert "fiscal" not in CaktoCommercialEntitlement.__dataclass_fields__
    assert "fiscal" not in CaktoCommercialTenant.__dataclass_fields__
