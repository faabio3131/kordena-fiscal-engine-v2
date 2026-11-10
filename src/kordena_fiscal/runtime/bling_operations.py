"""Authenticated multi-tenant Bling operations, review and recovery endpoints.

All mutations require the existing human session, unit RBAC and CSRF.
Order, receipt, outbox and fiscal rules reuse the canonical authorities.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Body, HTTPException, Request
from fastapi.responses import JSONResponse

from kordena_fiscal.application.bling_operations import (
    BlingOperationalError,
    BlingOperationsService,
)
from kordena_fiscal.application.bling_orders import BlingOrders
from kordena_fiscal.connectors.bling_api import BlingApiError
from kordena_fiscal.domain import (
    ExecutionScope,
    FiscalDomainError,
    FiscalEnvironment,
    FiscalValidationError,
)
from kordena_fiscal.integrations.bling_contracts import BlingInstallationState
from kordena_fiscal.persistence.bling_installations import BlingInstallationRepository
from kordena_fiscal.persistence.ports import PersistenceConflictError, PersistenceStateError
from kordena_fiscal.runtime.bling_oauth_service import BlingOAuthUnavailable
from kordena_fiscal.runtime.bling_preparation import BlingSalePreparer
from kordena_fiscal.security.human_identity import HumanIdentityService, PortalPermission
from kordena_fiscal.web.portal_api import _authenticated, _authorized, _csrf

_ERRORS = {
    "BLING_INSTALLATION_NOT_FOUND": 404,
    "BLING_SCOPE_FORBIDDEN": 403,
    "BLING_NEEDS_REAUTH": 409,
    "BLING_PAUSED": 409,
    "BLING_INVALID_CURSOR": 422,
    "BLING_INVALID_LIMIT": 422,
    "BLING_INPUT_INVALID": 422,
    "BLING_RECOVERY_REQUIRED": 409,
    "BLING_TEMPORARILY_UNAVAILABLE": 503,
}


def build_bling_operations_router(
    identity: HumanIdentityService,
    installations: BlingInstallationRepository,
    operations: BlingOperationsService,
    preparer: BlingSalePreparer | None = None,
) -> APIRouter:
    """The caller composes this router exactly once with A-owned dependencies."""
    router = APIRouter(prefix="/v1/portal/integrations/bling", tags=["bling-operations"])

    def response(payload: object, status: int = 200) -> JSONResponse:
        return JSONResponse(
            content=payload, status_code=status, headers={"Cache-Control": "no-store"},
        )

    def authenticated_scope(
        request: Request, installation_id: str, *, mutate: bool = False,
    ) -> tuple[ExecutionScope, BlingOrders, str]:
        human = _authenticated(request, identity, now=datetime.now(UTC))
        view = installations.get_by_id(installation_id)
        if view is None or view.tenant_id != human.tenant_id:
            raise HTTPException(404, detail={"code": "BLING_INSTALLATION_NOT_FOUND"})
        _authorized(human, PortalPermission.INTEGRATION_MANAGE, unit_id=view.unit_id)
        if mutate:
            _authorized(human, PortalPermission.DOCUMENT_ISSUE, unit_id=view.unit_id)
            _csrf(request, identity, human)
        scope = ExecutionScope(
            tenant_id=view.tenant_id,
            unit_id=view.unit_id,
            environment=view.environment,
            correlation_id="bling-web-operations",
            host_namespace="bling",
        )
        try:
            orders = operations._orders(scope, installation_id)
        except BlingOperationalError as exc:
            raise HTTPException(
                _ERRORS.get(exc.code, 503), detail={"code": exc.code},
            ) from None
        return scope, orders, human.account.account_id

    def reject(exc: Exception) -> HTTPException:
        if isinstance(exc, BlingOperationalError):
            return HTTPException(_ERRORS.get(exc.code, 503), detail={"code": exc.code})
        if isinstance(exc, BlingApiError):
            return HTTPException(
                429 if exc.status == 429 else 503,
                detail={"code": (
                    "BLING_RATE_LIMITED" if exc.status == 429
                    else "BLING_TEMPORARILY_UNAVAILABLE"
                )},
            )
        if isinstance(exc, BlingOAuthUnavailable):
            return HTTPException(409, detail={"code": "BLING_NEEDS_REAUTH"})
        if isinstance(exc, (PersistenceConflictError, PersistenceStateError, FiscalDomainError)):
            return HTTPException(409, detail={"code": "BLING_REVIEW_CONFLICT"})
        return HTTPException(503, detail={"code": "BLING_TEMPORARILY_UNAVAILABLE"})

    @router.get("/installations/available")
    def available(request: Request, unit_id: str, limit: int = 100) -> JSONResponse:
        human = _authenticated(request, identity, now=datetime.now(UTC))
        _authorized(human, PortalPermission.INTEGRATION_MANAGE, unit_id=unit_id)
        if not unit_id or len(unit_id) > 128 or not 1 <= limit <= 100:
            raise HTTPException(422, detail={"code": "BLING_INPUT_INVALID"})
        scope = ExecutionScope(
            tenant_id=human.tenant_id, unit_id=unit_id,
            environment=FiscalEnvironment.HOMOLOGATION,
            correlation_id="bling-available", host_namespace="bling",
        )
        views, next_cursor = installations.list_for_scope(scope, limit=limit)
        return response({
            "rows": [{
                "installation_id": view.installation_id,
                "company_id": view.company_id,
                "state": view.state.value,
                "health_code": view.health_code,
                "credential_status": view.credential_status,
                "revision": view.revision,
                "environment": view.environment.value,
            } for view in views],
            "next_cursor": next_cursor,
        })

    @router.get("/installations/{installation_id}/orders")
    def list_orders(
        installation_id: str, request: Request,
        cursor: str | None = None, limit: int = 50,
    ) -> JSONResponse:
        scope, _orders, _actor = authenticated_scope(request, installation_id)
        try:
            page = operations.list_orders(scope, installation_id, cursor=cursor, limit=limit)
        except BlingOperationalError as exc:
            raise reject(exc) from None
        return response({"rows": list(page.rows), "next_cursor": page.next_cursor})

    @router.get("/installations/{installation_id}/jobs")
    def list_jobs(
        installation_id: str, request: Request, offset: int = 0, limit: int = 50,
    ) -> JSONResponse:
        scope, _orders, _actor = authenticated_scope(request, installation_id)
        try:
            return response(operations.list_jobs(
                scope, installation_id, offset=offset, limit=limit,
            ))
        except BlingOperationalError as exc:
            raise reject(exc) from None

    @router.get("/installations/{installation_id}/metrics")
    def metrics(installation_id: str, request: Request) -> JSONResponse:
        scope, _orders, _actor = authenticated_scope(request, installation_id)
        try:
            return response(operations.page_metrics(scope, installation_id))
        except BlingOperationalError as exc:
            raise reject(exc) from None

    @router.get("/installations/{installation_id}/provider-orders")
    def provider_orders(
        installation_id: str, request: Request,
        cursor: str | None = None, limit: int = 10,
    ) -> JSONResponse:
        scope, _orders, _actor = authenticated_scope(request, installation_id)
        try:
            rows, next_cursor = operations.search_orders(
                scope, installation_id, cursor=cursor, limit=limit,
            )
        except (BlingOperationalError, BlingApiError, BlingOAuthUnavailable) as exc:
            raise reject(exc) from None
        return response({"rows": list(rows), "next_cursor": next_cursor})

    @router.post("/installations/{installation_id}/recovery/backfill")
    def backfill(
        installation_id: str, request: Request,
        payload: Annotated[dict[str, Any], Body()],
    ) -> JSONResponse:
        scope, _orders, actor = authenticated_scope(
            request, installation_id, mutate=True,
        )
        if set(payload) != {"page", "limit", "request_id"}:
            raise HTTPException(422, detail={"code": "BLING_INPUT_INVALID"})
        try:
            value = operations.backfill_page(
                scope, installation_id, page=payload["page"], limit=payload["limit"],
                request_id=payload["request_id"], actor_id=actor,
            )
        except (
            BlingOperationalError, BlingApiError, BlingOAuthUnavailable,
            PersistenceConflictError, FiscalDomainError,
        ) as exc:
            raise reject(exc) from None
        return response(value)

    @router.post("/installations/{installation_id}/orders/{order_id}/recover")
    def recover(
        installation_id: str, order_id: int, request: Request,
        payload: Annotated[dict[str, Any], Body()],
    ) -> JSONResponse:
        scope, _orders, actor = authenticated_scope(
            request, installation_id, mutate=True,
        )
        if set(payload) != {"request_id"} or not isinstance(payload["request_id"], str):
            raise HTTPException(422, detail={"code": "BLING_INPUT_INVALID"})
        try:
            result = operations.reconcile(
                scope, installation_id, order_id,
                request_id=payload["request_id"], actor_id=actor,
            )
        except (
            BlingOperationalError, BlingApiError, BlingOAuthUnavailable,
            PersistenceConflictError, FiscalDomainError,
        ) as exc:
            raise reject(exc) from None
        return response({
            "operation_id": result.operation_id, "order_id": result.order_id,
            "outcome": result.outcome.value, "correlation_id": result.correlation_id,
        })

    @router.post("/installations/{installation_id}/orders/{order_id}/retry-status")
    def retry_status(
        installation_id: str, order_id: int, request: Request,
        payload: Annotated[dict[str, Any], Body()],
    ) -> JSONResponse:
        scope, _orders, actor = authenticated_scope(
            request, installation_id, mutate=True,
        )
        if set(payload) != {"request_id"} or not isinstance(payload["request_id"], str):
            raise HTTPException(422, detail={"code": "BLING_INPUT_INVALID"})
        try:
            result = operations.retry_status(
                scope, installation_id, order_id,
                request_id=payload["request_id"], actor_id=actor,
            )
        except (BlingOperationalError, PersistenceConflictError, FiscalDomainError) as exc:
            raise reject(exc) from None
        return response({"operation_id": result.operation_id, "outcome": result.outcome.value})

    @router.get("/installations/{installation_id}/orders/{order_id}")
    def review(installation_id: str, order_id: int, request: Request) -> JSONResponse:
        scope, orders, _actor = authenticated_scope(request, installation_id)
        if order_id <= 0:
            raise HTTPException(422, detail={"code": "BLING_INPUT_INVALID"})
        row = orders.get(order_id)
        if row is None:
            raise HTTPException(404, detail={"code": "BLING_ORDER_NOT_FOUND"})
        preparation: dict[str, Any] = {"configured": False}
        if preparer is not None:
            try:
                policy, digest = preparer.policy(orders)
                preparation = {
                    "configured": True,
                    "policy_id": policy["policy_id"],
                    "version": policy["version"],
                    "sha256": digest,
                    "issued_at": datetime.now(UTC).isoformat(),
                }
                if policy.get("sale_options", {}).get("card_integration_type") == 1:
                    raw = orders.snapshot(order_id)["raw"]
                    preparation["integrated_card_indexes"] = [
                        index for index, parcel in enumerate(raw.get("parcelas", []))
                        if policy.get("payment_methods", {}).get(
                            str(parcel.get("formaPagamento", {}).get("id"))
                        ) in {"credit_card", "debit_card"}
                    ]
            except FiscalValidationError:
                pass
        return response({
            "order": row, "snapshots": orders.review_snapshots(order_id),
            "preparation": preparation,
        })

    @router.post("/installations/{installation_id}/orders/{order_id}/{action}")
    def decide(
        installation_id: str, order_id: int, action: str, request: Request,
        payload: Annotated[dict[str, Any], Body()],
    ) -> JSONResponse:
        _scope, orders, actor = authenticated_scope(request, installation_id, mutate=True)
        if order_id <= 0:
            raise HTTPException(422, detail={"code": "BLING_INPUT_INVALID"})
        if action == "prepare":
            if preparer is None:
                raise HTTPException(503, detail={"code": "BLING_NOT_CONFIGURED"})
            try:
                document_id = preparer.prepare(orders, order_id, payload, actor)
            except (PersistenceConflictError, PersistenceStateError, FiscalDomainError):
                raise HTTPException(409, detail={"code": "BLING_PREPARATION_BLOCKED"}) from None
            return response({
                "document_id": document_id,
                "state": (orders.get(order_id) or {}).get("state"),
            })
        expected = {"snapshot_sha256"}
        if action == "approve-prepared":
            expected.add("document_id")
        elif action != "select-snapshot":
            raise HTTPException(404, detail={"code": "BLING_ACTION_NOT_FOUND"})
        if set(payload) != expected or any(
            not isinstance(value, str) or not value.strip() or len(value) > 256
            for value in payload.values()
        ):
            raise HTTPException(422, detail={"code": "BLING_INPUT_INVALID"})
        try:
            if action == "select-snapshot":
                result = orders.select_snapshot(
                    order_id, snapshot_sha256=payload["snapshot_sha256"],
                    actor_id=actor, now=datetime.now(UTC),
                )
            else:
                result = orders.approve_prepared(
                    order_id, snapshot_sha256=payload["snapshot_sha256"],
                    document_id=payload["document_id"], actor_id=actor,
                    now=datetime.now(UTC),
                )
        except (PersistenceConflictError, PersistenceStateError, FiscalDomainError):
            raise HTTPException(409, detail={"code": "BLING_REVIEW_CONFLICT"}) from None
        return response({"order": result})

    return router
