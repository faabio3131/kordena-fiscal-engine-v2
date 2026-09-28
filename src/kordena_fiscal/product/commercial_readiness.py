"""Deterministic commercial delivery-path readiness for public purchase gating.

This value object is a projection of already-composed NFCORE capabilities. It is not
an authority and cannot approve a release, configure pricing, select checkout or
create commercial state.
"""

from __future__ import annotations

from dataclasses import dataclass


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


__all__ = ["CommercialDeliveryPathReadiness"]
