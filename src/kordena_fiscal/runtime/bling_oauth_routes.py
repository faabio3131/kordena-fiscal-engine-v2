"""Human-session Bling OAuth administration: canonical binding, RBAC and CSRF."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Body, HTTPException, Request
from fastapi.responses import JSONResponse

from kordena_fiscal.domain import ExecutionScope, FiscalEnvironment
from kordena_fiscal.persistence.bling_installations import BlingInstallationRepository
from kordena_fiscal.persistence.ports import PersistenceConflictError
from kordena_fiscal.security.human_identity import HumanIdentityService, PortalPermission
from kordena_fiscal.web.portal_api import _authenticated, _authorized, _csrf

from .bling_oauth_service import BlingOAuthService, BlingOAuthUnavailable


def build_bling_oauth_router(
    identity: HumanIdentityService,
    installations: BlingInstallationRepository,
    oauth: BlingOAuthService,
) -> APIRouter:
    router = APIRouter(prefix="/v1/portal/integrations/bling", tags=["bling-oauth"])

    def by_binding(request: Request, binding_id: str) -> tuple[Any, ExecutionScope]:
        human = _authenticated(request, identity, now=datetime.now(UTC))
        if not binding_id or len(binding_id) > 128:
            raise HTTPException(422, detail={"code": "BLING_BINDING_INVALID"})
        with installations.database() as uow:
            binding = uow.bindings.get_by_id(binding_id)
        if binding is None or binding.fiscal_account_id.value != human.tenant_id:
            raise HTTPException(404, detail={"code": "BLING_BINDING_NOT_FOUND"})
        _authorized(
            human, PortalPermission.INTEGRATION_MANAGE, unit_id=binding.fiscal_unit_id.value,
        )
        scope = binding.to_execution_scope(
            environment=FiscalEnvironment.HOMOLOGATION,
            correlation_id="bling-web-oauth",
        )
        return human, scope

    def by_installation(request: Request, installation_id: str) -> tuple[Any, ExecutionScope]:
        human = _authenticated(request, identity, now=datetime.now(UTC))
        view = installations.get_by_id(installation_id)
        if view is None or human.tenant_id != view.tenant_id:
            raise HTTPException(404, detail={"code": "BLING_INSTALLATION_NOT_FOUND"})
        _authorized(human, PortalPermission.INTEGRATION_MANAGE, unit_id=view.unit_id)
        scope = ExecutionScope(
            tenant_id=view.tenant_id,
            unit_id=view.unit_id,
            environment=view.environment,
            correlation_id="bling-web-oauth",
            host_namespace="bling",
        )
        return human, scope

    @router.post("/installations")
    def create(request: Request, body: Annotated[dict[str, Any], Body()]) -> JSONResponse:
        if set(body) != {"binding_id", "company_id"}:
            raise HTTPException(422, detail={"code": "BLING_INPUT_INVALID"})
        human, scope = by_binding(request, str(body["binding_id"]))
        _csrf(request, identity, human)
        with installations.database() as uow:
            binding = uow.bindings.get_by_id(str(body["binding_id"]))
        if binding is None:
            raise HTTPException(404, detail={"code": "BLING_BINDING_NOT_FOUND"})
        try:
            view = installations.create(
                host_scope=binding.host_scope,
                company_id=body["company_id"],
                environment=scope.environment,
            )
        except (ValueError, PersistenceConflictError):
            raise HTTPException(409, detail={"code": "BLING_INSTALLATION_CONFLICT"}) from None
        return JSONResponse(
            status_code=201,
            content={"installation_id": view.installation_id, "state": view.state.value},
            headers={"Cache-Control": "no-store"},
        )

    @router.get("/installations")
    def list_installations(
        request: Request, binding_id: str, cursor: str | None = None, limit: int = 50,
    ) -> JSONResponse:
        _, scope = by_binding(request, binding_id)
        rows, following = installations.list_for_scope(scope, cursor=cursor, limit=limit)
        return JSONResponse(
            content={
                "rows": [{
                    "installation_id": row.installation_id,
                    "company_id": row.company_id,
                    "state": row.state.value,
                    "environment": row.environment.value,
                    "health_code": row.health_code,
                    "credential_status": row.credential_status,
                    "revision": row.revision,
                    "updated_at": row.updated_at.isoformat(),
                } for row in rows],
                "next_cursor": following,
            },
            headers={"Cache-Control": "no-store"},
        )

    @router.post("/installations/{installation_id}/connect")
    def connect(installation_id: str, request: Request) -> JSONResponse:
        human, scope = by_installation(request, installation_id)
        _csrf(request, identity, human)
        try:
            url = oauth.begin(
                scope, installation_id,
                actor_id=human.account.account_id, session_id=human.session_id,
            )
        except BlingOAuthUnavailable:
            raise HTTPException(503, detail={"code": "BLING_NOT_CONFIGURED"}) from None
        return JSONResponse(
            content={"authorization_url": url}, headers={"Cache-Control": "no-store"},
        )

    @router.get("/oauth/callback")
    def callback(request: Request, state: str = "", code: str = "", error: str = "") -> JSONResponse:
        human = _authenticated(request, identity, now=datetime.now(UTC))
        if error or not state or not code or len(state) != 64:
            raise HTTPException(400, detail={"code": "BLING_OAUTH_REJECTED"})
        # Resolve the installation ONLY from the server-stored one-use state.
        digest = hashlib.sha256(state.encode()).hexdigest()
        with installations.database.connection() as connection:
            match = connection.execute(
                "SELECT installation_id FROM fm_bling_oauth_flows "
                "WHERE state_sha256 = ? AND actor_id = ? AND session_id = ? "
                "AND consumed = 0 AND expires_at > ?",
                (digest, human.account.account_id, human.session_id,
                 datetime.now(UTC).isoformat()),
            ).fetchone()
        if match is None:
            raise HTTPException(403, detail={"code": "BLING_OAUTH_STATE_INVALID"})
        installation_id = str(match[0])
        _, scope = by_installation(request, installation_id)
        try:
            oauth.complete(
                scope, state=state, code=code,
                actor_id=human.account.account_id, session_id=human.session_id,
            )
        except (BlingOAuthUnavailable, PersistenceConflictError):
            raise HTTPException(409, detail={"code": "BLING_NEEDS_REAUTH"}) from None
        return JSONResponse(
            content={"state": "connected", "installation_id": installation_id},
            headers={"Cache-Control": "no-store"},
        )

    @router.post("/installations/{installation_id}/disconnect")
    def disconnect(installation_id: str, request: Request) -> JSONResponse:
        human, scope = by_installation(request, installation_id)
        _csrf(request, identity, human)
        try:
            oauth.revoke_local(scope, installation_id)
        except (BlingOAuthUnavailable, PersistenceConflictError):
            raise HTTPException(409, detail={"code": "BLING_INSTALLATION_CONFLICT"}) from None
        return JSONResponse(content={"state": "paused"}, headers={"Cache-Control": "no-store"})

    return router
