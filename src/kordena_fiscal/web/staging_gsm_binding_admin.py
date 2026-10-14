"""Staging pilot GSM binding administration via existing human session authority."""

from __future__ import annotations

from dataclasses import replace
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
            existing_worker = administration.current_binding(binding.reference_id)
            worker_revision = 0
            if existing_worker is not None:
                if (
                    existing_worker.cloud_version not in {"1", "3"}
                    or replace(existing_worker, revision=1, cloud_version="3") != replace(binding, cloud_version="3")
                ):
                    raise SecretResolutionError("GSM worker binding conflict")
                if existing_worker.cloud_version == "3":
                    binding = existing_worker
                else:
                    worker_revision = existing_worker.revision
                    binding = replace(existing_worker, revision=existing_worker.revision + 1, cloud_version="3")
            else:
                binding = replace(binding, cloud_version="3")
            administration.put(
                actor=actor,
                binding=binding,
                expected_revision=worker_revision,
                correlation_id=uuid4().hex,
            )
            verification_binding = SecretBinding(
                reference_id="sec_nfcore_staging_pilot_gsm_verify_01",
                tenant_id=_PILOT_TENANT,
                unit_id=_PILOT_UNIT,
                purpose="webhook-signing",
                runtime_environment="staging",
                fiscal_environment=None,
                provider_id="google-secret-manager",
                workload_id="nfcore-api",
                kind="signature",
                canonical_version=1,
                resource=_PILOT_RESOURCE,
                cloud_version="2",
            )
            existing = administration.current_binding(verification_binding.reference_id)
            expected_revision = 0
            if existing is not None:
                if (
                    existing.cloud_version not in {"1", "2"}
                    or replace(existing, revision=1, cloud_version="2")
                    != verification_binding
                ):
                    raise SecretResolutionError("GSM verifier binding conflict")
                if existing.cloud_version == "2":
                    verification_binding = existing  # Safe idempotent replay.
                else:
                    expected_revision = existing.revision
                    verification_binding = replace(
                        existing, revision=existing.revision + 1, cloud_version="2"
                    )
            administration.put(
                actor=actor,
                binding=verification_binding,
                expected_revision=expected_revision,
                correlation_id=uuid4().hex,
            )
        except SecretResolutionError:
            raise HTTPException(status_code=409, detail="GSM_BINDING_DENIED") from None
        return {"status": "bound", "reference_id": _PILOT_REFERENCE}

    return router
