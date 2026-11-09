"""Public commercial-acquisition ingress: explicit origin, no browser HMAC."""
import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from kordena_fiscal.product.commercial_fulfillment import CommercialFulfillmentError
from kordena_fiscal.security.s2s import FixedWindowRateLimiter
from kordena_fiscal.web.public_commercial_acquisition import (
    create_public_commercial_acquisition_router,
)


class Acquisition:
    def __init__(self, *, raises: Exception | None = None) -> None:
        self.calls = []
        self._raises = raises

    def begin(self, **kwargs):
        self.calls.append(kwargs)
        if self._raises is not None:
            raise self._raises
        return SimpleNamespace(
            acquisition_reference="acq-synthetic-0001",
            provider_id="cakto",
            checkout_url="https://pay.cakto.com.br/synthetic?callback=acq-synthetic-0001",
            expires_at=datetime.now(UTC) + timedelta(minutes=30),
            replay=False,
        )


def client(service: Acquisition) -> TestClient:
    app = FastAPI()
    app.include_router(create_public_commercial_acquisition_router(
        service,  # type: ignore[arg-type]
        allowed_origins=("https://app.nfcore.com.br",),
        rate_limiter=FixedWindowRateLimiter(max_requests=3, window_seconds=3600),
    ))
    return TestClient(app)


BODY = {
    "plan_id": "starter",
    "price_id": "nfcore-starter-monthly",
    "buyer_email": "a@example.com",
    "legal_name": "ACME LTDA",
}


def test_public_acquisition_requires_approved_origin() -> None:
    service = Acquisition()
    c = client(service)
    headers = {
        "Origin": "https://app.nfcore.com.br",
        "Idempotency-Key": "public-acquisition-0001",
    }
    assert c.post("/v1/public/acquisitions", json=BODY).status_code == 403
    response = c.post("/v1/public/acquisitions", json=BODY, headers=headers)
    assert response.status_code == 201
    assert response.json()["checkout_url"].startswith("https://pay.cakto.com.br/")
    assert response.json()["acquisition_reference"] == "acq-synthetic-0001"
    assert response.headers["access-control-allow-origin"] == headers["Origin"]
    assert len(service.calls) == 1


def test_public_acquisition_rejects_unsigned_browser_authority() -> None:
    service = Acquisition()
    c = client(service)
    headers = {
        "Origin": "https://app.nfcore.com.br",
        "Idempotency-Key": "public-acquisition-0002",
    }
    assert c.post(
        "/v1/public/acquisitions",
        json=BODY,
        headers={**headers, "Authorization": "Bearer forged"},
    ).status_code == 403
    assert c.post(
        "/v1/public/acquisitions",
        json=BODY,
        headers={**headers, "Cookie": "session=forged"},
    ).status_code == 403
    assert service.calls == []


def test_public_acquisition_rejects_oversized_payload() -> None:
    service = Acquisition()
    c = client(service)
    response = c.post(
        "/v1/public/acquisitions",
        content=json.dumps({"x": "a" * 5000}),
        headers={
            "Origin": "https://app.nfcore.com.br",
            "Content-Type": "application/json",
            "Idempotency-Key": "public-acquisition-0003",
        },
    )
    assert response.status_code == 413
    assert service.calls == []


def test_public_acquisition_requires_explicit_https_origin() -> None:
    with pytest.raises(ValueError):
        create_public_commercial_acquisition_router(
            Acquisition(),  # type: ignore[arg-type]
            allowed_origins=("http://app.nfcore.com.br",),
            rate_limiter=FixedWindowRateLimiter(max_requests=1, window_seconds=60),
        )


def test_public_acquisition_cors_preflight_requires_origin_and_restricted_headers() -> None:
    service = Acquisition()
    c = client(service)
    good = {
        "Origin": "https://app.nfcore.com.br",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type,idempotency-key",
    }
    response = c.options("/v1/public/acquisitions", headers=good)
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == good["Origin"]
    denied = c.options(
        "/v1/public/acquisitions",
        headers={**good, "Access-Control-Request-Headers": "authorization"},
    )
    assert denied.status_code == 403
    assert c.options("/v1/public/acquisitions", headers={
        **good, "Origin": "https://attacker.example"
    }).status_code == 403
    assert service.calls == []


