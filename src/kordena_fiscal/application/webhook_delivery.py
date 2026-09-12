"""Signed webhook delivery adapter for the durable V2-08 outbox worker."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from urllib.parse import urlsplit

from kordena_fiscal.contingency import (
    FiscalDispatchResult,
    FiscalDispatchStatus,
    FiscalOutboxEntry,
)
from kordena_fiscal.domain import FiscalValidationError
from kordena_fiscal.security import WebhookSecurity

FM_WEBHOOK_SIGNATURE_HEADER = "X-FM-Webhook-Signature"
FM_WEBHOOK_CORRELATION_HEADER = "X-FM-Correlation-ID"
FM_WEBHOOK_OUTBOX_ENTRY_HEADER = "X-FM-Outbox-Entry-ID"
FM_WEBHOOK_ATTEMPT_HEADER = "X-FM-Delivery-Attempt"


def _required(value: str, field_name: str, max_length: int) -> str:
    normalized = value.strip()
    if not normalized:
        raise FiscalValidationError(f"{field_name} must not be blank")
    if len(normalized) > max_length:
        raise FiscalValidationError(f"{field_name} exceeds max length {max_length}")
    return normalized


def _aware(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise FiscalValidationError(f"{field_name} must be timezone-aware")
    return value


@dataclass(frozen=True, slots=True)
class WebhookDestination:
    """Resolved host-neutral destination. Secrets never belong in this object."""

    destination_id: str
    url: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "destination_id",
            _required(self.destination_id, "destination_id", 256),
        )
        normalized_url = _required(self.url, "url", 2048)
        parsed = urlsplit(normalized_url)
        if parsed.scheme.lower() != "https" or not parsed.hostname:
            raise FiscalValidationError("webhook destination must use an absolute https URL")
        if parsed.username is not None or parsed.password is not None:
            raise FiscalValidationError("webhook destination URL cannot contain credentials")
        if parsed.fragment:
            raise FiscalValidationError("webhook destination URL cannot contain a fragment")
        object.__setattr__(self, "url", normalized_url)


@dataclass(frozen=True, slots=True)
class WebhookDeliveryRequest:
    """Transport-neutral HTTP-shaped webhook request."""

    destination: WebhookDestination
    body: bytes
    headers: tuple[tuple[str, str], ...]
    outbox_entry_id: str
    attempt_count: int

    def __post_init__(self) -> None:
        if not isinstance(self.destination, WebhookDestination):
            raise FiscalValidationError("destination must be WebhookDestination")
        if not isinstance(self.body, bytes) or not self.body:
            raise FiscalValidationError("body must be non-empty bytes")
        if not self.headers:
            raise FiscalValidationError("headers must not be empty")
        normalized_headers: list[tuple[str, str]] = []
        seen: set[str] = set()
        for name, value in self.headers:
            normalized_name = _required(name, "header name", 128)
            normalized_value = _required(value, "header value", 4096)
            canonical = normalized_name.lower()
            if canonical in seen:
                raise FiscalValidationError("webhook request contains duplicate headers")
            seen.add(canonical)
            normalized_headers.append((normalized_name, normalized_value))
        object.__setattr__(self, "headers", tuple(normalized_headers))
        object.__setattr__(
            self,
            "outbox_entry_id",
            _required(self.outbox_entry_id, "outbox_entry_id", 128),
        )
        if (
            not isinstance(self.attempt_count, int)
            or isinstance(self.attempt_count, bool)
            or self.attempt_count < 1
        ):
            raise FiscalValidationError("attempt_count must be a positive integer")

    def header(self, name: str) -> str | None:
        normalized = _required(name, "header name", 128).lower()
        for header_name, value in self.headers:
            if header_name.lower() == normalized:
                return value
        return None


@dataclass(frozen=True, slots=True)
class WebhookDeliveryResponse:
    """Minimal transport result; classification remains inside FM Fiscal."""

    status_code: int
    delivery_reference: str | None = None
    error_detail: str | None = None

    def __post_init__(self) -> None:
        if (
            not isinstance(self.status_code, int)
            or isinstance(self.status_code, bool)
            or not 100 <= self.status_code <= 599
        ):
            raise FiscalValidationError("status_code must be an integer from 100 to 599")
        if self.delivery_reference is not None:
            object.__setattr__(
                self,
                "delivery_reference",
                _required(self.delivery_reference, "delivery_reference", 512),
            )
        if self.error_detail is not None:
            object.__setattr__(
                self,
                "error_detail",
                _required(self.error_detail, "error_detail", 1024),
            )


class WebhookDestinationResolver(Protocol):
    def resolve(self, entry: FiscalOutboxEntry) -> WebhookDestination | None: ...


class WebhookTransport(Protocol):
    def deliver(self, request: WebhookDeliveryRequest) -> WebhookDeliveryResponse: ...


class WebhookDeliveryClock(Protocol):
    def now(self) -> datetime: ...


class SystemWebhookDeliveryClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


class SignedWebhookOutboxHandler:
    """Sign the exact durable payload and dispatch it through an injected transport.

    HMAC material, key-id rotation and replay bounds are delegated to the V2-05
    ``WebhookSecurity`` primitive. The handler owns only destination resolution,
    request construction and deterministic HTTP outcome classification.
    """

    def __init__(
        self,
        *,
        security: WebhookSecurity,
        destination_resolver: WebhookDestinationResolver,
        transport: WebhookTransport,
        clock: WebhookDeliveryClock | None = None,
    ) -> None:
        if not isinstance(security, WebhookSecurity):
            raise FiscalValidationError("security must be WebhookSecurity")
        self._security = security
        self._destination_resolver = destination_resolver
        self._transport = transport
        self._clock = clock or SystemWebhookDeliveryClock()

    def dispatch(self, entry: FiscalOutboxEntry) -> FiscalDispatchResult:
        if not isinstance(entry, FiscalOutboxEntry):
            raise FiscalValidationError("entry must be FiscalOutboxEntry")
        destination = self._destination_resolver.resolve(entry)
        if destination is None:
            return FiscalDispatchResult(
                FiscalDispatchStatus.FATAL_FAILURE,
                error="webhook destination is not configured",
            )
        if not isinstance(destination, WebhookDestination):
            raise FiscalValidationError(
                "webhook destination resolver must return WebhookDestination or None"
            )

        now = _aware(self._clock.now(), "webhook delivery clock")
        signature = self._security.sign(entry.payload, now=now)
        request = WebhookDeliveryRequest(
            destination=destination,
            body=entry.payload,
            headers=(
                ("Content-Type", "application/json"),
                (FM_WEBHOOK_SIGNATURE_HEADER, signature.header_value),
                (FM_WEBHOOK_CORRELATION_HEADER, entry.scope.correlation_id),
                (FM_WEBHOOK_OUTBOX_ENTRY_HEADER, entry.entry_id),
                (FM_WEBHOOK_ATTEMPT_HEADER, str(entry.attempt_count)),
            ),
            outbox_entry_id=entry.entry_id,
            attempt_count=entry.attempt_count,
        )
        response = self._transport.deliver(request)
        if not isinstance(response, WebhookDeliveryResponse):
            raise FiscalValidationError(
                "webhook transport must return WebhookDeliveryResponse"
            )
        return self._classify(entry, response)

    @staticmethod
    def _classify(
        entry: FiscalOutboxEntry,
        response: WebhookDeliveryResponse,
    ) -> FiscalDispatchResult:
        status = response.status_code
        if 200 <= status <= 299:
            reference = response.delivery_reference or (
                f"webhook:{entry.entry_id}:attempt:{entry.attempt_count}:http:{status}"
            )
            return FiscalDispatchResult(
                FiscalDispatchStatus.SUCCEEDED,
                reference=reference,
            )

        detail = response.error_detail or f"webhook endpoint returned HTTP {status}"
        error = f"HTTP {status}: {detail}"[:1024]
        if status in {408, 425, 429} or status >= 500 or status < 200:
            return FiscalDispatchResult(
                FiscalDispatchStatus.RETRYABLE_FAILURE,
                error=error,
            )
        return FiscalDispatchResult(
            FiscalDispatchStatus.FATAL_FAILURE,
            error=error,
        )
