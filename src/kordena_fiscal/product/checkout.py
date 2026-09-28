"""Provider-neutral commercial checkout projection contracts for FM NFCORE.

Checkout providers are infrastructure adapters. The canonical commercial offer depends only
on this contract and must not depend on Cakto, Hotmart, Kax or any other external channel.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, runtime_checkable
from urllib.parse import urlsplit

from kordena_fiscal.domain import FiscalValidationError
from kordena_fiscal.product.pricing import CommercialPricingConfiguration

_PROVIDER_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")


class CommercialCheckoutStatus(StrEnum):
    UNCONFIGURED = "unconfigured"
    PARTIAL = "partial"
    CONFIGURED = "configured"


def normalize_checkout_provider_id(value: str) -> str:
    normalized = value.strip().lower()
    if not _PROVIDER_ID.fullmatch(normalized):
        raise FiscalValidationError("checkout provider_id is invalid")
    return normalized


def validate_checkout_url(value: str) -> str:
    normalized = value.strip()
    if not normalized or len(normalized) > 2048:
        raise FiscalValidationError("checkout_url must be non-blank and <= 2048 chars")
    parsed = urlsplit(normalized)
    try:
        _ = parsed.port
    except ValueError as exc:
        raise FiscalValidationError("checkout_url contains an invalid port") from exc
    if (
        parsed.scheme.casefold() != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise FiscalValidationError(
            "checkout_url must be an absolute HTTPS URL without credentials"
        )
    return normalized


@dataclass(frozen=True, slots=True)
class CommercialCheckoutItem:
    plan_id: str
    price_id: str
    provider: str
    checkout_url: str

    def __post_init__(self) -> None:
        plan_id = self.plan_id.strip()
        price_id = self.price_id.strip()
        if not plan_id or len(plan_id) > 128:
            raise FiscalValidationError("checkout plan_id must be non-blank and <= 128 chars")
        if not price_id or len(price_id) > 128:
            raise FiscalValidationError("checkout price_id must be non-blank and <= 128 chars")
        object.__setattr__(self, "plan_id", plan_id)
        object.__setattr__(self, "price_id", price_id)
        object.__setattr__(self, "provider", normalize_checkout_provider_id(self.provider))
        object.__setattr__(self, "checkout_url", validate_checkout_url(self.checkout_url))

    def to_mapping(self, *, expose_url: bool) -> dict[str, object]:
        return {
            "plan_id": self.plan_id,
            "price_id": self.price_id,
            "provider": self.provider,
            "checkout_url": self.checkout_url if expose_url else None,
        }


@dataclass(frozen=True, slots=True)
class CommercialCheckoutProjection:
    status: CommercialCheckoutStatus
    provider: str | None
    expected_count: int
    configured_count: int
    items: tuple[CommercialCheckoutItem, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.status, CommercialCheckoutStatus):
            raise FiscalValidationError("checkout status is invalid")
        if self.expected_count < 0 or self.configured_count < 0:
            raise FiscalValidationError("checkout projection counts cannot be negative")
        if self.configured_count > self.expected_count:
            raise FiscalValidationError(
                "configured checkout count cannot exceed expected count"
            )
        if self.configured_count != len(self.items):
            raise FiscalValidationError(
                "configured checkout count must match projected items"
            )
        expected_status = (
            CommercialCheckoutStatus.UNCONFIGURED
            if self.expected_count == 0 or self.configured_count == 0
            else (
                CommercialCheckoutStatus.CONFIGURED
                if self.configured_count == self.expected_count
                else CommercialCheckoutStatus.PARTIAL
            )
        )
        if self.status is not expected_status:
            raise FiscalValidationError(
                "checkout status is inconsistent with projection counts"
            )

        provider = (
            None if self.provider is None else normalize_checkout_provider_id(self.provider)
        )
        if self.status is CommercialCheckoutStatus.UNCONFIGURED and not self.items:
            object.__setattr__(self, "provider", provider)
            return
        if provider is None:
            raise FiscalValidationError("configured checkout projection requires provider")
        if any(item.provider != provider for item in self.items):
            raise FiscalValidationError(
                "checkout projection items must belong to the selected provider"
            )
        object.__setattr__(self, "provider", provider)

    def to_public_mapping(
        self,
        *,
        processing_configured: bool,
        expose_urls: bool,
    ) -> dict[str, object]:
        return {
            "status": self.status.value,
            "provider": self.provider,
            "processing_status": (
                "configured" if processing_configured else "unconfigured"
            ),
            "items": [
                item.to_mapping(expose_url=expose_urls)
                for item in self.items
            ],
        }


def unconfigured_checkout_projection(
    provider: str | None = None,
) -> CommercialCheckoutProjection:
    return CommercialCheckoutProjection(
        status=CommercialCheckoutStatus.UNCONFIGURED,
        provider=provider,
        expected_count=0,
        configured_count=0,
        items=(),
    )


@runtime_checkable
class CommercialCheckoutStarter(Protocol):
    @property
    def provider_id(self) -> str:
        """Stable provider identifier for one checkout-start adapter."""

    def start_checkout(
        self,
        *,
        item: CommercialCheckoutItem,
        acquisition_reference: str,
    ) -> str:
        """Return the governed provider checkout URL for one NFCore acquisition."""


@runtime_checkable
class CommercialCheckoutProjector(Protocol):
    @property
    def provider_id(self) -> str:
        """Stable provider identifier for diagnostics and public projection."""

    def project(
        self,
        pricing: CommercialPricingConfiguration | None,
    ) -> CommercialCheckoutProjection:
        """Project checkout state for the canonical commercial pricing catalog."""


__all__ = [
    "CommercialCheckoutItem",
    "CommercialCheckoutProjection",
    "CommercialCheckoutProjector",
    "CommercialCheckoutStarter",
    "CommercialCheckoutStatus",
    "normalize_checkout_provider_id",
    "unconfigured_checkout_projection",
    "validate_checkout_url",
]
