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
    CaktoEntitlementStatus,
    CaktoPlanBinding,
    commercial_tenant_id,
)
from kordena_fiscal.runtime.cakto import compose_cakto_commercial_runtime

NOW = datetime(2026, 9, 16, 16, 30, tzinfo=UTC)
SECRET = b"cl05-test-only-webhook-secret"
PRODUCT_ID = "nfcore-product"
OFFER_ID = "nfcore-offer"
CUSTOMER_ID = "481920"


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
        "customer": {"id": CUSTOMER_ID, "name": "CL05 Customer"},
        "product": {"id": PRODUCT_ID, "name": "NFCORE"},
        "offer": {"id": OFFER_ID, "name": "NFCORE V1", "price": 100.0},
        "subscription": {"status": "active"},
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


def test_composed_runtime_ingests_and_processes_approved_purchase(tmp_path: Path) -> None:
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
    assert result.claimed == 1
    assert result.succeeded == 1
    tenant_id = commercial_tenant_id(CUSTOMER_ID)
    with database() as uow:
        entitlement = uow.commercial.get_cakto_entitlement(
            tenant_id,
            "nfcore-commercial-v1",
        )
    assert entitlement is not None
    assert entitlement.status is CaktoEntitlementStatus.ACTIVE
    assert entitlement.entitlement_ids == ("portal", "fiscal-core")


def test_composed_runtime_rejects_invalid_signature_before_persistence(tmp_path: Path) -> None:
    database = _database(tmp_path)
    runtime = compose_cakto_commercial_runtime(
        database=database,
        webhook_secret=SECRET,
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


def test_composition_rejects_missing_webhook_secret(tmp_path: Path) -> None:
    database = _database(tmp_path)

    with pytest.raises(CaktoAuthenticationError, match="non-empty bytes"):
        compose_cakto_commercial_runtime(
            database=database,
            webhook_secret=b"",
        )


def test_composed_runtime_has_no_fiscal_authority_surface(tmp_path: Path) -> None:
    runtime = compose_cakto_commercial_runtime(
        database=_database(tmp_path),
        webhook_secret=SECRET,
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
