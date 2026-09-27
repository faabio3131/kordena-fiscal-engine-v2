"""Runtime composition and HTTP adapter for the Cakto commercial boundary.

The runtime deliberately accepts webhook secret material only by injection. Secret
resolution belongs to the external secret boundary; this module never reads secrets
from environment variables, persists them, or grants fiscal production authority.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from fastapi import APIRouter, Header, HTTPException, Request, status

from kordena_fiscal.persistence.cakto import (
    CaktoCommercialDatabase,
    postgres_cakto_commercial_database,
)
from kordena_fiscal.product.cakto import (
    CaktoAuthenticationError,
    CaktoCommercialProcessor,
    CaktoMetricSink,
    CaktoPayloadError,
    CaktoStateConflictError,
    CaktoWebhookReceiver,
    CaktoWebhookVerifier,
    utc_now,
)

Clock = Callable[[], datetime]


@dataclass(frozen=True, slots=True)
class CaktoCommercialRuntime:
    """Canonical commercial runtime assembled around one durable database."""

    database: CaktoCommercialDatabase
    receiver: CaktoWebhookReceiver
    processor: CaktoCommercialProcessor


def compose_cakto_commercial_runtime(
    *,
    database: CaktoCommercialDatabase,
    webhook_secret: bytes,
    metrics: CaktoMetricSink | None = None,
    initialize_schema: bool = True,
) -> CaktoCommercialRuntime:
    """Compose Cakto ingestion and processing without resolving secret material here.

    ``webhook_secret`` must already have been resolved by the governed external secret
    boundary. Keeping that resolution outside this function prevents a second secret
    architecture and makes rotation observable on the next composition/reload.
    """

    if not isinstance(database, CaktoCommercialDatabase):
        raise CaktoStateConflictError("Cakto commercial database is required")
    if initialize_schema:
        database.initialize()
    verifier = CaktoWebhookVerifier(webhook_secret)
    receiver = CaktoWebhookReceiver(
        verifier=verifier,
        unit_of_work_factory=database,
        metrics=metrics,
    )
    processor = CaktoCommercialProcessor(
        unit_of_work_factory=database,
        metrics=metrics,
    )
    return CaktoCommercialRuntime(
        database=database,
        receiver=receiver,
        processor=processor,
    )


def compose_postgres_cakto_commercial_runtime(
    *,
    fiscal_database: object,
    webhook_secret: bytes,
    metrics: CaktoMetricSink | None = None,
) -> CaktoCommercialRuntime:
    """Bind the commercial runtime to the canonical PostgreSQL connection boundary."""

    database = postgres_cakto_commercial_database(fiscal_database)
    return compose_cakto_commercial_runtime(
        database=database,
        webhook_secret=webhook_secret,
        metrics=metrics,
        initialize_schema=True,
    )


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
