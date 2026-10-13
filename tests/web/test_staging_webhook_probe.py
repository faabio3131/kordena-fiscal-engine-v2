"""Directed tests for the staging-only signed receiver (no Railway deploy)."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient

from kordena_fiscal.security.s2s import InMemoryWebhookKeyRing, WebhookSecurity
from kordena_fiscal.web.staging_webhook_probe import (
    MAX_PROBE_BYTES,
    create_staging_webhook_probe_router,
)

KEY_ID = "sec_nfcore_staging_pilot_gsm_signing_01"
KEY = b"staging-webhook-test-only-material-not-a-real-secret-key"


def _client() -> tuple[TestClient, WebhookSecurity]:
    ring = InMemoryWebhookKeyRing(active_key_id=KEY_ID, keys={KEY_ID: KEY})
    security = WebhookSecurity(key_resolver=ring, signing_key_id=KEY_ID)
    app = FastAPI()
    app.include_router(create_staging_webhook_probe_router(security))
    return TestClient(app), security


def test_signed_probe_returns_no_content() -> None:
    client, security = _client()
    payload = b'{"probe":"nfcore-staging"}'
    signature = security.sign(payload, now=datetime.now(UTC)).header_value
    response = client.post(
        "/internal/staging/webhook-probe",
        content=payload,
        headers={"X-FM-Webhook-Signature": signature},
    )
    assert response.status_code == 204
    assert response.content == b""


def test_probe_rejects_missing_and_invalid_signature() -> None:
    client, security = _client()
    payload = b"probe"
    assert client.post("/internal/staging/webhook-probe", content=payload).status_code == 401
    signed = security.sign(payload, now=datetime.now(UTC)).header_value
    assert client.post(
        "/internal/staging/webhook-probe",
        content=b"tampered",
        headers={"X-FM-Webhook-Signature": signed},
    ).status_code == 401


def test_probe_rejects_oversize_body_before_auth() -> None:
    client, _ = _client()
    response = client.post(
        "/internal/staging/webhook-probe",
        content=b"x" * (MAX_PROBE_BYTES + 1),
    )
    assert response.status_code == 413



def test_probe_rejects_expired_signature() -> None:
    from datetime import timedelta

    client, security = _client()
    payload = b"expired"
    old = datetime.now(UTC) - timedelta(minutes=6)
    signature = security.sign(payload, now=old).header_value
    response = client.post(
        "/internal/staging/webhook-probe",
        content=payload,
        headers={"X-FM-Webhook-Signature": signature},
    )
    assert response.status_code == 401


def test_probe_fails_closed_if_verifier_backend_unavailable() -> None:
    client, security = _client()

    def unavailable(*args: object, **kwargs: object) -> None:
        raise RuntimeError("secret backend unreachable")

    security.verify = unavailable  # type: ignore[method-assign]
    response = client.post(
        "/internal/staging/webhook-probe",
        content=b"probe",
        headers={"X-FM-Webhook-Signature": "t=1,kid=invalid,v1=" + "0" * 64},
    )
    assert response.status_code == 401
    assert b"unreachable" not in response.content
