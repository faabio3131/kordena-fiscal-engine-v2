"""Human review of immutable Bling orders using the existing portal session boundary."""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Body, HTTPException, Request
from fastapi.responses import JSONResponse

from kordena_fiscal.application.bling_orders import BlingOrders
from kordena_fiscal.domain import FiscalValidationError
from kordena_fiscal.persistence.ports import PersistenceConflictError, PersistenceStateError
from kordena_fiscal.runtime.config import RuntimeConfigurationError
from kordena_fiscal.security.human_identity import HumanIdentityService, PortalPermission
from kordena_fiscal.web.portal_api import _authenticated, _authorized, _csrf


def build_bling_review_router(
    identity: HumanIdentityService,
    orders_factory: Callable[[], BlingOrders],
) -> APIRouter:
    router = APIRouter(prefix="/v1/portal/integrations/bling")

    def context(request: Request, *, mutate: bool = False) -> tuple[BlingOrders, str]:
        human = _authenticated(request, identity, now=datetime.now(UTC))
        try:
            orders = orders_factory()
        except RuntimeConfigurationError:
            raise HTTPException(503, detail={"code": "BLING_NOT_CONFIGURED"}) from None
        if human.tenant_id != orders.scope.tenant_id:
            raise HTTPException(403, detail={"code": "BLING_SCOPE_FORBIDDEN"})
        _authorized(human, PortalPermission.INTEGRATION_MANAGE, unit_id=orders.scope.unit_id)
        if mutate:
            _authorized(human, PortalPermission.DOCUMENT_ISSUE, unit_id=orders.scope.unit_id)
            _csrf(request, identity, human)
        return orders, human.account.account_id

    def response(value: object) -> JSONResponse:
        return JSONResponse(content=value, headers={"Cache-Control": "no-store"})

    @router.get("/orders/{order_id}")
    def review(order_id: int, request: Request) -> JSONResponse:
        orders, _actor = context(request)
        if order_id <= 0:
            raise HTTPException(422, detail={"code": "INVALID_ORDER_ID"})
        row = orders.get(order_id)
        if row is None:
            raise HTTPException(404, detail={"code": "BLING_ORDER_NOT_FOUND"})
        # Only immutable snapshots belonging to this installation and this order.
        return response({"order": row, "snapshots": orders.review_snapshots(order_id)})

    @router.post("/orders/{order_id}/{action}")
    def decide(
        order_id: int,
        action: str,
        request: Request,
        payload: Annotated[dict[str, Any], Body()],
    ) -> JSONResponse:
        orders, actor = context(request, mutate=True)
        if order_id <= 0:
            raise HTTPException(422, detail={"code": "INVALID_ORDER_ID"})
        expected = {"snapshot_sha256"}
        if action == "approve-prepared":
            expected.add("document_id")
        elif action != "select-snapshot":
            raise HTTPException(404, detail={"code": "BLING_ACTION_NOT_FOUND"})
        if set(payload) != expected or any(
            not isinstance(value, str) or not value.strip() or len(value) > 256
            for value in payload.values()
        ):
            raise HTTPException(422, detail={"code": "INVALID_BLING_REVIEW"})
        try:
            if action == "select-snapshot":
                result = orders.select_snapshot(
                    order_id, snapshot_sha256=payload["snapshot_sha256"],
                    actor_id=actor, now=datetime.now(UTC),
                )
            else:
                result = orders.approve_prepared(
                    order_id, snapshot_sha256=payload["snapshot_sha256"],
                    document_id=payload["document_id"], actor_id=actor, now=datetime.now(UTC),
                )
        except (PersistenceConflictError, PersistenceStateError, FiscalValidationError):
            raise HTTPException(409, detail={"code": "BLING_REVIEW_CONFLICT"}) from None
        return response({"order": result})

    return router
