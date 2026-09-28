from __future__ import annotations

import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from kordena_fiscal.persistence.cakto import SqliteCaktoCommercialDatabase
from kordena_fiscal.product.cakto import (
    CaktoAuthenticationError,
    CaktoExternalSubscriptionStatus,
    CaktoPlanBinding,
    CaktoReconciliationResult,
    CaktoReconciliationSnapshot,
    CaktoWebhookInboxEntry,
)
from kordena_fiscal.runtime.cakto import compose_cakto_commercial_runtime

NOW = datetime(2026, 9, 16, 16, 30, tzinfo=UTC)
SECRET = b"cl05-test-only-webhook-secret"
PRODUCT_ID = "nfcore-product"
OFFER_ID = "nfcore-offer"
CUSTOMER_ID = "481920"


class CanonicalBridge:
    def __init__(self) -> None:
        self.process_count = 0

    def process(self, entry: CaktoWebhookInboxEntry, binding: CaktoPlanBinding) -> str:
        self.process_count += 1
        assert binding.plan_id == "nfcore-commercial-v1"
        assert entry.external_customer_id == CUSTOMER_ID
        return "canonical_purchase:purchase-1:unclaimed"

    def reconcile(
        self,
        snapshot: CaktoReconciliationSnapshot,
        binding: CaktoPlanBinding,
    ) -> CaktoReconciliationResult:
        assert binding.plan_id == "nfcore-commercial-v1"
        return CaktoReconciliationResult(
            canonical_purchase_id="purchase-1",
            external_status=snapshot.status,
            canonical_status="active",
            drift=False,
        )


def _database(tmp_path: Path) -> SqliteCaktoCommercialDatabase:
    return SqliteCaktoCommercialDatabase(tmp_path / "cl05-cakto.sqlite3")


def _binding() -> CaktoPlanBinding:
    return CaktoPlanBinding(
        external_product_id=PRODUCT_ID,
        external_offer_id=OFFER_ID,
        plan_id="nfcore-commercial-v1",
        entitlement_ids=("portal", "fiscal-core"),
    )


def _order(*, order_id: str, status: str = "paid") -> dict[str, object]:
    return {
        "id": order_id,
        "status": status,
        "callback": "acq-0123456789abcdef0123456789abcdef",
        "customer": {"id": CUSTOMER_ID, "name": "CL05 Customer"},
        "product": {"id": PRODUCT_ID, "name": "NFCORE"},
        "offer": {"id": OFFER_ID, "name": "NFCORE V1", "price": 100.0},
        "subscription": {"id": "sub-cl05", "status": "active"},
        "createdAt": (NOW - timedelta(seconds=5)).isoformat(),
        "paidAt": (NOW - timedelta(seconds=4)).isoformat(),
        "refundedAt": None,
        "chargedbackAt": None,
        "canceledAt": None,
    }


def _signed_payload(event: str, data: object) -> tuple[bytes, str, str]:
    body = json.dumps(
        {"secret": "body-secret-must-never-persist", "event": event, "data": data},
        separators=(",", ":"),
    ).encode()
    timestamp = str(int(NOW.timestamp()))
    digest = hmac.new(
        SECRET,
        timestamp.encode() + b"." + body,
        hashlib.sha256,
    ).hexdigest()
    return body, timestamp, f"v1={digest}"


def test_composed_runtime_ingests_and_delegates_approved_purchase(tmp_path: Path) -> None:
    database = _database(tmp_path)
    bridge = CanonicalBridge()
    runtime = compose_cakto_commercial_runtime(
        database=database,
        webhook_secret=SECRET,
        canonical_bridge=bridge,
    )
    with database() as uow:
        uow.commercial.put_cakto_plan_binding(_binding())
        uow.commit()

    body, timestamp, signature = _signed_payload(
        "purchase_approved",
        _order(order_id="approved-1"),
    )
    accepted = runtime.receiver.receive(
        raw_body=body,
        timestamp_header=timestamp,
        signature_header=signature,
        received_at=NOW,
    )
    result = runtime.processor.process_due(now=NOW)

    assert len(accepted) == 1
    assert accepted[0].callback_token is not None
    assert accepted[0].external_subscription_id == "sub-cl05"
    assert result.claimed == 1
    assert result.succeeded == 1
    assert bridge.process_count == 1
    with database() as uow:
        assert uow.commercial.get_cakto_tenant_by_customer(CUSTOMER_ID) is None


def test_composed_runtime_rejects_invalid_signature_before_persistence(tmp_path: Path) -> None:
    database = _database(tmp_path)
    runtime = compose_cakto_commercial_runtime(
        database=database,
        webhook_secret=SECRET,
        canonical_bridge=CanonicalBridge(),
    )
    body, timestamp, _signature = _signed_payload(
        "purchase_approved",
        _order(order_id="rejected-signature"),
    )

    with pytest.raises(CaktoAuthenticationError, match="signature"):
        runtime.receiver.receive(
            raw_body=body,
            timestamp_header=timestamp,
            signature_header="v1=invalid",
            received_at=NOW,
        )

    with database() as uow:
        assert uow.commercial.list_due_cakto_events(NOW, 100) == ()


def test_composition_without_canonical_bridge_fails_closed_during_processing(
    tmp_path: Path,
) -> None:
    database = _database(tmp_path)
    runtime = compose_cakto_commercial_runtime(
        database=database,
        webhook_secret=SECRET,
    )
    with database() as uow:
        uow.commercial.put_cakto_plan_binding(_binding())
        uow.commit()
    body, timestamp, signature = _signed_payload(
        "purchase_approved",
        _order(order_id="no-bridge"),
    )
    runtime.receiver.receive(
        raw_body=body,
        timestamp_header=timestamp,
        signature_header=signature,
        received_at=NOW,
    )

    result = runtime.processor.process_due(now=NOW)
    assert result.retry_wait == 1


def test_composition_rejects_missing_webhook_secret(tmp_path: Path) -> None:
    with pytest.raises(CaktoAuthenticationError, match="non-empty bytes"):
        compose_cakto_commercial_runtime(
            database=_database(tmp_path),
            webhook_secret=b"",
        )


def test_composed_runtime_has_no_fiscal_authority_surface(tmp_path: Path) -> None:
    runtime = compose_cakto_commercial_runtime(
        database=_database(tmp_path),
        webhook_secret=SECRET,
        canonical_bridge=CanonicalBridge(),
    )
    forbidden = {
        "production_approval",
        "production_activation",
        "homologation",
        "certificate",
        "csc",
        "fiscal_authority",
    }
    exposed = set(dir(runtime)) | set(dir(runtime.receiver)) | set(dir(runtime.processor))
    assert forbidden.isdisjoint(exposed)


def test_composed_reconciliation_uses_canonical_bridge(tmp_path: Path) -> None:
    database = _database(tmp_path)
    runtime = compose_cakto_commercial_runtime(
        database=database,
        webhook_secret=SECRET,
        canonical_bridge=CanonicalBridge(),
    )
    with database() as uow:
        uow.commercial.put_cakto_plan_binding(_binding())
        uow.commit()

    result = runtime.processor.reconcile(
        CaktoReconciliationSnapshot(
            external_customer_id=CUSTOMER_ID,
            external_product_id=PRODUCT_ID,
            external_offer_id=OFFER_ID,
            status=CaktoExternalSubscriptionStatus.ACTIVE,
            observed_at=NOW,
            external_subscription_id="sub-cl05",
        )
    )
    assert result.canonical_purchase_id == "purchase-1"
    assert result.drift is False
