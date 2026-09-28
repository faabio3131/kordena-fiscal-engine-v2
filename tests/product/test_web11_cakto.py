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
    CaktoExternalSubscriptionStatus,
    CaktoInboxStatus,
    CaktoPayloadError,
    CaktoPlanBinding,
    CaktoReconciliationResult,
    CaktoReconciliationSnapshot,
    CaktoStateConflictError,
    CaktoWebhookEvent,
    CaktoWebhookInboxEntry,
    CaktoWebhookReceiver,
    CaktoWebhookVerifier,
)

NOW = datetime(2026, 9, 15, 20, 10, tzinfo=UTC)
SECRET = b"test-only-cakto-webhook-secret"
PRODUCT_ID = "cd287b31-d4b7-4e94-858a-96e05ce2f4a2"
OFFER_ID = "a8BcHrY"
ACQUISITION = "acq-0123456789abcdef0123456789abcdef"


def _order(
    *,
    order_id: str = "order-1",
    customer_id: int = 481920,
    status: str = "paid",
    created_at: datetime = NOW - timedelta(seconds=5),
    paid_at: datetime | None = NOW - timedelta(seconds=4),
    callback: str | None = ACQUISITION,
    subscription_id: str | None = "sub-1",
) -> dict[str, object]:
    payload: dict[str, object] = {
        "id": order_id,
        "refId": "4852F91",
        "status": status,
        "offer_type": "main",
        "checkoutUrl": f"https://pay.cakto.com.br/{OFFER_ID}",
        "customer": {"id": customer_id, "name": "Test Customer"},
        "product": {"id": PRODUCT_ID, "short_id": "42bruPi", "name": "NFCore"},
        "offer": {"id": OFFER_ID, "name": "NFCore SaaS", "price": 100.0},
        "subscription": {
            "id": subscription_id,
            "status": "active",
        },
        "createdAt": created_at.isoformat(),
        "paidAt": None if paid_at is None else paid_at.isoformat(),
        "refundedAt": None,
        "chargedbackAt": None,
        "canceledAt": None,
    }
    if callback is not None:
        payload["callback"] = callback
    return payload


def _body(event: str, data: object, *, body_secret: str = "secret-must-not-persist") -> bytes:
    return json.dumps(
        {"secret": body_secret, "event": event, "data": data},
        separators=(",", ":"),
    ).encode()


def _headers(body: bytes, *, timestamp: datetime = NOW) -> tuple[str, str]:
    raw_timestamp = str(int(timestamp.timestamp()))
    digest = hmac.new(
        SECRET,
        raw_timestamp.encode() + b"." + body,
        hashlib.sha256,
    ).hexdigest()
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
        plan_id="nfcore-pro",
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
) -> tuple[CaktoWebhookInboxEntry, ...]:
    body = _body(event, data)
    timestamp_header, signature = _headers(body, timestamp=timestamp)
    return _receiver(database).receive(
        raw_body=body,
        timestamp_header=timestamp_header,
        signature_header=signature,
        received_at=timestamp,
    )


