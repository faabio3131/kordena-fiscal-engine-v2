"""Durable inbox contract, state machine and deduplication semantics for V2-08."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from kordena_fiscal.domain import ExecutionScope, FiscalDomainError, FiscalValidationError


class FiscalInboxError(FiscalDomainError):
    """Base error for durable inbox invariants."""


class InboxConflictError(FiscalInboxError):
    """Raised when one semantic event identity is reused with different content."""


class InboxStateError(FiscalInboxError):
    """Raised when an inbox state transition violates status/version authority."""


class FiscalInboxStatus(StrEnum):
    RECEIVED = "received"
    PROCESSING = "processing"
    PROCESSED = "processed"
    REJECTED = "rejected"


def _required(value: str, field_name: str, max_length: int) -> str:
    normalized = value.strip()
    if not normalized:
        raise FiscalValidationError(f"{field_name} must not be blank")
    if len(normalized) > max_length:
        raise FiscalValidationError(f"{field_name} exceeds max length {max_length}")
    return normalized


def _optional(value: str | None, field_name: str, max_length: int) -> str | None:
    if value is None:
        return None
    return _required(value, field_name, max_length)


def _aware(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise FiscalValidationError(f"{field_name} must be timezone-aware")
    return value


def _sha256_hex(value: str, field_name: str) -> str:
    normalized = value.strip().lower()
    if len(normalized) != 64:
        raise FiscalValidationError(f"{field_name} must be SHA-256 hex")
    try:
        int(normalized, 16)
    except ValueError as exc:
        raise FiscalValidationError(f"{field_name} must be hexadecimal") from exc
    return normalized


def build_inbox_entry_id(
    *,
    scope: ExecutionScope,
    producer: str,
    event_id: str,
) -> str:
    """Build deterministic identity from partition + producer + upstream event id."""

    if not isinstance(scope, ExecutionScope):
        raise FiscalValidationError("scope must be ExecutionScope")
    producer = _required(producer, "producer", 128).lower()
    event_id = _required(event_id, "event_id", 256)
    material = "|".join((*scope.identity_material, producer, event_id))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class FiscalInboxEntry:
    """Immutable inbound event payload plus governed processing state."""

    entry_id: str
    scope: ExecutionScope
    producer: str
    event_id: str
    event_type: str
    payload: bytes
    payload_sha256: str
    occurred_at: datetime
    received_at: datetime
    causation_id: str | None = None
    idempotency_key: str | None = None
    status: FiscalInboxStatus = FiscalInboxStatus.RECEIVED
    version: int = 0
    processed_at: datetime | None = None
    outcome_reference: str | None = None
    last_error: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "entry_id", _sha256_hex(self.entry_id, "entry_id"))
        if not isinstance(self.scope, ExecutionScope):
            raise FiscalValidationError("scope must be ExecutionScope")
        object.__setattr__(self, "producer", _required(self.producer, "producer", 128).lower())
        object.__setattr__(self, "event_id", _required(self.event_id, "event_id", 256))
        object.__setattr__(
            self,
            "event_type",
            _required(self.event_type, "event_type", 128).lower(),
        )
        if not isinstance(self.payload, bytes) or not self.payload:
            raise FiscalValidationError("payload must be non-empty bytes")
        digest = _sha256_hex(self.payload_sha256, "payload_sha256")
        if digest != hashlib.sha256(self.payload).hexdigest():
            raise FiscalValidationError("payload_sha256 does not match payload")
        object.__setattr__(self, "payload_sha256", digest)
        _aware(self.occurred_at, "occurred_at")
        _aware(self.received_at, "received_at")
        object.__setattr__(
            self,
            "causation_id",
            _optional(self.causation_id, "causation_id", 256),
        )
        object.__setattr__(
            self,
            "idempotency_key",
            _optional(self.idempotency_key, "idempotency_key", 256),
        )
        if not isinstance(self.status, FiscalInboxStatus):
            raise FiscalValidationError("status must be FiscalInboxStatus")
        if not isinstance(self.version, int) or isinstance(self.version, bool) or self.version < 0:
            raise FiscalValidationError("version must be an integer >= 0")
        if self.processed_at is not None:
            _aware(self.processed_at, "processed_at")
        object.__setattr__(
            self,
            "outcome_reference",
            _optional(self.outcome_reference, "outcome_reference", 512),
        )
        object.__setattr__(self, "last_error", _optional(self.last_error, "last_error", 1024))
        expected = build_inbox_entry_id(
            scope=self.scope,
            producer=self.producer,
            event_id=self.event_id,
        )
        if self.entry_id != expected:
            raise FiscalValidationError("entry_id does not match inbox semantic identity")
        self._validate_state_shape()

    def _validate_state_shape(self) -> None:
        if self.status in (FiscalInboxStatus.RECEIVED, FiscalInboxStatus.PROCESSING):
            if self.processed_at is not None:
                raise FiscalValidationError("non-terminal inbox entry cannot have processed_at")
            if self.outcome_reference is not None or self.last_error is not None:
                raise FiscalValidationError("non-terminal inbox entry cannot have terminal result")
            return
        if self.processed_at is None:
            raise FiscalValidationError("terminal inbox entry requires processed_at")
        if self.status is FiscalInboxStatus.PROCESSED:
            if self.last_error is not None:
                raise FiscalValidationError("processed inbox entry cannot have last_error")
            return
        if self.status is FiscalInboxStatus.REJECTED:
            if self.last_error is None:
                raise FiscalValidationError("rejected inbox entry requires last_error")
            if self.outcome_reference is not None:
                raise FiscalValidationError("rejected inbox entry cannot have outcome_reference")

    @classmethod
    def build(
        cls,
        *,
        scope: ExecutionScope,
        producer: str,
        event_id: str,
        event_type: str,
        payload: bytes,
        occurred_at: datetime,
        received_at: datetime,
        causation_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> FiscalInboxEntry:
        if not isinstance(payload, bytes) or not payload:
            raise FiscalValidationError("payload must be non-empty bytes")
        return cls(
            entry_id=build_inbox_entry_id(scope=scope, producer=producer, event_id=event_id),
            scope=scope,
            producer=producer,
            event_id=event_id,
            event_type=event_type,
            payload=payload,
            payload_sha256=hashlib.sha256(payload).hexdigest(),
            occurred_at=occurred_at,
            received_at=received_at,
            causation_id=causation_id,
            idempotency_key=idempotency_key,
        )

    def same_event_content(self, other: FiscalInboxEntry) -> bool:
        """Compare immutable upstream semantics; duplicate receive time is irrelevant."""

        return (
            self.entry_id == other.entry_id
            and self.scope.identity_partition_key == other.scope.identity_partition_key
            and self.scope.correlation_id == other.scope.correlation_id
            and self.producer == other.producer
            and self.event_id == other.event_id
            and self.event_type == other.event_type
            and self.payload == other.payload
            and self.payload_sha256 == other.payload_sha256
            and self.occurred_at == other.occurred_at
            and self.causation_id == other.causation_id
            and self.idempotency_key == other.idempotency_key
        )


@dataclass(frozen=True, slots=True)
class FiscalInboxReceiveResult:
    entry: FiscalInboxEntry
    replay: bool


class FiscalInboxStore(Protocol):
    def receive(self, entry: FiscalInboxEntry) -> FiscalInboxReceiveResult: ...

    def get(self, entry_id: str) -> FiscalInboxEntry | None: ...

    def begin_processing(
        self,
        entry_id: str,
        *,
        expected_version: int,
    ) -> FiscalInboxEntry: ...

    def mark_processed(
        self,
        entry_id: str,
        *,
        expected_version: int,
        processed_at: datetime,
        outcome_reference: str | None = None,
    ) -> FiscalInboxEntry: ...

    def mark_rejected(
        self,
        entry_id: str,
        *,
        expected_version: int,
        processed_at: datetime,
        error: str,
    ) -> FiscalInboxEntry: ...


class FiscalInboxService:
    """Construct durable inbox identities before persistence."""

    def __init__(self, store: FiscalInboxStore) -> None:
        self._store = store

    def receive(
        self,
        *,
        scope: ExecutionScope,
        producer: str,
        event_id: str,
        event_type: str,
        payload: bytes,
        occurred_at: datetime,
        received_at: datetime,
        causation_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> FiscalInboxReceiveResult:
        entry = FiscalInboxEntry.build(
            scope=scope,
            producer=producer,
            event_id=event_id,
            event_type=event_type,
            payload=payload,
            occurred_at=occurred_at,
            received_at=received_at,
            causation_id=causation_id,
            idempotency_key=idempotency_key,
        )
        return self._store.receive(entry)
