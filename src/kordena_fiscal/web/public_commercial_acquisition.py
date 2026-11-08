"""Opt-in public commercial-acquisition intake for first-party NFCore checkout.

The existing `/v1/commercial/acquisitions` route (commercial_acquisition.py) is
a signed server-to-server boundary: it requires an `X-NFCore-Signature` header
HMAC-signed with `commercial_acquisition_security`, a secret that must never
reach a browser. The public NFCore portal is a static site with no backend of
its own to hold that secret, so a browser visitor cannot call that route.

This router is the first-party, browser-facing counterpart: no S2S secret, no
authority from client-supplied tenant fields, same anonymous-intake shape as
public_trial.py (explicit allowlisted origin, external shared anti-abuse gate,
never automatically enabled). It calls the same governed
`CommercialAcquisitionService` in-process -- the signature requirement exists
to protect an authenticated network boundary, and there is none to cross here,
since this process is already the one invoking the service.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Protocol
from urllib.parse import urlsplit

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from kordena_fiscal.application.commercial_acquisition import CommercialAcquisitionService
from kordena_fiscal.product.commercial_fulfillment import CommercialFulfillmentError

MAX_PUBLIC_ACQUISITION_BODY_BYTES = 4096


class PublicCommercialAcquisitionAbuseGate(Protocol):
    """Atomically decide acquisition admission across all application replicas."""

    def allow(self, identity: str, now: datetime) -> bool: ...


def _strict_json_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """Reject ambiguous JSON objects at every nesting level."""
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON field")
        result[key] = value
    return result


def create_public_commercial_acquisition_router(
    service: CommercialAcquisitionService,
    *,
    allowed_origins: tuple[str, ...],
    rate_limiter: PublicCommercialAcquisitionAbuseGate,
) -> APIRouter:
    """Produce first-party public acquisition ingress without touching the signed S2S route."""
    if not allowed_origins or any(
        urlsplit(value).scheme != "https"
        or not urlsplit(value).netloc
        or urlsplit(value).username is not None
        or urlsplit(value).password is not None
        or urlsplit(value).path not in ("", "/")
        or urlsplit(value).query
        or urlsplit(value).fragment
        or value.rstrip("/") != value
        for value in allowed_origins
    ):
        raise ValueError("public commercial acquisition requires explicit HTTPS origins")

    router = APIRouter(tags=["public-commercial-acquisition"])

    @router.options("/v1/public/acquisitions")
    async def public_acquisition_preflight(request: Request) -> JSONResponse:
        origin = request.headers.get("origin", "")
        if origin not in allowed_origins:
            return JSONResponse(status_code=403, content={"detail": "origin denied"})
        requested = {
            item.strip().lower()
            for item in request.headers.get("access-control-request-headers", "").split(",")
            if item.strip()
        }
        if request.headers.get("access-control-request-method", "") != "POST" or not (
            requested <= {"content-type", "idempotency-key"}
        ):
            return JSONResponse(status_code=403, content={"detail": "preflight denied"})
        return JSONResponse(
            status_code=200,
            content={},
            headers={
                "Access-Control-Allow-Origin": origin,
                "Access-Control-Allow-Methods": "POST",
                "Access-Control-Allow-Headers": "Content-Type, Idempotency-Key",
                "Access-Control-Max-Age": "600",
                "Cache-Control": "no-store",
                "Vary": "Origin",
            },
        )

    @router.post("/v1/public/acquisitions")
    async def public_acquisition(request: Request) -> JSONResponse:
        origin = request.headers.get("origin", "")
        headers = {"Cache-Control": "no-store, max-age=0"}
        if origin not in allowed_origins:
            return JSONResponse(
                status_code=403,
                content={"detail": "origin denied"},
                headers=headers,
            )
        headers["Access-Control-Allow-Origin"] = origin
        headers["Vary"] = "Origin"
        if (
            request.headers.get("content-type", "").split(";")[0].strip().lower()
            != "application/json"
        ):
            return JSONResponse(
                status_code=415,
                content={"detail": "JSON required"},
                headers=headers,
            )
        if request.headers.get("cookie") or request.headers.get("authorization"):
            return JSONResponse(
                status_code=403,
                content={"detail": "anonymous request required"},
                headers=headers,
            )
        identity = request.client.host if request.client is not None else "unknown"
        if not rate_limiter.allow(f"public-acquisition:{identity}", datetime.now(UTC)):
            return JSONResponse(
                status_code=429,
                content={"detail": "rate limited"},
                headers=headers,
            )
        key = request.headers.get("Idempotency-Key", "").strip()
        if not (16 <= len(key) <= 128 and key.isascii() and key.isprintable()):
            return JSONResponse(
                status_code=400,
                content={"detail": "invalid idempotency key"},
                headers=headers,
            )
        body = bytearray()
        async for chunk in request.stream():
            if len(body) + len(chunk) > MAX_PUBLIC_ACQUISITION_BODY_BYTES:
                return JSONResponse(
                    status_code=413,
                    content={"detail": "payload too large"},
                    headers=headers,
                )
            body.extend(chunk)
        try:
            payload = json.loads(bytes(body), object_pairs_hook=_strict_json_pairs)
        except (ValueError, UnicodeDecodeError):
            return JSONResponse(
                status_code=400,
                content={"detail": "invalid JSON"},
                headers=headers,
            )
        fields = {"plan_id", "price_id", "buyer_email", "legal_name"}
        if not isinstance(payload, dict) or set(payload) != fields or not all(
            isinstance(payload[field], str) for field in fields
        ):
            return JSONResponse(
                status_code=400,
                content={"detail": "invalid acquisition fields"},
                headers=headers,
            )
        now = datetime.now(UTC)
        try:
            started = service.begin(
                plan_id=payload["plan_id"],
                price_id=payload["price_id"],
                buyer_email=payload["buyer_email"],
                legal_name=payload["legal_name"],
                idempotency_key=key,
                now=now,
            )
        except CommercialFulfillmentError as exc:
            message = str(exc)
            not_ready = "not operationally ready" in message
            return JSONResponse(
                status_code=503 if not_ready else 409,
                content={
                    "detail": (
                        "commercial purchase path is unavailable"
                        if not_ready
                        else "commercial acquisition could not be created"
                    )
                },
                headers=headers,
            )
        except Exception:
            return JSONResponse(
                status_code=503,
                content={"detail": "commercial acquisition temporarily unavailable"},
                headers=headers,
            )
        return JSONResponse(
            status_code=200 if started.replay else 201,
            content={
                "acquisition_reference": started.acquisition_reference,
                "provider": started.provider_id,
                "checkout_url": started.checkout_url,
                "expires_at": started.expires_at.isoformat(),
                "replay": started.replay,
            },
            headers=headers,
        )

    return router


__all__ = [
    "PublicCommercialAcquisitionAbuseGate",
    "create_public_commercial_acquisition_router",
]
