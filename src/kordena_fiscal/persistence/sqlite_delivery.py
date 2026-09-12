"""SQLite adapters for delivery-attempt audit and explicit outbox ordering metadata."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import cast

from kordena_fiscal.contingency import FiscalOutboxEntry
from kordena_fiscal.domain import FiscalValidationError
from kordena_fiscal.events import (
    DeliveryAttemptStatus,
    DeliveryAuditError,
    FiscalDeliveryAttempt,
)

from ._sqlite_common import dt, host_key, integer, iso, optional_text, scope_from_values, text


def _required(value: str, field_name: str, max_length: int) -> str:
    normalized = value.strip()
    if not normalized:
        raise FiscalValidationError(f"{field_name} must not be blank")
    if len(normalized) > max_length:
        raise FiscalValidationError(f"{field_name} exceeds max length {max_length}")
    return normalized


class SqliteFiscalOutboxOrderingStore:
    """Persist an optional explicit ordering key independently of outbox identity."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def register(self, entry_id: str, ordering_key: str) -> str:
        entry = _required(entry_id, "entry_id", 64).lower()
        key = _required(ordering_key, "ordering_key", 256)
        row = self._connection.execute(
            "SELECT ordering_key FROM fm_fiscal_outbox_ordering WHERE entry_id = ?",
            (entry,),
        ).fetchone()
        if row is not None:
            existing = text(row[0], "ordering_key")
            if existing != key:
                raise DeliveryAuditError(
                    "outbox ordering identity cannot be rebound to another ordering key"
                )
            return existing
        self._connection.execute(
            "INSERT INTO fm_fiscal_outbox_ordering (entry_id, ordering_key) VALUES (?, ?)",
            (entry, key),
        )
        return key

    def get(self, entry_id: str) -> str | None:
        entry = _required(entry_id, "entry_id", 64).lower()
        row = self._connection.execute(
            "SELECT ordering_key FROM fm_fiscal_outbox_ordering WHERE entry_id = ?",
            (entry,),
        ).fetchone()
        return None if row is None else text(row[0], "ordering_key")


