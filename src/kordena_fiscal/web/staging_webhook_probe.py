"""Opt-in staging-only sink for proving signed outbound webhook delivery.

No business mutation, no raw payload, no credentials and no inbound test data
are written to durable state. Not a customer-configurable webhook endpoint.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Request
from fastapi.responses import Response
from starlette.concurrency import run_in_threadpool

from kordena_fiscal.security.s2s import WebhookSecurity, WebhookSignature

MAX_PROBE_BYTES = 64 * 1024


def create_staging_webhook_probe_router(security: WebhookSecurity) -> APIRouter:
    if not isinstance(security, WebhookSecurity):
        raise TypeError("staging probe requires canonical webhook security")
    router = APIRouter(tags=["staging-webhook-probe"])

    @router.post("/internal/staging/webhook-probe", include_in_schema=False)
    async def receive(request: Request) -> Response:
        # Bound memory and prevent an unbounded streaming ingress.
        body = bytearray()
        async for chunk in request.stream():
            if len(body) + len(chunk) > MAX_PROBE_BYTES:
                return Response(status_code=413)
            body.extend(chunk)
        try:
            signature = WebhookSignature.parse(
                request.headers.get("X-FM-Webhook-Signature", "")
            )
            await run_in_threadpool(
                security.verify, bytes(body), signature, now=datetime.now(UTC)
            )
        except Exception:
            # Fail closed, including unavailable secret backend. No body or key
            # material is emitted in responses or logs.
            return Response(status_code=401)
        finally:
            body.clear()
        # A non-mutating sink: retries are safe; never claim a fiscal operation
        # was processed. HTTP 204 is only receipt of a valid signed probe.
        return Response(status_code=204)

    return router
