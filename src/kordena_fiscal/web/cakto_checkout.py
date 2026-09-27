"""Platform administration HTTP surface for canonical Cakto checkout bindings."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Body, HTTPException, Request, status

from kordena_fiscal.control_plane.cakto_checkout import (
    CaktoCheckoutAdministrationService,
)
from kordena_fiscal.product.cakto import CaktoPayloadError, CaktoPlanBinding
from kordena_fiscal.security.human_identity import HumanIdentityService
from kordena_fiscal.web.portal_api import _csrf
from kordena_fiscal.web.pricing_admin import _platform_actor


def _binding_mapping(binding: CaktoPlanBinding) -> dict[str, object]:
    return {
        "external_product_id": binding.external_product_id,
        "external_offer_id": binding.external_offer_id,
        "plan_id": binding.plan_id,
        "entitlement_ids": list(binding.entitlement_ids),
        "enabled": binding.enabled,
        "checkout_url": binding.checkout_url,
    }


def create_cakto_checkout_router(
    identity: HumanIdentityService,
    checkout: CaktoCheckoutAdministrationService,
) -> APIRouter:
    router = APIRouter(tags=["commercial-checkout"])

    @router.get("/v1/admin/checkout/cakto")
    async def checkout_admin(request: Request) -> dict[str, object]:
        _authority, actor = _platform_actor(request, identity)
        bindings = checkout.bindings(actor=actor)
        return {"provider": "cakto", "bindings": [_binding_mapping(item) for item in bindings]}

    @router.post("/v1/admin/checkout/cakto")
    async def configure_checkout(
        request: Request,
        payload: Annotated[dict[str, Any], Body()],
    ) -> dict[str, object]:
        authority, actor = _platform_actor(request, identity)
        _csrf(request, identity, authority)

        external_product_id = payload.get("external_product_id")
        external_offer_id = payload.get("external_offer_id")
        plan_id = payload.get("plan_id")
        entitlement_ids = payload.get("entitlement_ids")
        enabled = payload.get("enabled", True)

        if (
            not isinstance(external_product_id, str)
            or not isinstance(external_offer_id, str)
            or not isinstance(plan_id, str)
            or not isinstance(entitlement_ids, list)
            or not all(isinstance(item, str) for item in entitlement_ids)
            or not isinstance(enabled, bool)
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "INVALID_CAKTO_CHECKOUT_BINDING",
                    "message": "Cakto checkout binding payload is invalid",
                },
            )
        try:
            binding = CaktoPlanBinding(
                external_product_id=external_product_id,
                external_offer_id=external_offer_id,
                plan_id=plan_id,
                entitlement_ids=tuple(entitlement_ids),
                enabled=enabled,
            )
            persisted = checkout.set_binding(actor=actor, binding=binding)
        except CaktoPayloadError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "INVALID_CAKTO_CHECKOUT_BINDING",
                    "message": str(exc),
                },
            ) from exc

        return {"provider": "cakto", "binding": _binding_mapping(persisted)}

    return router
