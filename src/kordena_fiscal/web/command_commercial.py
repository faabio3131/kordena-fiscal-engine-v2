"""Bounded, authenticated HTTP ingress; no accepted response before durable effects."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from kordena_fiscal.application.command_commercial import CommandCommercialReceiver
from kordena_fiscal.product.command_commercial import CommandCommercialEvent
from kordena_fiscal.product.commercial_fulfillment import CommercialFulfillmentError
from kordena_fiscal.security.s2s import FixedWindowRateLimiter, WebhookSignature

MAX_COMMAND_BODY_BYTES = 64 * 1024


def create_command_commercial_router(
    receiver: CommandCommercialReceiver,
    *,
    rate_limiter: FixedWindowRateLimiter,
) -> APIRouter:
    router = APIRouter(tags=["command-commercial"])

    @router.post("/v1/commercial/command/events")
    async def receive(request: Request) -> JSONResponse:
        now = datetime.now(UTC)
        body = bytearray()
        async for chunk in request.stream():
            if len(body) + len(chunk) > MAX_COMMAND_BODY_BYTES:
                return JSONResponse(status_code=413, content={"detail": "Command body too large"})
            body.extend(chunk)
        try:
            signature = WebhookSignature.parse(request.headers.get("X-NFCore-Signature", ""))
            binding = await run_in_threadpool(receiver.authenticate, bytes(body), signature, now)
        except Exception:
            # Covers unknown/revoked key, malformed headers and unavailable
            # secret/binding backend without disclosing metadata or raw errors.
            return JSONResponse(
                status_code=401, content={"detail": "Command authentication failed"}
            )
        if not rate_limiter.allow(binding.binding_id, now):
            return JSONResponse(status_code=429, content={"detail": "Command rate limit exceeded"})
        try:
            event = CommandCommercialEvent.parse(bytes(body))
        except CommercialFulfillmentError:
            return JSONResponse(status_code=400, content={"detail": "Invalid Command envelope"})
        try:
            result = await run_in_threadpool(
                receiver.receive, event=event, binding=binding, now=now
            )
        except CommercialFulfillmentError:
            return JSONResponse(status_code=409, content={"detail": "Command event rejected"})
        except Exception:
            return JSONResponse(
                status_code=503, content={"detail": "Command processing unavailable"}
            )
        return JSONResponse(
            status_code=200 if result.replay else 202,
            content={
                "status": "processed",
                "purchase_id": result.purchase_id,
                "replay": result.replay,
            },
            headers={"Cache-Control": "no-store, max-age=0"},
        )

    return router
