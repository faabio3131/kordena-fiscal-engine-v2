"""Commercial pricing HTTP surfaces for FM NFCORE.

The public route exposes only active sellable catalog data. Mutations reuse the
canonical human session/CSRF authority and require the explicit platform_admin flag;
tenant OWNER/ADMIN roles never imply platform authority.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Body, HTTPException, Request, status

from kordena_fiscal.control_plane.models import AdminPrincipal, ControlPlanePermission
from kordena_fiscal.control_plane.pricing_admin import (
    CommercialPricingAdministrationService,
)
from kordena_fiscal.product.pricing import (
    CommercialPricingConfiguration,
    CommercialPricingError,
)
from kordena_fiscal.security.human_identity import AuthenticatedHuman, HumanIdentityService
from kordena_fiscal.web.portal_api import _authenticated, _csrf


def _platform_actor(
    request: Request,
    identity: HumanIdentityService,
) -> tuple[AuthenticatedHuman, AdminPrincipal]:
    authority = _authenticated(request, identity, now=datetime.now(UTC))
    if not authority.account.platform_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "PLATFORM_ADMIN_REQUIRED",
                "message": "Platform administration authority is required",
            },
        )
    return authority, AdminPrincipal(
        actor_id=authority.account.account_id,
        permissions=frozenset({ControlPlanePermission.COMMERCIAL_CONFIG_WRITE}),
        global_scope=True,
    )


def _public_catalog(
    configuration: CommercialPricingConfiguration,
) -> dict[str, object]:
    """Project only public sellable configuration; private overrides stay internal."""

    active_prices = tuple(price for price in configuration.prices if price.enabled)
    active_price_ids = {price.price_id for price in active_prices}
    prices = [
        {
            "price_id": price.price_id,
            "currency": price.currency,
            "cadence": price.cadence.value,
            "base_amount": str(price.base_amount),
            "per_document_amount": str(price.per_document_amount),
            "setup_amount": str(price.setup_amount),
        }
        for price in active_prices
    ]
    plans = [
        {
            "plan_id": plan.plan_id,
            "display_name": plan.display_name,
            "edition_id": plan.edition_id,
            "price_ids": [
                price_id for price_id in plan.price_ids if price_id in active_price_ids
            ],
            "trial_days": plan.trial_days,
            "tags": list(plan.tags),
        }
        for plan in configuration.plans
        if plan.enabled
    ]
    return {
        "configuration_id": configuration.configuration_id,
        "version": configuration.version,
        "prices": prices,
        "plans": plans,
    }


def create_pricing_router(
    identity: HumanIdentityService,
    pricing: CommercialPricingAdministrationService,
) -> APIRouter:
    router = APIRouter(tags=["commercial-pricing"])

    @router.get("/v1/commercial/pricing")
    async def public_pricing() -> dict[str, object]:
        current = pricing.current
        if current is None:
            return {
                "status": "unpriced",
                "catalog": None,
                "message": "Commercial pricing has not been published yet",
            }
        return {"status": "published", "catalog": _public_catalog(current)}

    @router.get("/v1/admin/pricing")
    async def admin_pricing(request: Request) -> dict[str, object]:
        _authority, _actor = _platform_actor(request, identity)
        current = pricing.current
        history = pricing.history()
        return {
            "current": None if current is None else current.to_mapping(),
            "history": [
                {
                    "version": publication.configuration.version,
                    "configuration_id": publication.configuration.configuration_id,
                    "actor_id": publication.actor_id,
                    "correlation_id": publication.correlation_id,
                    "published_at": publication.published_at.isoformat(),
                }
                for publication in history
            ],
        }

    @router.post("/v1/admin/pricing")
    async def publish_pricing(
        request: Request,
        payload: Annotated[dict[str, Any], Body()],
    ) -> dict[str, object]:
        authority, actor = _platform_actor(request, identity)
        _csrf(request, identity, authority)
        raw_configuration = payload.get("configuration")
        expected_version = payload.get("expected_version")
        if not isinstance(raw_configuration, dict):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "INVALID_PRICING_CONFIGURATION",
                    "message": "configuration must be an object",
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
            configuration = CommercialPricingConfiguration.from_mapping(raw_configuration)
            published = pricing.publish(
                actor=actor,
                configuration=configuration,
                expected_version=expected_version,
                correlation_id=request.headers.get("X-Correlation-Id", "").strip()
                or uuid4().hex,
            )
        except CommercialPricingError as exc:
            code = (
                status.HTTP_409_CONFLICT
                if "version" in str(exc).casefold()
                else status.HTTP_400_BAD_REQUEST
            )
            raise HTTPException(
                status_code=code,
                detail={
                    "code": "PRICING_PUBLICATION_REJECTED",
                    "message": str(exc),
                },
            ) from exc
        return {"catalog": published.to_mapping()}

    return router
