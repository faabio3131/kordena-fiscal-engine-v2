"""Provider-neutral first-party commercial acquisition for FM NFCORE."""

from __future__ import annotations

import hashlib
import json
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol

from kordena_fiscal.product.checkout import (
    CommercialCheckoutItem,
    CommercialCheckoutProjector,
    CommercialCheckoutStarter,
    validate_checkout_url,
)
from kordena_fiscal.product.commercial_fulfillment import (
    CanonicalCommercialUnitOfWorkFactory,
    CommercialAcquisitionRecord,
    CommercialFulfillmentError,
)
from kordena_fiscal.product.commercial_readiness import (
    CommercialDeliveryPathReadiness,
    commercial_purchase_ready,
)
from kordena_fiscal.product.commercial_release import CommercialReleaseDecision
from kordena_fiscal.product.pricing import CommercialPricingConfiguration


class CommercialPricingCurrentReader(Protocol):
    @property
    def current(self) -> CommercialPricingConfiguration | None: ...


class CommercialReleaseCurrentReader(Protocol):
    @property
    def current(self) -> CommercialReleaseDecision | None: ...


@dataclass(frozen=True, slots=True)
class CommercialAcquisitionStart:
    acquisition_reference: str
    provider_id: str
    checkout_url: str
    expires_at: datetime
    replay: bool


