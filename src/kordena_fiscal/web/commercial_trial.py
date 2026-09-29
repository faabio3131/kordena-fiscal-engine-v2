"""Signed server-to-server boundary for governed NFCore trials."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from kordena_fiscal.application.commercial_trial import GovernedTrialService
from kordena_fiscal.product.commercial_fulfillment import CommercialFulfillmentError
from kordena_fiscal.security.s2s import (
    FixedWindowRateLimiter,
    WebhookSecurity,
    WebhookSignature,
    WebhookSignatureError,
)
from kordena_fiscal.web.human_recovery import PasswordResetDelivery


def create_commercial_trial_router(
    service: GovernedTrialService,
    *,
    security: WebhookSecurity,
    rate_limiter: FixedWindowRateLimiter,
    delivery: PasswordResetDelivery,
) -> APIRouter:
    router = APIRouter(tags=["commercial-trial"])

    @router.post("/v1/commercial/trials")
    async def begin_trial(request: Request) -> JSONResponse:
        now = datetime.now(UTC)
        body = await request.body()
        raw_signature = request.headers.get("X-NFCore-Signature", "").strip()
        if not raw_signature:
            return JSONResponse(
                status_code=401,
                content={"detail": "commercial workload authentication is required"},
            )
        try:
            signature = WebhookSignature.parse(raw_signature)
            security.verify(body, signature, now=now)
        except (WebhookSignatureError, ValueError):
            return JSONResponse(
                status_code=401,
                content={"detail": "commercial workload authentication failed"},
            )
        if not rate_limiter.allow(f"trial:{signature.key_id}", now):
            return JSONResponse(
                status_code=429,
                content={"detail": "commercial trial rate limit exceeded"},
            )

        idempotency_key = request.headers.get("Idempotency-Key", "").strip()
        if not idempotency_key:
            return JSONResponse(
                status_code=400,
                content={"detail": "Idempotency-Key is required"},
            )
        try:
            payload = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return JSONResponse(
                status_code=400,
                content={"detail": "commercial trial body must be valid JSON"},
            )
        if not isinstance(payload, dict):
            return JSONResponse(
                status_code=400,
                content={"detail": "commercial trial body must be an object"},
            )
        required = {"plan_id", "price_id", "buyer_email", "legal_name"}
        if set(payload) != required or not all(
            isinstance(payload.get(field), str) for field in required
        ):
            return JSONResponse(
                status_code=400,
                content={"detail": "commercial trial fields are invalid"},
            )

        try:
            started = service.begin(
                plan_id=payload["plan_id"],
                price_id=payload["price_id"],
                buyer_email=payload["buyer_email"],
                legal_name=payload["legal_name"],
                idempotency_key=idempotency_key,
                now=now,
            )
        except CommercialFulfillmentError:
            return JSONResponse(
                status_code=409,
                content={"detail": "commercial trial could not be created"},
            )

        if started.activation_reset is not None:
            try:
                delivery.deliver(
                    email=payload["buyer_email"].strip().casefold(),
                    reset=started.activation_reset,
                )
            except Exception:
                return JSONResponse(
                    status_code=503,
                    content={"detail": "commercial trial activation delivery failed"},
                )

        return JSONResponse(
            status_code=200 if started.replay else 201,
            content={
                "status": "trial_activation_pending",
                "trial_expires_at": started.expires_at.isoformat(),
                "replay": started.replay,
            },
            headers={"Cache-Control": "no-store, max-age=0"},
        )

    return router


__all__ = ["create_commercial_trial_router"]
