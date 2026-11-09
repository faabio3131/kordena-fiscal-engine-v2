"""Read-only Bling result projection behind the existing S2S query capability."""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from kordena_fiscal.application.bling_orders import BlingOrders
from kordena_fiscal.persistence.ports import FiscalUnitOfWorkFactory
from kordena_fiscal.security.s2s import AuthorizedFiscalRequest, FiscalCapability
from kordena_fiscal.web.app import BridgeSecurityBoundary, HttpContractError, _context


def build_bling_status_router(
    database: FiscalUnitOfWorkFactory,
    company_id: str,
    security: BridgeSecurityBoundary,
) -> APIRouter:
    router = APIRouter()

    @router.get("/v1/integrations/bling/orders/{order_id}")
    def status(order_id: int, request: Request) -> JSONResponse:
        try:
            context = _context(request, idempotency_required=False)
            authorized = security.authorize(operation_id="queryFiscalDocument", context=context)
        except HttpContractError as exc:
            return JSONResponse(
                status_code=exc.status_code,
                content={"code": exc.code, "message": exc.message},
                headers={"Cache-Control": "no-store"},
            )
        authority = authorized.authority
        if (
            not isinstance(authority, AuthorizedFiscalRequest)
            or authority.capability is not FiscalCapability.QUERY
            or authority.scope.host_namespace != "bling"
        ):
            raise HTTPException(403, "Invalid Bling query authority")
        if order_id <= 0:
            raise HTTPException(422, "Invalid order identifier")
        row = BlingOrders(database, authority.scope, company_id).get(order_id)
        if row is None:
            raise HTTPException(404, "Bling order not found")
        # No raw customer data, credential, provider error or archive contents here.
        fields = (
            "order_id",
            "state",
            "normalization_ready",
            "snapshot_sha256",
            "document_id",
            "recovery_required",
            "result_reference",
            "review_required",
            "deleted",
        )
        return JSONResponse(
            content={key: row[key] for key in fields if key in row},
            headers={"Cache-Control": "no-store", "X-Correlation-Id": authorized.correlation_id},
        )

    return router