class CommercialAcquisitionService:
    """Create one NFCore-owned pre-payment reference before provider redirect."""

    def __init__(
        self,
        *,
        unit_of_work_factory: CanonicalCommercialUnitOfWorkFactory,
        pricing: CommercialPricingCurrentReader,
        release: CommercialReleaseCurrentReader,
        checkout: CommercialCheckoutProjector,
        checkout_starter: CommercialCheckoutStarter,
        checkout_processing_configured: bool,
        delivery_readiness: CommercialDeliveryPathReadiness,
        ttl: timedelta = timedelta(minutes=30),
    ) -> None:
        if ttl < timedelta(minutes=5) or ttl > timedelta(hours=24):
            raise ValueError("acquisition ttl must be between 5 minutes and 24 hours")
        if checkout.provider_id != checkout_starter.provider_id:
            raise ValueError("checkout projector and starter providers must match")
        self._unit_of_work_factory = unit_of_work_factory
        self._pricing = pricing
        self._release = release
        self._checkout = checkout
        self._checkout_starter = checkout_starter
        self._checkout_processing_configured = checkout_processing_configured
        self._delivery_readiness = delivery_readiness
        self._ttl = ttl

    def begin(
        self,
        *,
        plan_id: str,
        price_id: str,
        buyer_email: str,
        legal_name: str,
        idempotency_key: str,
        now: datetime,
    ) -> CommercialAcquisitionStart:
        self._aware(now)
        normalized_plan = self._token(plan_id, "plan_id")
        normalized_price = self._token(price_id, "price_id")
        normalized_email = self._email(buyer_email)
        normalized_name = self._legal_name(legal_name)
        idempotency_digest = self._idempotency_digest(idempotency_key)

        pricing = self._pricing.current
        release = self._release.current
        projection = self._checkout.project(pricing)
        if not commercial_purchase_ready(
            release=release,
            pricing=pricing,
            checkout=projection,
            checkout_processing_configured=self._checkout_processing_configured,
            delivery=self._delivery_readiness,
        ):
            raise CommercialFulfillmentError(
                "commercial purchase path is not operationally ready"
            )

        item = self._selected_item(
            projection.items,
            plan_id=normalized_plan,
            price_id=normalized_price,
        )
        if item.provider != self._checkout_starter.provider_id:
            raise CommercialFulfillmentError("checkout provider identity mismatch")

        request_digest = self._request_digest(
            provider_id=item.provider,
            plan_id=normalized_plan,
            price_id=normalized_price,
            buyer_email=normalized_email,
            legal_name=normalized_name,
        )

        replay = False
        with self._unit_of_work_factory() as uow:
            existing = uow.commercial.get_acquisition_by_idempotency(
                idempotency_digest
            )
            if existing is not None:
                if existing.request_sha256 != request_digest:
                    raise CommercialFulfillmentError(
                        "idempotency key was reused with different acquisition data"
                    )
                if now >= existing.expires_at:
                    raise CommercialFulfillmentError(
                        "commercial acquisition reference has expired"
                    )
                acquisition = existing
                replay = True
            else:
                acquisition = CommercialAcquisitionRecord(
                    acquisition_id=f"acq-{secrets.token_hex(16)}",
                    idempotency_sha256=idempotency_digest,
                    request_sha256=request_digest,
                    provider_id=item.provider,
                    plan_id=normalized_plan,
                    price_id=normalized_price,
                    buyer_email=normalized_email,
                    legal_name=normalized_name,
                    created_at=now,
                    expires_at=now + self._ttl,
                )
                uow.commercial.put_acquisition(acquisition)
                uow.commit()

        checkout_url = validate_checkout_url(
            self._checkout_starter.start_checkout(
                item=item,
                acquisition_reference=acquisition.acquisition_id,
            )
        )
        return CommercialAcquisitionStart(
            acquisition_reference=acquisition.acquisition_id,
            provider_id=acquisition.provider_id,
            checkout_url=checkout_url,
            expires_at=acquisition.expires_at,
            replay=replay,
        )

    @staticmethod
    def _selected_item(
        items: tuple[CommercialCheckoutItem, ...],
        *,
        plan_id: str,
        price_id: str,
    ) -> CommercialCheckoutItem:
        matched = tuple(
            item
            for item in items
            if item.plan_id == plan_id and item.price_id == price_id
        )
        if len(matched) != 1:
            raise CommercialFulfillmentError(
                "selected commercial plan/price is not available for checkout"
            )
        return matched[0]

    @staticmethod
    def _aware(now: datetime) -> None:
        if now.tzinfo is None or now.utcoffset() is None:
            raise CommercialFulfillmentError("now must be timezone-aware")

    @staticmethod
    def _token(value: str, field_name: str) -> str:
        normalized = value.strip().lower()
        if not normalized or len(normalized) > 128:
            raise CommercialFulfillmentError(
                f"{field_name} must be non-blank and <= 128 chars"
            )
        return normalized

    @staticmethod
    def _email(value: str) -> str:
        normalized = value.strip().casefold()
        if (
            not normalized
            or len(normalized) > 320
            or normalized.count("@") != 1
            or normalized.startswith("@")
            or normalized.endswith("@")
        ):
            raise CommercialFulfillmentError("buyer_email is invalid")
        return normalized

    @staticmethod
    def _legal_name(value: str) -> str:
        normalized = value.strip()
        if not normalized or len(normalized) > 256:
            raise CommercialFulfillmentError(
                "legal_name must be non-blank and <= 256 chars"
            )
        return normalized

    @staticmethod
    def _idempotency_digest(value: str) -> str:
        normalized = value.strip()
        if len(normalized) < 16 or len(normalized) > 256:
            raise CommercialFulfillmentError(
                "idempotency key must contain between 16 and 256 characters"
            )
        return hashlib.sha256(normalized.encode()).hexdigest()

    @staticmethod
    def _request_digest(
        *,
        provider_id: str,
        plan_id: str,
        price_id: str,
        buyer_email: str,
        legal_name: str,
    ) -> str:
        payload = json.dumps(
            {
                "provider_id": provider_id,
                "plan_id": plan_id,
                "price_id": price_id,
                "buyer_email": buyer_email,
                "legal_name": legal_name,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode()).hexdigest()


__all__ = [
    "CommercialAcquisitionService",
    "CommercialAcquisitionStart",
    "CommercialPricingCurrentReader",
    "CommercialReleaseCurrentReader",
]
