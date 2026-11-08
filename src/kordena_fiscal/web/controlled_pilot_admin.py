"""Self-service admin surface for the certified V2-15 B5 Controlled Pilot gate.

Lets an existing platform admin (reusing the NFCore portal's own session and
CSRF authority — no new auth system) activate/deactivate a HOMOLOGATION-only
Controlled Pilot cell for an exact tenant/unit/provider/document/jurisdiction,
and read its internal-vs-external readiness, without any engineer writing or
running code per client. This never performs a fiscal provider call, never
touches real fiscal production, and never accepts a certificate or secret
material directly (those are configured through the existing self-service
Empresas/Unidades/Certificados/Provedores portal surfaces).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Body, HTTPException, Request, status

from kordena_fiscal.control_plane.models import AdminPrincipal, ControlPlanePermission
from kordena_fiscal.domain import (
    BrazilianJurisdiction,
    ExecutionScope,
    FiscalDocumentKind,
    FiscalEnvironment,
    FiscalValidationError,
)
from kordena_fiscal.gateway import ProviderOperation
from kordena_fiscal.runtime.controlled_pilots import (
    ControlledPilotGovernanceService,
    ControlledPilotScope,
)
from kordena_fiscal.security.human_identity import HumanIdentityService
from kordena_fiscal.web.portal_api import _authenticated, _csrf

_HOST_NAMESPACE = "fm-nfcore"


def _admin_principal(actor: Any) -> AdminPrincipal:
    return AdminPrincipal(
        actor_id=actor.account.account_id,
        permissions=frozenset({ControlPlanePermission.COMMERCIAL_CONFIG_WRITE}),
        global_scope=True,
    )


def _build_scope(payload: dict[str, Any]) -> ControlledPilotScope:
    try:
        tenant_id = str(payload["tenant_id"])
        unit_id = str(payload["unit_id"])
        pilot_id = str(payload["pilot_id"])
        document_kind = FiscalDocumentKind(str(payload["document_kind"]))
        jurisdiction_payload = payload["jurisdiction"]
        jurisdiction = BrazilianJurisdiction(
            state_code=str(jurisdiction_payload["state_code"]),
            municipality_ibge_code=(
                str(jurisdiction_payload["municipality_ibge_code"])
                if jurisdiction_payload.get("municipality_ibge_code")
                else None
            ),
        )
        provider_id = str(payload["provider_id"])
        allowed_operations = frozenset(
            ProviderOperation(str(item)) for item in payload["allowed_operations"]
        )
    except (KeyError, ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_PILOT_SCOPE", "message": "Dados do piloto inválidos"},
        ) from exc
    try:
        scope = ExecutionScope(
            tenant_id=tenant_id,
            unit_id=unit_id,
            environment=FiscalEnvironment.HOMOLOGATION,
            correlation_id=uuid4().hex,
            host_namespace=_HOST_NAMESPACE,
        )
        return ControlledPilotScope(
            pilot_id=pilot_id,
            scope=scope,
            document_kind=document_kind,
            jurisdiction=jurisdiction,
            provider_id=provider_id,
            allowed_operations=allowed_operations,
        )
    except FiscalValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_PILOT_SCOPE", "message": str(exc)},
        ) from exc


def create_controlled_pilot_admin_router(
    identity: HumanIdentityService,
    pilot_service: ControlledPilotGovernanceService,
) -> APIRouter:
    router = APIRouter(tags=["controlled-pilot-admin"])

    def _authorize(request: Request) -> AdminPrincipal:
        authority = _authenticated(request, identity, now=datetime.now(UTC))
        if not authority.account.platform_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "PLATFORM_ADMIN_REQUIRED",
                    "message": "Platform administration authority is required",
                },
            )
        _csrf(request, identity, authority)
        return _admin_principal(authority)

    @router.post("/admin/controlled-pilots/activate", include_in_schema=False)
    async def activate(
        request: Request, body: Annotated[dict[str, Any], Body()]
    ) -> dict[str, Any]:
        actor = _authorize(request)
        pilot = _build_scope(body)
        correlation_id = uuid4().hex
        now = datetime.now(UTC)
        try:
            pilot_service.activate(
                actor=actor, pilot=pilot, correlation_id=correlation_id, now=now,
            )
        except FiscalValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "PILOT_ACTIVATION_DENIED", "message": str(exc)},
            ) from None
        readiness = pilot_service.assess_external_scope(pilot=pilot)
        return {
            "status": "activated",
            "pilot_id": pilot.pilot_id,
            "module_id": pilot.module_id,
            "internal_ready": readiness.internal_ready,
            "official_evidence_complete": readiness.official_evidence_complete,
            "internal_reasons": list(readiness.internal_reasons),
            "external_reasons": list(readiness.external_reasons),
        }

    @router.post("/admin/controlled-pilots/deactivate", include_in_schema=False)
    async def deactivate(
        request: Request, body: Annotated[dict[str, Any], Body()]
    ) -> dict[str, Any]:
        actor = _authorize(request)
        pilot = _build_scope(body)
        pilot_service.deactivate(
            actor=actor, pilot=pilot, correlation_id=uuid4().hex, now=datetime.now(UTC),
        )
        return {"status": "deactivated", "pilot_id": pilot.pilot_id}

    @router.post("/admin/controlled-pilots/assess", include_in_schema=False)
    async def assess(
        request: Request, body: Annotated[dict[str, Any], Body()]
    ) -> dict[str, Any]:
        _authorize(request)
        pilot = _build_scope(body)
        readiness = pilot_service.assess_external_scope(pilot=pilot)
        return {
            "pilot_id": pilot.pilot_id,
            "internal_ready": readiness.internal_ready,
            "official_evidence_complete": readiness.official_evidence_complete,
            "internal_reasons": list(readiness.internal_reasons),
            "external_reasons": list(readiness.external_reasons),
        }

    return router


__all__ = ["create_controlled_pilot_admin_router"]
