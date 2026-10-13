"""Governed staging webhook destination request and platform egress approval.

This module reuses the existing human session, CSRF, commercial repository,
versioning, immutable audit and fail-closed DNS/TLS egress policy.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request

from kordena_fiscal.control_plane.commercial import WebhookDestinationConfig
from kordena_fiscal.control_plane.models import (
    ControlPlaneAuditAction,
    ControlPlaneAuditEvent,
)
from kordena_fiscal.control_plane.webhook_policy import normalize_webhook_url
from kordena_fiscal.domain import ExecutionScope, FiscalEnvironment
from kordena_fiscal.persistence.ports import FiscalUnitOfWorkFactory
from kordena_fiscal.security.human_identity import (
    AuthenticatedHuman,
    HumanIdentityService,
    PortalPermission,
)
from kordena_fiscal.web.human_auth import CSRF_COOKIE, CSRF_HEADER, SESSION_COOKIE

_TENANT = "nfcore-staging-e2e"
_UNIT = "pilot-gsm-staging"
_DESTINATION = "nfcore-staging-webhook-probe"
_HOST = "nfcore-staging"
_URL = "https://nfcore-api-production.up.railway.app/internal/staging/webhook-probe"


def _actor(request: Request, identity: HumanIdentityService) -> AuthenticatedHuman:
    token = request.cookies.get(SESSION_COOKIE, "")
    csrf = request.headers.get(CSRF_HEADER, "")
    if not token:
        raise HTTPException(status_code=401, detail="SESSION_REQUIRED")
    if not csrf or csrf != request.cookies.get(CSRF_COOKIE, ""):
        raise HTTPException(status_code=403, detail="CSRF_REQUIRED")
    try:
        actor = identity.authenticate_session(session_token=token, now=datetime.now(UTC))
        identity.assert_csrf(actor, csrf)
    except Exception:
        raise HTTPException(status_code=403, detail="SESSION_OR_CSRF_DENIED") from None
    if not actor.account.enabled:
        raise HTTPException(status_code=403, detail="ACCOUNT_DISABLED")
    return actor


def _scope() -> ExecutionScope:
    return ExecutionScope(
        tenant_id=_TENANT,
        unit_id=_UNIT,
        environment=FiscalEnvironment.HOMOLOGATION,
        host_namespace=_HOST,
        correlation_id=uuid4().hex,
    )


def _audit(
    scope: ExecutionScope,
    actor: AuthenticatedHuman,
    action: ControlPlaneAuditAction,
) -> ControlPlaneAuditEvent:
    return ControlPlaneAuditEvent(
        event_id=uuid4().hex,
        occurred_at=datetime.now(UTC),
        actor_id=actor.account.account_id,
        action=action,
        target_type="webhook_destination",
        target_id=_DESTINATION,
        correlation_id=scope.correlation_id,
        tenant_id=scope.tenant_id,
        unit_id=scope.unit_id,
    )


def create_staging_webhook_egress_router(
    identity: HumanIdentityService,
    uow_factory: FiscalUnitOfWorkFactory,
) -> APIRouter:
    router = APIRouter(tags=["staging-webhook-egress"])

    @router.post("/internal/staging/webhook-destination/request", include_in_schema=False)
    async def request_destination(request: Request) -> dict[str, str]:
        actor = _actor(request, identity)
        try:
            actor.assert_permission(PortalPermission.INTEGRATION_MANAGE, unit_id=_UNIT)
        except Exception:
            raise HTTPException(status_code=403, detail="INTEGRATION_MANAGE_REQUIRED") from None
        if actor.account.tenant_id != _TENANT and not actor.account.is_platform_admin:
            raise HTTPException(status_code=403, detail="TENANT_SCOPE_DENIED")
        scope = _scope()
        destination = WebhookDestinationConfig(
            destination_id=_DESTINATION,
            tenant_id=_TENANT,
            unit_id=_UNIT,
            environment=FiscalEnvironment.HOMOLOGATION,
            url=_URL,
        )
        try:
            with uow_factory() as uow:
                unit = uow.control_plane.get_unit(_TENANT, _UNIT)
                if unit is None or FiscalEnvironment.HOMOLOGATION not in unit.enabled_environments:
                    raise ValueError("unit not enabled")
                current = uow.commercial.configuration_version(scope, "webhooks", _DESTINATION)
                uow.commercial.put_webhook_destination(destination)
                version = uow.commercial.advance_configuration_version(
                    scope, "webhooks", _DESTINATION, current
                )
                uow.commercial.record_webhook_approval(
                    scope, _DESTINATION, status="pending", version=None,
                    expires_at=None, url_sha256=None,
                    requested_by=actor.account.account_id, approved_by=None,
                )
                uow.control_plane.append_audit(
                    _audit(scope, actor, ControlPlaneAuditAction.CUSTOMER_CONFIGURATION_CHANGED)
                )
                uow.commit()
        except ValueError:
            raise HTTPException(status_code=409, detail="DESTINATION_REQUEST_DENIED") from None
        return {"status": "pending", "destination_id": _DESTINATION, "version": str(version)}

    @router.post("/internal/staging/webhook-destination/approve", include_in_schema=False)
    async def approve_destination(request: Request) -> dict[str, str]:
        actor = _actor(request, identity)
        if not actor.account.is_platform_admin:
            raise HTTPException(status_code=403, detail="PLATFORM_ADMIN_REQUIRED")
        scope = _scope()
        canonical, _hostname, _path = normalize_webhook_url(_URL)
        expires = datetime.now(UTC) + timedelta(hours=2)
        try:
            with uow_factory() as uow:
                unit = uow.control_plane.get_unit(_TENANT, _UNIT)
                record = uow.commercial.webhook_approval(scope, _DESTINATION)
                version = uow.commercial.configuration_version(scope, "webhooks", _DESTINATION)
                if (
                    unit is None
                    or FiscalEnvironment.HOMOLOGATION not in unit.enabled_environments
                    or record is None
                    or not record["enabled"]
                    or record["approval_status"] != "pending"
                    or record["url"] != canonical
                    or not record["requested_by"]
                    or version < 1
                ):
                    raise ValueError("destination missing, changed or not pending")
                uow.commercial.record_webhook_approval(
                    scope, _DESTINATION,
                    status="approved", version=version,
                    expires_at=expires.isoformat(),
                    url_sha256=hashlib.sha256(canonical.encode()).hexdigest(),
                    approved_by=actor.account.account_id,
                )
                uow.control_plane.append_audit(
                    _audit(scope, actor, ControlPlaneAuditAction.WEBHOOK_EGRESS_DECIDED)
                )
                uow.commit()
        except ValueError:
            raise HTTPException(status_code=409, detail="WEBHOOK_APPROVAL_DENIED") from None
        return {"status": "approved", "destination_id": _DESTINATION, "version": str(version)}

    return router
