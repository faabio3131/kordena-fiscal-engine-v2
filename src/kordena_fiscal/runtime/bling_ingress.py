"""Bling order notifications enter the existing durable fiscal inbox."""

from collections.abc import Mapping
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request
from starlette.concurrency import run_in_threadpool

from kordena_fiscal.application.service import FiscalApplicationService
from kordena_fiscal.connectors.bling_webhook import BlingWebhookError, verify_order_notification
from kordena_fiscal.domain import FiscalEnvironment, FiscalValidationError, HostNamespace, HostScope
from kordena_fiscal.events.inbox import InboxConflictError

from .config import RuntimeConfigurationError


def build_bling_ingress(
    application: FiscalApplicationService | None,
    environ: Mapping[str, str],
) -> APIRouter | None:
    prefix = "NFCORE_BLING_"
    fields = ("CLIENT_SECRET", "COMPANY_ID", "TENANT_ID", "UNIT_ID", "ENVIRONMENT")
    values = [environ.get(prefix + field, "").strip() for field in fields]
    if not any(values):
        return None
    if application is None or not all(values):
        raise RuntimeConfigurationError("Bling ingress prerequisites are incomplete")
    secret, company_id, tenant, unit, environment = values
    try:
        if len(company_id) > 96:
            raise ValueError("invalid company")
        host_scope = HostScope(HostNamespace("bling"), tenant, unit)
        fiscal_environment = FiscalEnvironment(environment)
    except ValueError:
        raise RuntimeConfigurationError("Invalid Bling ingress configuration") from None

    router = APIRouter()

    @router.post("/webhooks/bling", status_code=202, include_in_schema=False)
    async def receive(request: Request) -> dict[str, str]:
        body = bytearray()
        async for chunk in request.stream():
            if len(body) + len(chunk) > 1_048_576:
                raise HTTPException(413, "Bling notification exceeds size limit")
            body.extend(chunk)
        raw = bytes(body)
        try:
            notification = verify_order_notification(
                raw,
                request.headers.get("X-Bling-Signature-256", ""),
                client_secret=secret.encode(),
                expected_company_id=company_id,
            )
        except BlingWebhookError:
            raise HTTPException(400, "Bling notification rejected") from None

        try:
            scope = await run_in_threadpool(
                application.resolve_scope,
                host_scope,
                environment=fiscal_environment,
                correlation_id=notification.event_id,
            )
            await run_in_threadpool(
                application.receive_inbox_event,
                scope=scope,
                producer=f"bling:{company_id}",
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
            raise HTTPException(422, "Bling fiscal scope or event is invalid") from None
        return {"status": "accepted"}

    return router
