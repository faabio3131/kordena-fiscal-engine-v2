"""Provider-neutral commercial fulfillment contracts for FM NFCORE.

External sales channels authenticate and normalize their own payloads before creating
ValidatedCommercialEvent values. These contracts deliberately contain no provider-specific
payload shape and no authority to create tenant, user, RBAC or fiscal-production state.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from types import TracebackType
from typing import Protocol, Self

from kordena_fiscal.product.billing import SubscriptionCheckpoint, SubscriptionStatus

_PROVIDER_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
_TOKEN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")


class CommercialFulfillmentError(ValueError):
    """A canonical commercial fulfillment invariant was violated."""


class CommercialEventType(StrEnum):
    SALE_CONFIRMED = "sale_confirmed"
    SUBSCRIPTION_ACTIVATED = "subscription_activated"
    SUBSCRIPTION_RENEWED = "subscription_renewed"
    SUBSCRIPTION_PAYMENT_LATE = "subscription_payment_late"
    SUBSCRIPTION_PAUSED = "subscription_paused"
    SUBSCRIPTION_RECOVERED = "subscription_recovered"
    SUBSCRIPTION_CANCELED = "subscription_canceled"
    REFUND_CONFIRMED = "refund_confirmed"
    CHARGEBACK_CONFIRMED = "chargeback_confirmed"


class CommercialPurchaseState(StrEnum):
    UNCLAIMED = "unclaimed"
    IDENTITY_REQUIRED = "identity_required"
    READY_TO_PROVISION = "ready_to_provision"
    PROVISIONED = "provisioned"
    ACTIVATION_PENDING = "activation_pending"
    ACTIVE = "active"
    MANUAL_REVIEW = "manual_review"
    CANCELED = "canceled"
    REFUNDED = "refunded"


def _aware(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise CommercialFulfillmentError(f"{field_name} must be timezone-aware")
    return value


def _provider(value: str) -> str:
    normalized = value.strip().lower()
    if not _PROVIDER_ID.fullmatch(normalized):
        raise CommercialFulfillmentError("provider_id is invalid")
    return normalized


def _token(value: str, field_name: str) -> str:
    normalized = value.strip().lower()
    if not _TOKEN.fullmatch(normalized):
        raise CommercialFulfillmentError(f"{field_name} is invalid")
    return normalized


def _external(value: str, field_name: str, *, max_length: int = 320) -> str:
    normalized = value.strip()
    if not normalized or len(normalized) > max_length:
        raise CommercialFulfillmentError(
            f"{field_name} must be non-blank and <= {max_length} chars"
        )
    return normalized


def _optional_external(value: str | None, field_name: str) -> str | None:
    if value is None:
        return None
    return _external(value, field_name)


def _optional_email(value: str | None) -> str | None:
    if value is None:
        return None
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


def _optional_legal_name(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized or len(normalized) > 256:
        raise CommercialFulfillmentError("legal_name must be non-blank and <= 256 chars")
    return normalized


def _sha256_hex(value: str, field_name: str) -> str:
    normalized = value.strip().lower()
    if len(normalized) != 64:
        raise CommercialFulfillmentError(f"{field_name} must be SHA-256 hex")
    try:
        int(normalized, 16)
    except ValueError as exc:
        raise CommercialFulfillmentError(f"{field_name} must be SHA-256 hex") from exc
    return normalized


def commercial_purchase_id(provider_id: str, external_order_id: str) -> str:
    """Return a deterministic internal ID without exposing the external order value."""

    provider = _provider(provider_id)
    order_id = _external(external_order_id, "external_order_id")
    digest = hashlib.sha256(f"{provider}|{order_id}".encode()).hexdigest()
    return f"commercial-purchase-{digest[:32]}"


@dataclass(frozen=True, slots=True)
class CommercialAcquisitionRecord:
    """Pre-payment first-party intent owned by NFCore, never by the browser/provider."""

    acquisition_id: str
    idempotency_sha256: str
    request_sha256: str
    provider_id: str
    plan_id: str
    price_id: str
    buyer_email: str
    legal_name: str
    created_at: datetime
    expires_at: datetime
    linked_purchase_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "acquisition_id",
            _token(self.acquisition_id, "acquisition_id"),
        )
        object.__setattr__(
            self,
            "idempotency_sha256",
            _sha256_hex(self.idempotency_sha256, "idempotency_sha256"),
        )
        object.__setattr__(
            self,
            "request_sha256",
            _sha256_hex(self.request_sha256, "request_sha256"),
        )
        object.__setattr__(self, "provider_id", _provider(self.provider_id))
        object.__setattr__(self, "plan_id", _token(self.plan_id, "plan_id"))
        object.__setattr__(self, "price_id", _token(self.price_id, "price_id"))
        buyer_email = _optional_email(self.buyer_email)
        if buyer_email is None:
            raise CommercialFulfillmentError("buyer_email is required")
        legal_name = _optional_legal_name(self.legal_name)
        if legal_name is None:
            raise CommercialFulfillmentError("legal_name is required")
        object.__setattr__(self, "buyer_email", buyer_email)
        object.__setattr__(self, "legal_name", legal_name)
        _aware(self.created_at, "created_at")
        _aware(self.expires_at, "expires_at")
        if self.expires_at <= self.created_at:
            raise CommercialFulfillmentError("acquisition expires_at must follow created_at")
        if self.linked_purchase_id is not None:
            object.__setattr__(
                self,
                "linked_purchase_id",
                _token(self.linked_purchase_id, "linked_purchase_id"),
            )

    def __repr__(self) -> str:
        return (
            "CommercialAcquisitionRecord("
            f"acquisition_id={self.acquisition_id!r}, "
            f"provider_id={self.provider_id!r}, plan_id={self.plan_id!r}, "
            f"price_id={self.price_id!r}, buyer_email=<redacted>, "
            "legal_name=<redacted>, "
            f"created_at={self.created_at!r}, expires_at={self.expires_at!r}, "
            f"linked_purchase_id={self.linked_purchase_id!r})"
        )


@dataclass(frozen=True, slots=True)
class ValidatedCommercialEvent:
    """Sanitized provider-neutral fact emitted only by an authenticated adapter."""

    provider_id: str
    event_id: str
    event_type: CommercialEventType
    external_order_id: str
    plan_id: str
    occurred_at: datetime
    price_id: str | None = None
    external_subscription_id: str | None = None
    external_customer_id: str | None = None
    buyer_email: str | None = None
    acquisition_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "provider_id", _provider(self.provider_id))
        object.__setattr__(self, "event_id", _external(self.event_id, "event_id"))
        if not isinstance(self.event_type, CommercialEventType):
            raise CommercialFulfillmentError("event_type must be CommercialEventType")
        object.__setattr__(
            self,
            "external_order_id",
            _external(self.external_order_id, "external_order_id"),
        )
        object.__setattr__(self, "plan_id", _token(self.plan_id, "plan_id"))
        if self.price_id is not None:
            object.__setattr__(self, "price_id", _token(self.price_id, "price_id"))
        object.__setattr__(
            self,
            "external_subscription_id",
            _optional_external(
                self.external_subscription_id,
                "external_subscription_id",
            ),
        )
        object.__setattr__(
            self,
            "external_customer_id",
            _optional_external(self.external_customer_id, "external_customer_id"),
        )
        object.__setattr__(self, "buyer_email", _optional_email(self.buyer_email))
        if self.acquisition_id is not None:
            object.__setattr__(
                self,
                "acquisition_id",
                _token(self.acquisition_id, "acquisition_id"),
            )
        _aware(self.occurred_at, "occurred_at")

    @property
    def purchase_id(self) -> str:
        return commercial_purchase_id(self.provider_id, self.external_order_id)


@dataclass(frozen=True, slots=True)
class CommercialEventReceipt:
    """Durable dedup receipt. Customer PII is intentionally absent."""

    provider_id: str
    event_id: str
    event_type: CommercialEventType
    external_order_id: str
    purchase_id: str
    occurred_at: datetime
    received_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "provider_id", _provider(self.provider_id))
        object.__setattr__(self, "event_id", _external(self.event_id, "event_id"))
        if not isinstance(self.event_type, CommercialEventType):
            raise CommercialFulfillmentError("event_type must be CommercialEventType")
        object.__setattr__(
            self,
            "external_order_id",
            _external(self.external_order_id, "external_order_id"),
        )
        object.__setattr__(self, "purchase_id", _token(self.purchase_id, "purchase_id"))
        _aware(self.occurred_at, "occurred_at")
        _aware(self.received_at, "received_at")


@dataclass(frozen=True, slots=True)
class CommercialPurchaseRecord:
    """Canonical NFCore purchase/claim state.

    Provider IDs remain scoped references. tenant_id is set only after NFCore resolves or
    creates canonical organization identity.
    """

    purchase_id: str
    provider_id: str
    external_order_id: str
    plan_id: str
    state: CommercialPurchaseState
    created_at: datetime
    updated_at: datetime
    last_event_at: datetime
    last_event_id: str
    price_id: str | None = None
    external_subscription_id: str | None = None
    external_customer_id: str | None = None
    buyer_email: str | None = None
    legal_name: str | None = None
    tenant_id: str | None = None
    account_id: str | None = None
    billing_status: SubscriptionStatus | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "purchase_id", _token(self.purchase_id, "purchase_id"))
        object.__setattr__(self, "provider_id", _provider(self.provider_id))
        object.__setattr__(
            self,
            "external_order_id",
            _external(self.external_order_id, "external_order_id"),
        )
        object.__setattr__(self, "plan_id", _token(self.plan_id, "plan_id"))
        if not isinstance(self.state, CommercialPurchaseState):
            raise CommercialFulfillmentError("state must be CommercialPurchaseState")
        if self.price_id is not None:
            object.__setattr__(self, "price_id", _token(self.price_id, "price_id"))
        object.__setattr__(
            self,
            "external_subscription_id",
            _optional_external(
                self.external_subscription_id,
                "external_subscription_id",
            ),
        )
        object.__setattr__(
            self,
            "external_customer_id",
            _optional_external(self.external_customer_id, "external_customer_id"),
        )
        object.__setattr__(self, "buyer_email", _optional_email(self.buyer_email))
        object.__setattr__(self, "legal_name", _optional_legal_name(self.legal_name))
        if self.tenant_id is not None:
            object.__setattr__(self, "tenant_id", _token(self.tenant_id, "tenant_id"))
        if self.account_id is not None:
            object.__setattr__(self, "account_id", _token(self.account_id, "account_id"))
        if self.billing_status is not None and not isinstance(
            self.billing_status,
            SubscriptionStatus,
        ):
            raise CommercialFulfillmentError(
                "billing_status must be SubscriptionStatus or null"
            )
        object.__setattr__(
            self,
            "last_event_id",
            _external(self.last_event_id, "last_event_id"),
        )
        _aware(self.created_at, "created_at")
        _aware(self.updated_at, "updated_at")
        _aware(self.last_event_at, "last_event_at")
        if self.updated_at < self.created_at:
            raise CommercialFulfillmentError("updated_at cannot precede created_at")


@dataclass(frozen=True, slots=True)
class CommercialClaimRecord:
    """Hashed one-time claim grant for one canonical commercial purchase."""

    claim_id: str
    purchase_id: str
    token_sha256: str
    created_at: datetime
    expires_at: datetime
    used_at: datetime | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "claim_id", _token(self.claim_id, "claim_id"))
        object.__setattr__(self, "purchase_id", _token(self.purchase_id, "purchase_id"))
        object.__setattr__(
            self,
            "token_sha256",
            _sha256_hex(self.token_sha256, "token_sha256"),
        )
        _aware(self.created_at, "created_at")
        _aware(self.expires_at, "expires_at")
        if self.expires_at <= self.created_at:
            raise CommercialFulfillmentError("claim expires_at must be after created_at")
        if self.used_at is not None:
            _aware(self.used_at, "used_at")
            if self.used_at < self.created_at:
                raise CommercialFulfillmentError("claim used_at cannot precede created_at")


@dataclass(frozen=True, slots=True)
class DurableCommercialSubscription:
    subscription_id: str
    purchase_id: str
    checkpoint: SubscriptionCheckpoint
    provider_id: str
    external_subscription_id: str | None
    last_event_id: str
    last_event_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "subscription_id",
            _token(self.subscription_id, "subscription_id"),
        )
        object.__setattr__(self, "purchase_id", _token(self.purchase_id, "purchase_id"))
        if not isinstance(self.checkpoint, SubscriptionCheckpoint):
            raise CommercialFulfillmentError("checkpoint must be SubscriptionCheckpoint")
        object.__setattr__(self, "provider_id", _provider(self.provider_id))
        object.__setattr__(
            self,
            "external_subscription_id",
            _optional_external(
                self.external_subscription_id,
                "external_subscription_id",
            ),
        )
        object.__setattr__(
            self,
            "last_event_id",
            _external(self.last_event_id, "last_event_id"),
        )
        _aware(self.last_event_at, "last_event_at")


class CanonicalCommercialStore(Protocol):
    def get_acquisition(
        self,
        acquisition_id: str,
    ) -> CommercialAcquisitionRecord | None: ...

    def get_acquisition_by_idempotency(
        self,
        idempotency_sha256: str,
    ) -> CommercialAcquisitionRecord | None: ...

    def put_acquisition(
        self,
        acquisition: CommercialAcquisitionRecord,
    ) -> CommercialAcquisitionRecord: ...

    def receive_event(
        self,
        receipt: CommercialEventReceipt,
    ) -> tuple[CommercialEventReceipt, bool]: ...

    def get_event(
        self,
        provider_id: str,
        event_id: str,
    ) -> CommercialEventReceipt | None: ...

    def get_purchase(self, purchase_id: str) -> CommercialPurchaseRecord | None: ...

    def get_trial_for_email(self, email: str) -> CommercialPurchaseRecord | None: ...

    def get_purchase_by_external_order(
        self,
        provider_id: str,
        external_order_id: str,
    ) -> CommercialPurchaseRecord | None: ...

    def get_purchase_by_account(
        self,
        account_id: str,
    ) -> CommercialPurchaseRecord | None: ...

    def get_purchase_by_external_subscription(
        self,
        provider_id: str,
        external_subscription_id: str,
    ) -> CommercialPurchaseRecord | None: ...

    def put_purchase(self, purchase: CommercialPurchaseRecord) -> CommercialPurchaseRecord: ...

    def get_claim_by_digest(self, token_sha256: str) -> CommercialClaimRecord | None: ...

    def get_claim_for_purchase(self, purchase_id: str) -> CommercialClaimRecord | None: ...

    def put_claim(self, claim: CommercialClaimRecord) -> CommercialClaimRecord: ...

    def consume_claim(self, claim_id: str, used_at: datetime) -> bool: ...

    def get_subscription(
        self,
        subscription_id: str,
    ) -> DurableCommercialSubscription | None: ...

    def get_subscription_by_external_reference(
        self,
        provider_id: str,
        external_subscription_id: str,
    ) -> DurableCommercialSubscription | None: ...

    def get_subscription_for_tenant(
        self,
        tenant_id: str,
    ) -> DurableCommercialSubscription | None: ...

    def get_subscription_for_purchase(
        self,
        purchase_id: str,
    ) -> DurableCommercialSubscription | None: ...

    def put_subscription(
        self,
        subscription: DurableCommercialSubscription,
    ) -> DurableCommercialSubscription: ...


class CanonicalCommercialUnitOfWork(Protocol):
    @property
    def commercial(self) -> CanonicalCommercialStore: ...

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    def commit(self) -> None: ...


class CanonicalCommercialUnitOfWorkFactory(Protocol):
    def __call__(self) -> CanonicalCommercialUnitOfWork: ...


__all__ = [
    "CanonicalCommercialStore",
    "CommercialAcquisitionRecord",
    "CanonicalCommercialUnitOfWork",
    "CanonicalCommercialUnitOfWorkFactory",
    "CommercialClaimRecord",
    "CommercialEventReceipt",
    "CommercialEventType",
    "CommercialFulfillmentError",
    "CommercialPurchaseRecord",
    "CommercialPurchaseState",
    "DurableCommercialSubscription",
    "ValidatedCommercialEvent",
    "commercial_purchase_id",
]
