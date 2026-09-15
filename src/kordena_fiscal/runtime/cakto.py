"""Thin HTTP adapter for authenticated Cakto webhook ingestion."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from fastapi import APIRouter, Header, HTTPException, Request, status

from kordena_fiscal.product.cakto import (
    CaktoAuthenticationError,
    CaktoPayloadError,
    CaktoStateConflictError,
    CaktoWebhookReceiver,
    utc_now,
)

Clock = Callable[[], datetime]


def build_cakto_webhook_router(
    receiver: CaktoWebhookReceiver,
    *,
    clock: Clock = utc_now,
) -> APIRouter:
    """Build a router only when a real externally-sourced webhook secret is injected."""

    router = APIRouter(tags=["commercial-cakto"])

    @router.post(
        "/webhooks/cakto",
        status_code=status.HTTP_202_ACCEPTED,
        include_in_schema=False,
    )
    async def receive_cakto_webhook(
        request: Request,
        x_cakto_timestamp: str | None = Header(default=None, alias="X-Cakto-Timestamp"),
        x_cakto_signature: str | None = Header(default=None, alias="X-Cakto-Signature"),
    ) -> dict[str, int | str]:
        if x_cakto_timestamp is None or x_cakto_signature is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Cakto signature headers are required",
            )
        raw_body = await request.body()
        try:
            entries = receiver.receive(
                raw_body=raw_body,
                timestamp_header=x_cakto_timestamp,
                signature_header=x_cakto_signature,
                received_at=clock(),
            )
        except CaktoAuthenticationError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Cakto webhook authentication failed",
            ) from exc
        except CaktoPayloadError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cakto webhook payload rejected",
            ) from exc
        except CaktoStateConflictError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cakto webhook state conflict",
            ) from exc
        return {"status": "accepted", "accepted": len(entries)}

    return router
