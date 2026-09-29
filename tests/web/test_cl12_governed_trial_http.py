from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from fastapi import FastAPI
from fastapi.testclient import TestClient

from kordena_fiscal.security.human_recovery import IssuedPasswordReset
from kordena_fiscal.security.s2s import (
    FixedWindowRateLimiter,
    InMemoryWebhookKeyRing,
    WebhookSecurity,
)
from kordena_fiscal.web.commercial_trial import create_commercial_trial_router

SECRET = b"cl12-governed-trial-secret-material-2026"
KEY_ID = "site-fm-trial-v1"


@dataclass
class _Started:
    replay: bool
    expires_at: datetime
    activation_reset: IssuedPasswordReset | None


class _TrialService:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def begin(self, **kwargs):
        self.calls.append(kwargs)
        return _Started(
            replay=False,
            expires_at=datetime.now(UTC) + timedelta(days=14),
            activation_reset=IssuedPasswordReset(
                reset_token="trial-reset-secret-token",
                account_id="account-trial",
                expires_at=datetime.now(UTC) + timedelta(hours=1),
            ),
        )


class _Delivery:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def deliver(self, *, email: str, reset: IssuedPasswordReset) -> None:
        self.calls.append((email, reset.account_id))


def _security() -> WebhookSecurity:
    return WebhookSecurity(
        key_resolver=InMemoryWebhookKeyRing(
            active_key_id=KEY_ID,
            keys={KEY_ID: SECRET},
        ),
        signing_key_id=KEY_ID,
        max_age_seconds=300,
        max_future_skew_seconds=30,
    )


def _body() -> bytes:
    return json.dumps(
        {
            "plan_id": "growth",
            "price_id": "growth-monthly",
            "buyer_email": "owner@example.com",
            "legal_name": "ACME Trial LTDA",
        },
        separators=(",", ":"),
    ).encode()


def test_trial_http_requires_signature_rejects_extra_authority_and_delivers_activation() -> None:
    service = _TrialService()
    delivery = _Delivery()
    security = _security()
    app = FastAPI()
    app.include_router(
        create_commercial_trial_router(
            service,  # type: ignore[arg-type]
            security=security,
            rate_limiter=FixedWindowRateLimiter(
                max_requests=10,
                window_seconds=3600,
            ),
            delivery=delivery,
        )
    )
    client = TestClient(app)
    body = _body()

    unsigned = client.post(
        "/v1/commercial/trials",
        content=body,
        headers={"Idempotency-Key": "cl12-http-idempotency-001"},
    )
    assert unsigned.status_code == 401

    signature = security.sign(body, now=datetime.now(UTC))
    created = client.post(
        "/v1/commercial/trials",
        content=body,
        headers={
            "Content-Type": "application/json",
            "Idempotency-Key": "cl12-http-idempotency-001",
            "X-NFCore-Signature": signature.header_value,
        },
    )
    assert created.status_code == 201
    assert created.json()["status"] == "trial_activation_pending"
    assert "reset_token" not in created.text
    assert "tenant" not in created.text
    assert delivery.calls == [("owner@example.com", "account-trial")]

    privileged = json.loads(body)
    privileged["production_approved"] = True
    privileged_body = json.dumps(privileged, separators=(",", ":")).encode()
    privileged_signature = security.sign(privileged_body, now=datetime.now(UTC))
    rejected = client.post(
        "/v1/commercial/trials",
        content=privileged_body,
        headers={
            "Content-Type": "application/json",
            "Idempotency-Key": "cl12-http-idempotency-002",
            "X-NFCore-Signature": privileged_signature.header_value,
        },
    )
    assert rejected.status_code == 400


def test_trial_http_rate_limits_authenticated_site_key() -> None:
    service = _TrialService()
    delivery = _Delivery()
    security = _security()
    app = FastAPI()
    app.include_router(
        create_commercial_trial_router(
            service,  # type: ignore[arg-type]
            security=security,
            rate_limiter=FixedWindowRateLimiter(
                max_requests=1,
                window_seconds=3600,
            ),
            delivery=delivery,
        )
    )
    client = TestClient(app)
    body = _body()

    signature = security.sign(body, now=datetime.now(UTC))
    first = client.post(
        "/v1/commercial/trials",
        content=body,
        headers={
            "Content-Type": "application/json",
            "Idempotency-Key": "cl12-http-rate-0001",
            "X-NFCore-Signature": signature.header_value,
        },
    )
    assert first.status_code == 201

    signature2 = security.sign(body, now=datetime.now(UTC))
    second = client.post(
        "/v1/commercial/trials",
        content=body,
        headers={
            "Content-Type": "application/json",
            "Idempotency-Key": "cl12-http-rate-0002",
            "X-NFCore-Signature": signature2.header_value,
        },
    )
    assert second.status_code == 429