@pytest.mark.parametrize(
    "raw",
    (
        b'{"plan_id":"p","plan_id":"forged","price_id":"price","buyer_email":'
        b'"a@example.com","legal_name":"ACME"}',
        b'{"plan_id":"p","price_id":"price","buyer_email":"a@example.com",'
        b'"legal_name":"ACME","extra":{"key":1,"key":2}}',
    ),
)
def test_public_acquisition_rejects_duplicate_json_fields_before_service(raw: bytes) -> None:
    service = Acquisition()
    response = client(service).post(
        "/v1/public/acquisitions",
        content=raw,
        headers={
            "Origin": "https://app.nfcore.com.br",
            "Content-Type": "application/json",
            "Idempotency-Key": "public-acquisition-dup",
        },
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "invalid JSON"}
    assert service.calls == []


@pytest.mark.parametrize("key", ("short-key", " " * 7 + "abcdefgh"))
def test_public_acquisition_rejects_key_shorter_than_canonical_minimum(key: str) -> None:
    service = Acquisition()
    response = client(service).post(
        "/v1/public/acquisitions",
        json=BODY,
        headers={"Origin": "https://app.nfcore.com.br", "Idempotency-Key": key},
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "invalid idempotency key"}
    assert service.calls == []


def test_public_acquisition_streamed_payload_is_bounded_before_parsing() -> None:
    service = Acquisition()
    response = client(service).post(
        "/v1/public/acquisitions",
        content=iter((b'{"plan_id":"p","padding":"', b"x" * 4096, b'"}')),
        headers={
            "Origin": "https://app.nfcore.com.br",
            "Content-Type": "application/json",
            "Idempotency-Key": "public-acquisition-stream-overflow",
        },
    )
    assert response.status_code == 413
    assert service.calls == []


def test_public_acquisition_not_ready_maps_to_503() -> None:
    service = Acquisition(
        raises=CommercialFulfillmentError("commercial purchase path is not operationally ready")
    )
    response = client(service).post(
        "/v1/public/acquisitions",
        json=BODY,
        headers={
            "Origin": "https://app.nfcore.com.br",
            "Idempotency-Key": "public-acquisition-not-ready",
        },
    )
    assert response.status_code == 503
    assert response.json() == {"detail": "commercial purchase path is unavailable"}


def test_public_acquisition_rejected_selection_maps_to_409() -> None:
    service = Acquisition(
        raises=CommercialFulfillmentError("selected commercial plan/price is not available")
    )
    response = client(service).post(
        "/v1/public/acquisitions",
        json=BODY,
        headers={
            "Origin": "https://app.nfcore.com.br",
            "Idempotency-Key": "public-acquisition-rejected",
        },
    )
    assert response.status_code == 409
    assert response.json() == {"detail": "commercial acquisition could not be created"}


def test_public_acquisition_unexpected_error_is_503_without_leak() -> None:
    service = Acquisition(raises=RuntimeError("synthetic-internal-detail"))
    response = client(service).post(
        "/v1/public/acquisitions",
        json=BODY,
        headers={
            "Origin": "https://app.nfcore.com.br",
            "Idempotency-Key": "public-acquisition-internal-error",
        },
    )
    assert response.status_code == 503
    assert "synthetic-internal-detail" not in response.text


def test_public_acquisition_replay_returns_200() -> None:
    class ReplayAcquisition(Acquisition):
        def begin(self, **kwargs):
            self.calls.append(kwargs)
            return SimpleNamespace(
                acquisition_reference="acq-synthetic-0001",
                provider_id="cakto",
                checkout_url="https://pay.cakto.com.br/synthetic?callback=acq-synthetic-0001",
                expires_at=datetime.now(UTC) + timedelta(minutes=30),
                replay=True,
            )

    response = client(ReplayAcquisition()).post(
        "/v1/public/acquisitions",
        json=BODY,
        headers={
            "Origin": "https://app.nfcore.com.br",
            "Idempotency-Key": "public-acquisition-replay",
        },
    )
    assert response.status_code == 200
    assert response.json()["replay"] is True
