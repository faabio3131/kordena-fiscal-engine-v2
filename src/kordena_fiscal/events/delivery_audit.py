"""Durable delivery-attempt audit contracts for V2-08 asynchronous execution."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from kordena_fiscal.contingency import FiscalOutboxEntry
from kordena_fiscal.domain import ExecutionScope, FiscalDomainError, FiscalValidationError


class DeliveryAuditError(FiscalDomainError):
    """Raised when delivery-attempt audit state violates its contract."""


class DeliveryAttemptStatus(StrEnum):
    CLAIMED = "claimed"
    SUCCEEDED = "succeeded"
    RETRY_SCHEDULED = "retry_scheduled"
    DEAD_LETTER = "dead_letter"
    LEASE_EXPIRED = "lease_expired"


def _aware(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise FiscalValidationError(f"{field_name} must be timezone-aware")
    return value


def _optional(value: str | None, field_name: str, max_length: int) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        raise FiscalValidationError(f"{field_name} must not be blank")
    if len(normalized) > max_length:
        raise FiscalValidationError(f"{field_name} exceeds max length {max_length}")
    return normalized


@dataclass(frozen=True, slots=True)
class FiscalDeliveryAttempt:
    entry_id: str
    attempt_count: int
    scope: ExecutionScope
    operation: str
    ordering_key: str | None
    status: DeliveryAttemptStatus
    started_at: datetime
    finished_at: datetime | None = None
    next_available_at: datetime | None = None
    outcome_reference: str | None = None
    last_error: str | None = None

    def __post_init__(self) -> None:
        normalized_id = self.entry_id.strip().lower()
        if len(normalized_id) != 64:
            raise FiscalValidationError("entry_id must be SHA-256 hex")
        try:
            int(normalized_id, 16)
        except ValueError as exc:
            raise FiscalValidationError("entry_id must be hexadecimal") from exc
        object.__setattr__(self, "entry_id", normalized_id)
        if (
            not isinstance(self.attempt_count, int)
            or isinstance(self.attempt_count, bool)
            or self.attempt_count < 1
        ):
            raise FiscalValidationError("attempt_count must be a positive integer")
        if not isinstance(self.scope, ExecutionScope):
            raise FiscalValidationError("scope must be ExecutionScope")
        operation = self.operation.strip().lower()
        if not operation or len(operation) > 128:
            raise FiscalValidationError("operation must contain 1..128 characters")
        object.__setattr__(self, "operation", operation)
        object.__setattr__(
            self,
            "ordering_key",
            _optional(self.ordering_key, "ordering_key", 256),
        )
        if not isinstance(self.status, DeliveryAttemptStatus):
            raise FiscalValidationError("status must be DeliveryAttemptStatus")
        _aware(self.started_at, "started_at")
        if self.finished_at is not None:
            _aware(self.finished_at, "finished_at")
        if self.next_available_at is not None:
            _aware(self.next_available_at, "next_available_at")
        object.__setattr__(
            self,
            "outcome_reference",
            _optional(self.outcome_reference, "outcome_reference", 512),
        )
        object.__setattr__(self, "last_error", _optional(self.last_error, "last_error", 1024))
        self._validate_shape()

    def _validate_shape(self) -> None:
        if self.status is DeliveryAttemptStatus.CLAIMED:
            if any(
                value is not None
                for value in (
                    self.finished_at,
                    self.next_available_at,
                    self.outcome_reference,
                    self.last_error,
                )
            ):
                raise FiscalValidationError("claimed delivery attempt cannot be terminal")
            return
        if self.finished_at is None:
            raise FiscalValidationError("terminal delivery audit state requires finished_at")
        if self.status is DeliveryAttemptStatus.SUCCEEDED:
            if self.outcome_reference is None or self.last_error is not None:
                raise FiscalValidationError("successful delivery audit requires reference only")
            if self.next_available_at is not None:
                raise FiscalValidationError("successful delivery audit cannot have retry time")
        elif self.status is DeliveryAttemptStatus.RETRY_SCHEDULED:
            if self.last_error is None or self.next_available_at is None:
                raise FiscalValidationError("retry audit requires error and next_available_at")
            if self.outcome_reference is not None:
                raise FiscalValidationError("retry audit cannot have outcome_reference")
        elif self.status in (
            DeliveryAttemptStatus.DEAD_LETTER,
            DeliveryAttemptStatus.LEASE_EXPIRED,
        ):
            if self.last_error is None or self.outcome_reference is not None:
                raise FiscalValidationError("failed delivery audit requires error only")
            if self.next_available_at is not None:
                raise FiscalValidationError("terminal failed audit cannot have retry time")


class FiscalDeliveryAuditStore(Protocol):
    def start(self, entry: FiscalOutboxEntry, *, started_at: datetime) -> FiscalDeliveryAttempt: ...

    def expire_prior_attempts(
        self,
        entry_id: str,
        *,
        before_attempt: int,
        expired_at: datetime,
    ) -> tuple[FiscalDeliveryAttempt, ...]: ...

    def mark_succeeded(
        self,
        entry_id: str,
        *,
        attempt_count: int,
        finished_at: datetime,
        outcome_reference: str,
    ) -> FiscalDeliveryAttempt: ...

    def mark_retry_scheduled(
        self,
        entry_id: str,
        *,
        attempt_count: int,
        finished_at: datetime,
        next_available_at: datetime,
        error: str,
    ) -> FiscalDeliveryAttempt: ...

    def mark_dead_letter(
        self,
        entry_id: str,
        *,
        attempt_count: int,
        finished_at: datetime,
        error: str,
    ) -> FiscalDeliveryAttempt: ...

    def list_for_entry(self, entry_id: str) -> tuple[FiscalDeliveryAttempt, ...]: ...