class SqliteFiscalDeliveryAuditStore:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    @staticmethod
    def _record(row: tuple[object, ...]) -> FiscalDeliveryAttempt:
        finished = optional_text(row[11], "finished_at")
        next_available = optional_text(row[12], "next_available_at")
        return FiscalDeliveryAttempt(
            entry_id=text(row[0], "entry_id"),
            attempt_count=integer(row[1], "attempt_count"),
            scope=scope_from_values(row[2], row[3], row[4], row[5], row[6]),
            operation=text(row[7], "operation"),
            ordering_key=optional_text(row[8], "ordering_key"),
            status=DeliveryAttemptStatus(text(row[9], "status")),
            started_at=dt(text(row[10], "started_at")),
            finished_at=None if finished is None else dt(finished),
            next_available_at=None if next_available is None else dt(next_available),
            outcome_reference=optional_text(row[13], "outcome_reference"),
            last_error=optional_text(row[14], "last_error"),
        )

    def start(self, entry: FiscalOutboxEntry, *, started_at: datetime) -> FiscalDeliveryAttempt:
        if not isinstance(entry, FiscalOutboxEntry):
            raise FiscalValidationError("entry must be FiscalOutboxEntry")
        iso(started_at)
        ordering_key = self._ordering_key(entry.entry_id)
        record = FiscalDeliveryAttempt(
            entry_id=entry.entry_id,
            attempt_count=entry.attempt_count,
            scope=entry.scope,
            operation=entry.operation,
            ordering_key=ordering_key,
            status=DeliveryAttemptStatus.CLAIMED,
            started_at=started_at,
        )
        try:
            self._connection.execute(
                """
                INSERT INTO fm_fiscal_delivery_attempts (
                    entry_id, attempt_count, host_namespace, tenant_id, unit_id,
                    environment, correlation_id, operation, ordering_key, status,
                    started_at, finished_at, next_available_at, outcome_reference, last_error
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL, NULL)
                """,
                (
                    record.entry_id,
                    record.attempt_count,
                    host_key(record.scope.host_namespace),
                    record.scope.tenant_id,
                    record.scope.unit_id,
                    record.scope.environment.value,
                    record.scope.correlation_id,
                    record.operation,
                    record.ordering_key,
                    record.status.value,
                    iso(record.started_at),
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise DeliveryAuditError("delivery attempt audit already exists") from exc
        return record

    def expire_prior_attempts(
        self,
        entry_id: str,
        *,
        before_attempt: int,
        expired_at: datetime,
    ) -> tuple[FiscalDeliveryAttempt, ...]:
        entry = _required(entry_id, "entry_id", 64).lower()
        if (
            not isinstance(before_attempt, int)
            or isinstance(before_attempt, bool)
            or before_attempt < 1
        ):
            raise FiscalValidationError("before_attempt must be a positive integer")
        expired = iso(expired_at)
        rows = self._connection.execute(
            """
            SELECT entry_id, attempt_count, host_namespace, tenant_id, unit_id, environment,
                   correlation_id, operation, ordering_key, status, started_at, finished_at,
                   next_available_at, outcome_reference, last_error
            FROM fm_fiscal_delivery_attempts
            WHERE entry_id = ? AND attempt_count < ? AND status = ?
            ORDER BY attempt_count
            """,
            (entry, before_attempt, DeliveryAttemptStatus.CLAIMED.value),
        ).fetchall()
        if not rows:
            return ()
        self._connection.execute(
            """
            UPDATE fm_fiscal_delivery_attempts
            SET status = ?, finished_at = ?, last_error = ?
            WHERE entry_id = ? AND attempt_count < ? AND status = ?
            """,
            (
                DeliveryAttemptStatus.LEASE_EXPIRED.value,
                expired,
                "delivery lease expired before completion",
                entry,
                before_attempt,
                DeliveryAttemptStatus.CLAIMED.value,
            ),
        )
        refreshed = self._connection.execute(
            """
            SELECT entry_id, attempt_count, host_namespace, tenant_id, unit_id, environment,
                   correlation_id, operation, ordering_key, status, started_at, finished_at,
                   next_available_at, outcome_reference, last_error
            FROM fm_fiscal_delivery_attempts
            WHERE entry_id = ? AND attempt_count < ? AND status = ?
            ORDER BY attempt_count
            """,
            (entry, before_attempt, DeliveryAttemptStatus.LEASE_EXPIRED.value),
        ).fetchall()
        return tuple(self._record(cast(tuple[object, ...], row)) for row in refreshed)

    def mark_succeeded(
        self,
        entry_id: str,
        *,
        attempt_count: int,
        finished_at: datetime,
        outcome_reference: str,
    ) -> FiscalDeliveryAttempt:
        return self._finish(
            entry_id,
            attempt_count=attempt_count,
            status=DeliveryAttemptStatus.SUCCEEDED,
            finished_at=finished_at,
            outcome_reference=_required(outcome_reference, "outcome_reference", 512),
        )

    def mark_retry_scheduled(
        self,
        entry_id: str,
        *,
        attempt_count: int,
        finished_at: datetime,
        next_available_at: datetime,
        error: str,
    ) -> FiscalDeliveryAttempt:
        iso(next_available_at)
        return self._finish(
            entry_id,
            attempt_count=attempt_count,
            status=DeliveryAttemptStatus.RETRY_SCHEDULED,
            finished_at=finished_at,
            next_available_at=next_available_at,
            error=_required(error, "error", 1024),
        )

    def mark_dead_letter(
        self,
        entry_id: str,
        *,
        attempt_count: int,
        finished_at: datetime,
        error: str,
    ) -> FiscalDeliveryAttempt:
        return self._finish(
            entry_id,
            attempt_count=attempt_count,
            status=DeliveryAttemptStatus.DEAD_LETTER,
            finished_at=finished_at,
            error=_required(error, "error", 1024),
        )

    def list_for_entry(self, entry_id: str) -> tuple[FiscalDeliveryAttempt, ...]:
        entry = _required(entry_id, "entry_id", 64).lower()
        rows = self._connection.execute(
            """
            SELECT entry_id, attempt_count, host_namespace, tenant_id, unit_id, environment,
                   correlation_id, operation, ordering_key, status, started_at, finished_at,
                   next_available_at, outcome_reference, last_error
            FROM fm_fiscal_delivery_attempts
            WHERE entry_id = ? ORDER BY attempt_count
            """,
            (entry,),
        ).fetchall()
        return tuple(self._record(cast(tuple[object, ...], row)) for row in rows)

    def _ordering_key(self, entry_id: str) -> str | None:
        row = self._connection.execute(
            "SELECT ordering_key FROM fm_fiscal_outbox_ordering WHERE entry_id = ?",
            (entry_id,),
        ).fetchone()
        return None if row is None else text(row[0], "ordering_key")

    def _finish(
        self,
        entry_id: str,
        *,
        attempt_count: int,
        status: DeliveryAttemptStatus,
        finished_at: datetime,
        next_available_at: datetime | None = None,
        outcome_reference: str | None = None,
        error: str | None = None,
    ) -> FiscalDeliveryAttempt:
        entry = _required(entry_id, "entry_id", 64).lower()
        finished = iso(finished_at)
        cursor = self._connection.execute(
            """
            UPDATE fm_fiscal_delivery_attempts
            SET status = ?, finished_at = ?, next_available_at = ?,
                outcome_reference = ?, last_error = ?
            WHERE entry_id = ? AND attempt_count = ? AND status = ?
            """,
            (
                status.value,
                finished,
                None if next_available_at is None else iso(next_available_at),
                outcome_reference,
                error,
                entry,
                attempt_count,
                DeliveryAttemptStatus.CLAIMED.value,
            ),
        )
        if cursor.rowcount != 1:
            raise DeliveryAuditError("delivery attempt is missing or no longer claimed")
        row = self._connection.execute(
            """
            SELECT entry_id, attempt_count, host_namespace, tenant_id, unit_id, environment,
                   correlation_id, operation, ordering_key, status, started_at, finished_at,
                   next_available_at, outcome_reference, last_error
            FROM fm_fiscal_delivery_attempts
            WHERE entry_id = ? AND attempt_count = ?
            """,
            (entry, attempt_count),
        ).fetchone()
        assert row is not None
        return self._record(cast(tuple[object, ...], row))