class RecordingCanonicalBridge:
    def __init__(self) -> None:
        self.processed: list[tuple[CaktoWebhookInboxEntry, CaktoPlanBinding]] = []
        self.reconciled: list[tuple[CaktoReconciliationSnapshot, CaktoPlanBinding]] = []

    def process(
        self,
        entry: CaktoWebhookInboxEntry,
        binding: CaktoPlanBinding,
    ) -> str:
        self.processed.append((entry, binding))
        return "canonical_purchase:purchase-1:unclaimed"

    def reconcile(
        self,
        snapshot: CaktoReconciliationSnapshot,
        binding: CaktoPlanBinding,
    ) -> CaktoReconciliationResult:
        self.reconciled.append((snapshot, binding))
        return CaktoReconciliationResult(
            canonical_purchase_id="purchase-1",
            external_status=snapshot.status,
            canonical_status="active",
            drift=snapshot.status is not CaktoExternalSubscriptionStatus.ACTIVE,
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


def test_inbox_is_idempotent_sanitized_and_persists_correlation_only(tmp_path) -> None:
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

    assert second[0] == first[0]
    assert first[0].callback_token == ACQUISITION
    assert first[0].external_subscription_id == "sub-1"
    stored = database.path.read_bytes()
    assert b"NEVER-PERSIST-THIS-SECRET" not in stored
    assert b"Test Customer" not in stored


def test_callback_rejects_unsafe_characters(tmp_path) -> None:
    database = _database(tmp_path)
    body = _body("purchase_approved", _order(callback="acq-bad/value"))
    timestamp, signature = _headers(body)

    with pytest.raises(CaktoPayloadError, match="callback"):
        _receiver(database).receive(
            raw_body=body,
            timestamp_header=timestamp,
            signature_header=signature,
            received_at=NOW,
        )


def test_processor_delegates_paid_event_to_canonical_bridge_without_local_authority(
    tmp_path,
) -> None:
    database = _database(tmp_path)
    bridge = RecordingCanonicalBridge()
    with database() as uow:
        uow.commercial.put_cakto_plan_binding(_binding())
        uow.commit()
    _receive(database, "purchase_approved", _order())

    result = CaktoCommercialProcessor(
        unit_of_work_factory=database,
        canonical_bridge=bridge,
    ).process_due(now=NOW)

    assert result.succeeded == 1
    assert len(bridge.processed) == 1
    entry, binding = bridge.processed[0]
    assert entry.callback_token == ACQUISITION
    assert entry.external_customer_id == "481920"
    assert binding.plan_id == "nfcore-pro"

    with database() as uow:
        assert uow.commercial.get_cakto_tenant_by_customer("481920") is None
        assert uow.commercial.get_cakto_entitlement("anything", "nfcore-pro") is None
        stored_event = uow.commercial.get_cakto_event("purchase_approved:order-1")
    assert stored_event is not None
    assert stored_event.status is CaktoInboxStatus.PROCESSED
    assert stored_event.tenant_id is None
    assert stored_event.outcome_reference == "canonical_purchase:purchase-1:unclaimed"


def test_processor_without_canonical_bridge_retries_then_dead_letters(tmp_path) -> None:
    database = _database(tmp_path)
    with database() as uow:
        uow.commercial.put_cakto_plan_binding(_binding())
        uow.commit()
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


def test_missing_mapping_still_retries_before_canonical_bridge(tmp_path) -> None:
    database = _database(tmp_path)
    bridge = RecordingCanonicalBridge()
    _receive(database, "purchase_approved", _order())
    result = CaktoCommercialProcessor(
        unit_of_work_factory=database,
        canonical_bridge=bridge,
    ).process_due(now=NOW)

    assert result.retry_wait == 1
    assert bridge.processed == []


def test_informational_event_never_calls_canonical_bridge(tmp_path) -> None:
    database = _database(tmp_path)
    bridge = RecordingCanonicalBridge()
    abandonment = {
        "offer": {"id": OFFER_ID, "name": "Offer", "price": 100},
        "product": {"id": PRODUCT_ID, "name": "NFCore"},
        "customerName": "Abandoned",
        "customerEmail": "abandoned@example.com",
        "customerCellphone": None,
        "checkoutUrl": f"https://pay.cakto.com.br/{OFFER_ID}",
        "createdAt": NOW.isoformat(),
    }
    _receive(database, "checkout_abandonment", abandonment)

    result = CaktoCommercialProcessor(
        unit_of_work_factory=database,
        canonical_bridge=bridge,
    ).process_due(now=NOW)

    assert result.succeeded == 1
    assert bridge.processed == []


def test_reconciliation_delegates_to_canonical_bridge_and_reports_drift(tmp_path) -> None:
    database = _database(tmp_path)
    bridge = RecordingCanonicalBridge()
    with database() as uow:
        uow.commercial.put_cakto_plan_binding(_binding())
        uow.commit()

    result = CaktoCommercialProcessor(
        unit_of_work_factory=database,
        canonical_bridge=bridge,
    ).reconcile(
        CaktoReconciliationSnapshot(
            external_customer_id="481920",
            external_product_id=PRODUCT_ID,
            external_offer_id=OFFER_ID,
            status=CaktoExternalSubscriptionStatus.PAUSED,
            observed_at=NOW,
            external_subscription_id="sub-1",
        )
    )

    assert result.canonical_purchase_id == "purchase-1"
    assert result.canonical_status == "active"
    assert result.drift is True
    assert len(bridge.reconciled) == 1


def test_legacy_commercial_models_have_no_fiscal_activation_surface() -> None:
    assert "fiscal" not in CaktoCommercialEntitlement.__dataclass_fields__
    assert "fiscal" not in CaktoCommercialTenant.__dataclass_fields__
