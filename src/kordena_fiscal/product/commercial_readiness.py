"""Deterministic commercial delivery-path readiness for public purchase gating.

This value object is a projection of already-composed NFCORE capabilities. It is not
an authority and cannot approve a release, configure pricing, select checkout or
create commercial state.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from kordena_fiscal.product.checkout import (
    CommercialCheckoutProjection,
    CommercialCheckoutStatus,
)
from kordena_fiscal.product.commercial_release import CommercialReleaseDecision
from kordena_fiscal.product.pricing import CommercialPricingConfiguration


@dataclass(frozen=True, slots=True)
class CommercialDeliveryPathReadiness:
    """Project whether a paid purchase can reach an activated NFCORE customer."""

    canonical_commercial_persistence: bool = False
    fulfillment: bool = False
    provisioning: bool = False
    activation_delivery: bool = False

    @property
    def ready(self) -> bool:
        return (
            self.canonical_commercial_persistence
            and self.fulfillment
            and self.provisioning
            and self.activation_delivery
        )

    def to_mapping(self) -> dict[str, bool]:
        return {
            "canonical_commercial_persistence": self.canonical_commercial_persistence,
            "fulfillment": self.fulfillment,
            "provisioning": self.provisioning,
            "activation_delivery": self.activation_delivery,
            "ready": self.ready,
        }


def commercial_purchase_ready(
    *,
    release: CommercialReleaseDecision | None,
    pricing: CommercialPricingConfiguration | None,
    checkout: CommercialCheckoutProjection,
    checkout_processing_configured: bool,
    delivery: CommercialDeliveryPathReadiness,
    operational_readiness: Callable[[], bool] | None = None,
) -> bool:
    """Return the single provider-neutral public charge gate."""

    configured = bool(
        release is not None
        and release.commercially_approved
        and pricing is not None
        and checkout.status is CommercialCheckoutStatus.CONFIGURED
        and checkout.items
        and checkout_processing_configured is True
        and delivery.ready
    )
    if not configured:
        return False
    if pricing is None:
        return False
    try:
        if not all(
            pricing.price(item.price_id).enabled
            and any(
                plan.enabled and plan.plan_id == item.plan_id and item.price_id in plan.price_ids
                for plan in pricing.plans
            )
            for item in checkout.items
        ):
            return False
        if operational_readiness is None:
            return True
        # An injected live check is a projection, never a release authority.
        return operational_readiness() is True
    except Exception:
        return False


__all__ = [
    "CommercialDeliveryPathReadiness",
    "commercial_purchase_ready",
]
