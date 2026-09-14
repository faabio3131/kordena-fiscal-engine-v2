"""Session-authorized portal API for the FM NFCORE web control center.

The browser never supplies tenant authority. Human authority is reconstructed from
the opaque session cookie and every operation is delegated to a server-side product
executor. No synthetic fallback exists: if the executor is unavailable the portal
fails closed with 503.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Annotated, Any, Protocol, runtime_checkable

from fastapi import APIRouter, Body, HTTPException, Request, status

from kordena_fiscal.security.human_identity import (
    AuthenticatedHuman,
    CsrfValidationError,
    HumanAuthenticationError,
    HumanAuthorizationError,
    HumanIdentityService,
    PortalPermission,
)
from kordena_fiscal.web.human_auth import CSRF_COOKIE, CSRF_HEADER, SESSION_COOKIE


@runtime_checkable
class HumanPortalExecutor(Protocol):
    """Server-side product projection and operation boundary used by the web portal."""

    def snapshot(self, *, authority: AuthenticatedHuman) -> Mapping[str, Any]: ...

    def surface(
        self,
        *,
        surface_id: str,
        authority: AuthenticatedHuman,
    ) -> Sequence[Mapping[str, Any]]: ...

    def execute(
        self,
        *,
        operation_id: str,
        authority: AuthenticatedHuman,
        payload: Mapping[str, Any],
        idempotency_key: str | None,
    ) -> Mapping[str, Any]: ...


_SURFACE_PERMISSIONS: dict[str, PortalPermission] = {
    "overview": PortalPermission.PORTAL_READ,
    "documents": PortalPermission.DOCUMENT_QUERY,
    "issuances": PortalPermission.DOCUMENT_QUERY,
    "errors": PortalPermission.PORTAL_READ,
    "reconciliation": PortalPermission.DOCUMENT_QUERY,
    "onboarding": PortalPermission.CONFIGURATION_WRITE,
    "companies": PortalPermission.CONFIGURATION_WRITE,
    "units": PortalPermission.CONFIGURATION_WRITE,
    "environments": PortalPermission.CONFIGURATION_WRITE,
    "capabilities": PortalPermission.PORTAL_READ,
    "certificates": PortalPermission.CERTIFICATE_MANAGE,
    "providers": PortalPermission.INTEGRATION_MANAGE,
    "webhooks": PortalPermission.INTEGRATION_MANAGE,
    "integrations": PortalPermission.INTEGRATION_MANAGE,
    "usage": PortalPermission.BILLING_READ,
    "billing": PortalPermission.BILLING_READ,
    "plans": PortalPermission.BILLING_READ,
    "audit": PortalPermission.AUDIT_READ,
    "support": PortalPermission.PORTAL_READ,
    "settings": PortalPermission.CONFIGURATION_WRITE,
    "users": PortalPermission.USER_MANAGE,
}

_OPERATION_PERMISSIONS: dict[str, PortalPermission] = {
    "issueFiscalDocument": PortalPermission.DOCUMENT_ISSUE,
    "queryFiscalDocument": PortalPermission.DOCUMENT_QUERY,
    "cancelFiscalDocument": PortalPermission.DOCUMENT_CANCEL,
    "inutilizeFiscalRange": PortalPermission.DOCUMENT_INUTILIZE,
    "reconcileFiscalOperation": PortalPermission.RECONCILIATION_EXECUTE,
}

_IDEMPOTENT_MUTATIONS = {
    "issueFiscalDocument",
    "cancelFiscalDocument",
    "inutilizeFiscalRange",
    "reconcileFiscalOperation",
}

_SECRET_KEYS = {
    "password",
    "password_hash",
    "secret",
    "token",
    "session_token",
    "csrf_token",
    "private_key",
    "private_key_pem",
    "certificate_pem",
    "csc",
}

_BROWSER_AUTHORITY_FIELDS = {
    "tenant_id",
    "account_id",
    "role",
    "permissions",
    "authority",
    "session_epoch",
    "host_namespace",
}


def _safe_payload(value: object, *, path: str = "payload") -> None:
    """Fail closed if a portal projection attempts to expose secret material."""

    if isinstance(value, Mapping):
        for raw_key, nested in value.items():
            key = str(raw_key).strip().casefold()
            if key in _SECRET_KEYS or key.endswith("_secret") or key.endswith("_token"):
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail={
                        "code": "PORTAL_SECRET_BOUNDARY_VIOLATION",
                        "message": "Portal projection attempted to expose protected material",
                    },
                )
            _safe_payload(nested, path=f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, nested in enumerate(value):
            _safe_payload(nested, path=f"{path}[{index}]")


def _reject_browser_authority(value: object) -> None:
    """Reject mass-assignment attempts for server-owned authority fields."""

    if isinstance(value, Mapping):
        for raw_key, nested in value.items():
            key = str(raw_key).strip().casefold()
            if key in _BROWSER_AUTHORITY_FIELDS:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "code": "BROWSER_AUTHORITY_REJECTED",
                        "message": "Authority fields are derived from the authenticated session",
                    },
                )
            _reject_browser_authority(nested)
    elif isinstance(value, (list, tuple)):
        for nested in value:
            _reject_browser_authority(nested)


def _authenticated(
    request: Request,
    identity: HumanIdentityService,
    *,
    now: datetime,
) -> AuthenticatedHuman:
    token = request.cookies.get(SESSION_COOKIE, "")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "SESSION_REQUIRED", "message": "Web session is required"},
        )
    try:
        return identity.authenticate_session(session_token=token, now=now)
    except HumanAuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_SESSION", "message": "Web session is not usable"},
        ) from exc


def _csrf(
    request: Request,
    identity: HumanIdentityService,
    authority: AuthenticatedHuman,
) -> None:
    header_token = request.headers.get(CSRF_HEADER, "")
    cookie_token = request.cookies.get(CSRF_COOKIE, "")
    if not header_token or not cookie_token or header_token != cookie_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "CSRF_REQUIRED", "message": "Valid CSRF proof is required"},
        )
    try:
        identity.assert_csrf(authority, header_token)
    except CsrfValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "CSRF_INVALID", "message": "Valid CSRF proof is required"},
        ) from exc


def _authorized(
    authority: AuthenticatedHuman,
    permission: PortalPermission,
    *,
    unit_id: str | None = None,
) -> None:
    try:
        authority.assert_permission(permission, unit_id=unit_id)
    except HumanAuthorizationError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "PORTAL_FORBIDDEN", "message": "Operation is not permitted"},
        ) from exc


def create_portal_router(
    identity: HumanIdentityService,
    executor: HumanPortalExecutor | None,
) -> APIRouter:
    router = APIRouter(prefix="/v1/portal", tags=["human-portal"])

    def authority(request: Request) -> AuthenticatedHuman:
        return _authenticated(request, identity, now=datetime.now(UTC))

    def require_executor() -> HumanPortalExecutor:
        if executor is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "code": "PORTAL_RUNTIME_NOT_READY",
                    "message": "Portal product executor is not configured",
                },
            )
        return executor

    @router.get("/bootstrap")
    async def bootstrap(request: Request) -> dict[str, Any]:
        auth = authority(request)
        _authorized(auth, PortalPermission.PORTAL_READ)
        projection = dict(require_executor().snapshot(authority=auth))
        _safe_payload(projection)
        return {
            "product": "FM NFCORE",
            "version": "1.0",
            "tenant_id": auth.account.tenant_id,
            "unit_ids": sorted(auth.account.unit_ids) if auth.account.unit_ids is not None else None,
            "role": auth.account.role.value,
            "permissions": sorted(permission.value for permission in auth.permissions),
            "supported_documents": ["nfe", "nfce", "nfse"],
            "projection": projection,
        }

    @router.get("/surfaces/{surface_id}")
    async def surface(surface_id: str, request: Request) -> dict[str, Any]:
        permission = _SURFACE_PERMISSIONS.get(surface_id)
        if permission is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "UNKNOWN_PORTAL_SURFACE", "message": "Unknown portal surface"},
            )
        auth = authority(request)
        unit_id = request.query_params.get("unit_id")
        _authorized(auth, permission, unit_id=unit_id)
        rows = [dict(row) for row in require_executor().surface(surface_id=surface_id, authority=auth)]
        _safe_payload(rows)
        return {"surface": surface_id, "rows": rows}

    @router.post("/operations/{operation_id}")
    async def execute_operation(
        operation_id: str,
        request: Request,
        payload: Annotated[dict[str, Any], Body()],
    ) -> dict[str, Any]:
        permission = _OPERATION_PERMISSIONS.get(operation_id)
        if permission is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "UNKNOWN_PORTAL_OPERATION", "message": "Unknown portal operation"},
            )
        auth = authority(request)
        _reject_browser_authority(payload)
        unit_id = payload.get("unit_id")
        if unit_id is not None and not isinstance(unit_id, str):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "INVALID_UNIT", "message": "unit_id must be text"},
            )
        _authorized(auth, permission, unit_id=unit_id)
        _csrf(request, identity, auth)
        idempotency_key = request.headers.get("Idempotency-Key")
        if operation_id in _IDEMPOTENT_MUTATIONS and not (idempotency_key or "").strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "MISSING_IDEMPOTENCY_KEY",
                    "message": "Idempotency-Key is required",
                },
            )
        result = dict(
            require_executor().execute(
                operation_id=operation_id,
                authority=auth,
                payload=payload,
                idempotency_key=idempotency_key.strip() if idempotency_key else None,
            )
        )
        _safe_payload(result)
        return result

    return router
