"""Public and platform-admin HTTP surfaces for commercial release governance."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Body, HTTPException, Request, status

from kordena_fiscal.control_plane.cakto_checkout import (
    CaktoCheckoutAdministrationService,
    CaktoCheckoutProjection,
    CaktoCheckoutStatus,
)
from kordena_fiscal.control_plane.commercial_release import (
    CommercialReleaseAdministrationService,
)
from kordena_fiscal.control_plane.pricing_admin import (
    CommercialPricingAdministrationService,
)
from kordena_fiscal.product.commercial_release import (
    CommercialReleaseDecision,
    CommercialReleaseError,
)
from kordena_fiscal.security.human_identity import HumanIdentityService
from kordena_fiscal.web.portal_api import _csrf
from kordena_fiscal.web.pricing_admin import _platform_actor, _public_catalog


def create_commercial_release_router(
    identity: HumanIdentityService,
    pricing: CommercialPricingAdministrationService,
    release: CommercialReleaseAdministrationService,
    checkout: CaktoCheckoutAdministrationService | None = None,
    *,
    cakto_processing_configured: bool = False,
) -> APIRouter:
    router = APIRouter(tags=["commercial-release"])

    @router.get("/v1/commercial/offer")
    async def public_offer() -> dict[str, object]:
        pricing_current = pricing.current
        release_current = release.current
        pricing_payload: dict[str, object]
        if pricing_current is None:
            pricing_payload = {
                "status": "unpriced",
                "catalog": None,
            }
        else:
            pricing_payload = {
                "status": "published",
                "catalog": _public_catalog(pricing_current),
            }

        release_payload: dict[str, object] = {
            "status": "unavailable",
            "version": None,
            "public_message": None,
            "commercially_approved": False,
        }
        if release_current is not None:
            release_payload = {
                "status": release_current.status.value,
                "version": release_current.version,
                "public_message": release_current.public_message,
                "commercially_approved": release_current.commercially_approved,
            }

        checkout_projection = (
            CaktoCheckoutProjection(
                status=CaktoCheckoutStatus.UNCONFIGURED,
                expected_count=0,
                configured_count=0,
                items=(),
            )
            if checkout is None
            else checkout.project(pricing_current)
        )
        commercially_approved = (
            release_current is not None and release_current.commercially_approved
        )
        purchase_enabled = bool(
            commercially_approved
            and checkout_projection.status is CaktoCheckoutStatus.CONFIGURED
            and checkout_projection.items
            and cakto_processing_configured
        )
        checkout_payload = checkout_projection.to_public_mapping(
            processing_configured=cakto_processing_configured,
            expose_urls=purchase_enabled,
        )

        return {
            "product_id": "nfcore",
            "pricing": pricing_payload,
            "release": release_payload,
            "checkout": checkout_payload,
            "purchase_enabled": purchase_enabled,
            # Trial release is a separate authority and is not inferred from trial_days.
            "trial_enabled": False,
        }

    @router.get("/v1/admin/commercial-release")
    async def admin_release(request: Request) -> dict[str, object]:
        _authority, _actor = _platform_actor(request, identity)
        current = release.current
        history = release.history()
        return {
            "current": None if current is None else current.to_mapping(),
            "history": [
                {
                    "version": publication.decision.version,
                    "status": publication.decision.status.value,
                    "public_message": publication.decision.public_message,
                    "human_decision_reference": (
                        publication.decision.human_decision_reference
                    ),
                    "actor_id": publication.actor_id,
                    "correlation_id": publication.correlation_id,
                    "published_at": publication.published_at.isoformat(),
                }
                for publication in history
            ],
        }

    @router.post("/v1/admin/commercial-release")
    async def publish_release(
        request: Request,
        payload: Annotated[dict[str, Any], Body()],
    ) -> dict[str, object]:
        authority, actor = _platform_actor(request, identity)
        _csrf(request, identity, authority)
        raw_decision = payload.get("decision")
        expected_version = payload.get("expected_version")
        if not isinstance(raw_decision, dict):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "INVALID_COMMERCIAL_RELEASE",
                    "message": "decision must be an object",
                },
            )
        if expected_version is not None and (
            not isinstance(expected_version, int) or isinstance(expected_version, bool)
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "INVALID_EXPECTED_VERSION",
                    "message": "expected_version must be integer or null",
                },
            )
        try:
            decision = CommercialReleaseDecision.from_mapping(raw_decision)
            published = release.publish(
                actor=actor,
                decision=decision,
                expected_version=expected_version,
                correlation_id=request.headers.get("X-Correlation-Id", "").strip()
                or uuid4().hex,
            )
        except CommercialReleaseError as exc:
            code = (
                status.HTTP_409_CONFLICT
                if "version" in str(exc).casefold()
                else status.HTTP_400_BAD_REQUEST
            )
            raise HTTPException(
                status_code=code,
                detail={
                    "code": "COMMERCIAL_RELEASE_REJECTED",
                    "message": str(exc),
                },
            ) from exc
        return {"decision": published.to_mapping()}

    return router
