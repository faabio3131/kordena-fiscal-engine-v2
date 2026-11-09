"""Installation-scoped Bling webhook ingress using the canonical fiscal inbox."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol

from fastapi import APIRouter, HTTPException, Request
from starlette.concurrency import run_in_threadpool

from kordena_fiscal.application.service import FiscalApplicationService
from kordena_fiscal.connectors.bling_webhook import (
    BlingWebhookError,
    verify_order_notification,
)
from kordena_fiscal.domain import FiscalValidationError
from kordena_fiscal.events.inbox import InboxConflictError
from kordena_fiscal.integrations.bling_contracts import BlingInstallationState
from kordena_fiscal.persistence.bling_installations import BlingInstallationRepository


class BlingWebhookSecretReader(Protocol):
    """A-owned, fail-closed secret boundary; never accept keys from the request."""

    def webhook_secret(self, installation_id: str) -> bytes: ...


def build_multitenant_bling_ingress(
    application: FiscalApplicationService,
    installations: BlingInstallationRepository,
    secrets: BlingWebhookSecretReader,
) -> APIRouter:
    router = APIRouter()

    @router.post(
        "/webhooks/bling/installations/{installation_id}",
        status_code=202,
        include_in_schema=False,
    )
    async def receive(installation_id: str, request: Request) -> dict[str, str]:
        # Installation ID is a locator only. It never conveys fiscal authority.
        installation = installations.get_by_id(installation_id)
        if installation is None:
            raise HTTPException(404, "Bling installation not found")
        if installation.state is not BlingInstallationState.CONNECTED:
            raise HTTPException(409, "Bling installation not active")

        body = bytearray()
        async for chunk in request.stream():
            if len(body) + len(chunk) > 1_048_576:
                raise HTTPException(413, "Bling notification exceeds size limit")
            body.extend(chunk)
        raw = bytes(body)
        try:
            secret = await run_in_threadpool(secrets.webhook_secret, installation_id)
            if not isinstance(secret, bytes) or len(secret) < 16:
                raise ValueError("secret unavailable")
        except Exception:
            raise HTTPException(503, "Bling webhook secret unavailable") from None
        try:
            notification = verify_order_notification(
                raw,
                request.headers.get("X-Bling-Signature-256", ""),
                client_secret=secret,
                expected_company_id=installation.company_id,
            )
        except BlingWebhookError:
            raise HTTPException(400, "Bling notification rejected") from None

        # Never use companyId, tenant/unit, or environment from the untrusted envelope.
        host = installations.host_binding(installation_id)
        if host is None:
            raise HTTPException(409, "Bling binding unavailable")
        try:
            scope = await run_in_threadpool(
                application.resolve_scope,
                host,
                environment=installation.environment,
                correlation_id=notification.event_id,
            )
            if (
                scope.tenant_id != installation.tenant_id
                or scope.unit_id != installation.unit_id
                or scope.environment is not installation.environment
            ):
                raise FiscalValidationError("Bling binding drift")
            await run_in_threadpool(
                application.receive_inbox_event,
                scope=scope,
                producer=f"bling:{installation.company_id}",
                event_id=notification.event_id,
                event_type=notification.event,
                payload=raw,
                occurred_at=notification.occurred_at,
                received_at=datetime.now(UTC),
                processing_operation="process_bling_order",
            )
        except InboxConflictError:
            raise HTTPException(409, "Bling event conflicts with a stored event") from None
        except FiscalValidationError:
            raise HTTPException(422, "Bling fiscal binding unavailable") from None
        return {"status": "accepted"}

    return router
