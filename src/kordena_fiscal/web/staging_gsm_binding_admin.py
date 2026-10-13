"""Staging pilot GSM binding administration via existing human session authority."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request

from kordena_fiscal.runtime.secret_manager import SecretBindingAdministration
from kordena_fiscal.security.human_identity import HumanIdentityService
from kordena_fiscal.security.secret_binding import SecretBinding
from kordena_fiscal.security.secrets import SecretResolutionError
from kordena_fiscal.web.human_auth import CSRF_COOKIE, CSRF_HEADER, SESSION_COOKIE

_PILOT_TENANT = "nfcore-staging-e2e"
_PILOT_UNIT = "pilot-gsm-staging"
_PILOT_REFERENCE = "sec_nfcore_staging_pilot_gsm_signing_01"
_PILOT_RESOURCE = "projects/fm-nfcore-staging/secrets/nfcore-stg-pilot-webhook-signing"


def create_staging_gsm_binding_router(
    identity: HumanIdentityService,
    administration: SecretBindingAdministration,
) -> APIRouter:
    router = APIRouter(tags=["staging-gsm-pilot"])

    @router.post("/internal/staging/gsm-binding", include_in_schema=False)
    async def register_binding(request: Request) -> dict[str, str]:
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
        if not actor.account.is_platform_admin or not actor.account.enabled:
            raise HTTPException(status_code=403, detail="PLATFORM_ADMIN_REQUIRED")
        try:
            # All authoritative scope fields are server-owned for this pilot.
            binding = SecretBinding(
                reference_id=_PILOT_REFERENCE,
                tenant_id=_PILOT_TENANT,
                unit_id=_PILOT_UNIT,
                purpose="webhook-signing",
                runtime_environment="staging",
                fiscal_environment=None,
                provider_id="google-secret-manager",
                workload_id="nfcore-worker",
                kind="signature",
                canonical_version=1,
                resource=_PILOT_RESOURCE,
                cloud_version="1",
            )
            administration.put(
                actor=actor,
                binding=binding,
                expected_revision=0,
                correlation_id=uuid4().hex,
            )
        except SecretResolutionError:
            raise HTTPException(status_code=409, detail="GSM_BINDING_DENIED") from None
        return {"status": "bound", "reference_id": _PILOT_REFERENCE}

    return router
