from __future__ import annotations

import hashlib
import hmac
import json
from datetime import UTC, datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient

from kordena_fiscal.persistence.cakto import SqliteCaktoCommercialDatabase
from kordena_fiscal.product.cakto import CaktoWebhookReceiver, CaktoWebhookVerifier
from kordena_fiscal.runtime.api import create_runtime_app
from kordena_fiscal.runtime.cakto import build_cakto_webhook_router
from kordena_fiscal.runtime.config import RuntimeSettings

NOW = datetime.now(UTC)
SECRET = b"test-only-webhook-key"


def _payload() -> bytes:
    return json.dumps(
        {
            "secret": "secondary-body-secret-not-persisted",
            "event": "purchase_approved",
            "data": {
                "id": "order-http-1",
                "status": "paid",
                "customer": {"id": 12345},
                "product": {"id": "product-http-1"},
                "offer": {"id": "offer-http-1"},
                "createdAt": NOW.isoformat(),
                "paidAt": NOW.isoformat(),
            },
        },
        separators=(",", ":"),
    ).encode()


def _headers(body: bytes) -> dict[str, str]:
    timestamp = str(int(NOW.timestamp()))
    signature = hmac.new(
        SECRET,
        timestamp.encode() + b"." + body,
        hashlib.sha256,
    ).hexdigest()
    return {
        "X-Cakto-Timestamp": timestamp,
        "X-Cakto-Signature": f"v1={signature}",
    }


def _receiver(tmp_path) -> CaktoWebhookReceiver:
    database = SqliteCaktoCommercialDatabase(tmp_path / "http-cakto.sqlite3")
    database.initialize()
    return CaktoWebhookReceiver(
        verifier=CaktoWebhookVerifier(SECRET),
        unit_of_work_factory=database,
    )


def test_runtime_does_not_expose_cakto_webhook_without_explicit_injection() -> None:
    client = TestClient(create_runtime_app(RuntimeSettings.from_mapping({})))

    profile = client.get("/runtime/profile")
    response = client.post("/webhooks/cakto", content=b"{}")

    assert profile.status_code == 200
    assert profile.json()["cakto_webhook_configured"] is False
    assert response.status_code == 404


def test_runtime_accepts_authenticated_cakto_webhook_only_after_injection(tmp_path) -> None:
    receiver = _receiver(tmp_path)
    app = create_runtime_app(
        RuntimeSettings.from_mapping({}),
        cakto_receiver=receiver,
    )
    client = TestClient(app)
    body = _payload()

    response = client.post(
        "/webhooks/cakto",
        content=body,
        headers=_headers(body),
    )

    assert response.status_code == 202
    assert response.json() == {"status": "accepted", "accepted": 1}
    assert client.get("/runtime/profile").json()["cakto_webhook_configured"] is True


def test_http_boundary_rejects_missing_or_invalid_authentication(tmp_path) -> None:
    receiver = _receiver(tmp_path)
    app = create_runtime_app(
        RuntimeSettings.from_mapping({}),
        cakto_receiver=receiver,
    )
    client = TestClient(app)
    body = _payload()

    missing = client.post("/webhooks/cakto", content=body)
    invalid = client.post(
        "/webhooks/cakto",
        content=body,
        headers={
            "X-Cakto-Timestamp": str(int(NOW.timestamp())),
            "X-Cakto-Signature": "v1=invalid",
        },
    )

    assert missing.status_code == 401
    assert invalid.status_code == 401
    assert "signature" not in invalid.text.casefold()


def test_isolated_router_returns_400_for_authenticated_malformed_payload(tmp_path) -> None:
    receiver = _receiver(tmp_path)
    app = FastAPI()
    app.include_router(build_cakto_webhook_router(receiver, clock=lambda: NOW))
    client = TestClient(app)
    body = b'{"secret":"x","event":"purchase_approved","data":{}}'
    headers = _headers(body)

    response = client.post("/webhooks/cakto", content=body, headers=headers)

    assert response.status_code == 400
    assert response.json() == {"detail": "Cakto webhook payload rejected"}
