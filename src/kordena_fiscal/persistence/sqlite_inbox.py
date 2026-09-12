"""SQLite adapter for the V2-08 durable inbox contract."""

from __future__ import annotations

import sqlite3
from dataclasses import replace

from kordena_fiscal.domain import FiscalValidationError
from kordena_fiscal.events import (
    FiscalInboxEntry,
    FiscalInboxReceiveResult,
    FiscalInboxStatus,
    InboxConflictError,
    InboxStateError,
)

from ._sqlite_common import (
    blob,
    dt,
    host_key,
    integer,
    iso,
    one_row,
    optional_text,
    scope_from_values,
    text,
    validate_sha256,
)


class SqliteFiscalInboxStore:
    """Durable inbox with semantic deduplication and optimistic state versions."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    @staticmethod
    def _entry(row: tuple[object, ...]) -> FiscalInboxEntry:
        processed_at = optional_text(row[17], "processed_at")
        return FiscalInboxEntry(
            entry_id=text(row[0], "entry_id"),
            scope=scope_from_values(row[1], row[2], row[3], row[4], row[5]),
            producer=text(row[6], "producer"),
            event_id=text(row[7], "event_id"),
            event_type=text(row[8], "event_type"),
            payload=blob(row[9], "payload"),
            payload_sha256=text(row[10], "payload_sha256"),
            occurred_at=dt(text(row[11], "occurred_at")),
            received_at=dt(text(row[12], "received_at")),
            causation_id=optional_text(row[13], "causation_id"),
            idempotency_key=optional_text(row[14], "idempotency_key"),
            status=FiscalInboxStatus(text(row[15], "status")),
            version=integer(row[16], "version"),
            processed_at=None if processed_at is None else dt(processed_at),
            outcome_reference=optional_text(row[18], "outcome_reference"),
            last_error=optional_text(row[19], "last_error"),
        )

    @staticmethod
    def _values(entry: FiscalInboxEntry) -> tuple[object, ...]:
        return (
            entry.entry_id,
            host_key(entry.scope.host_namespace),
            entry.scope.tenant_id,
            entry.scope.unit_id,
            entry.scope.environment.value,
            entry.scope.correlation_id,
            entry.producer,
            entry.event_id,
            entry.event_type,
            entry.payload,
            entry.payload_sha256,
            iso(entry.occurred_at),
            iso(entry.received_at),
            entry.causation_id,
            entry.idempotency_key,
            entry.status.value,
            entry.version,
            None if entry.processed_at is None else iso(entry.processed_at),
            entry.outcome_reference,
            entry.last_error,
        )

    def receive(self, entry: FiscalInboxEntry) -> FiscalInboxReceiveResult:
        if not isinstance(entry, FiscalInboxEntry):
            raise FiscalValidationError("entry must be FiscalInboxEntry")
        existing = self.get(entry.entry_id)
        if existing is not None:
            if not existing.same_event_content(entry):
                raise InboxConflictError(
                    "inbox semantic event identity was reused with different content"
                )
            return FiscalInboxReceiveResult(entry=existing, replay=True)
        try:
            self._connection.execute(
                """
                INSERT INTO fm_fiscal_inbox (
                    entry_id, host_namespace, tenant_id, unit_id, environment,
                    correlation_id, producer, event_id, event_type, payload,
                    payload_sha256, occurred_at, received_at, causation_id,
                    idempotency_key, status, version, processed_at,
                    outcome_reference, last_error
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                self._values(entry),
            )
        except sqlite3.IntegrityError as exc:
            raise InboxConflictError(
                "inbox semantic event identity already exists"
            ) from exc
        return FiscalInboxReceiveResult(entry=entry, replay=False)

    def get(self, entry_id: str) -> FiscalInboxEntry | None:
        normalized = validate_sha256(entry_id, "entry_id")
        row = one_row(
            self._connection.execute(
                """
                SELECT entry_id, host_namespace, tenant_id, unit_id, environment,
                       correlation_id, producer, event_id, event_type, payload,
                       payload_sha256, occurred_at, received_at, causation_id,
                       idempotency_key, status, version, processed_at,
                       outcome_reference, last_error
                FROM fm_fiscal_inbox
                WHERE entry_id = ?
                """,
                (normalized,),
            )
        )
        return None if row is None else self._entry(row)

    def begin_processing(
        self,
        entry_id: str,
        *,
        expected_version: int,
    ) -> FiscalInboxEntry:
        current = self._expect(entry_id, expected_version, FiscalInboxStatus.RECEIVED)
        updated = replace(
            current,
            status=FiscalInboxStatus.PROCESSING,
            version=current.version + 1,
        )
        self._save(updated, expected_version=expected_version)
        return updated

    def mark_processed(
        self,
        entry_id: str,
        *,
        expected_version: int,
        processed_at,
        outcome_reference: str | None = None,
    ) -> FiscalInboxEntry:
        current = self._expect(entry_id, expected_version, FiscalInboxStatus.PROCESSING)
        updated = replace(
            current,
            status=FiscalInboxStatus.PROCESSED,
            version=current.version + 1,
            processed_at=processed_at,
            outcome_reference=outcome_reference,
            last_error=None,
        )
        self._save(updated, expected_version=expected_version)
        return updated

    def mark_rejected(
        self,
        entry_id: str,
        *,
        expected_version: int,
        processed_at,
        error: str,
    ) -> FiscalInboxEntry:
        current = self._expect(entry_id, expected_version, FiscalInboxStatus.PROCESSING)
        updated = replace(
            current,
            status=FiscalInboxStatus.REJECTED,
            version=current.version + 1,
            processed_at=processed_at,
            outcome_reference=None,
            last_error=error,
        )
        self._save(updated, expected_version=expected_version)
        return updated

    def _expect(
        self,
        entry_id: str,
        expected_version: int,
        expected_status: FiscalInboxStatus,
    ) -> FiscalInboxEntry:
        if not isinstance(expected_version, int) or isinstance(expected_version, bool):
            raise FiscalValidationError("expected_version must be an integer")
        if expected_version < 0:
            raise FiscalValidationError("expected_version must be >= 0")
        current = self.get(entry_id)
        if current is None:
            raise InboxStateError("inbox entry does not exist")
        if current.version != expected_version:
            raise InboxStateError("inbox version does not match expected_version")
        if current.status is not expected_status:
            raise InboxStateError(
                f"inbox entry must be {expected_status.value} for this transition"
            )
        return current

    def _save(self, entry: FiscalInboxEntry, *, expected_version: int) -> None:
        values = self._values(entry)
        cursor = self._connection.execute(
            """
            UPDATE fm_fiscal_inbox SET
                host_namespace = ?, tenant_id = ?, unit_id = ?, environment = ?,
                correlation_id = ?, producer = ?, event_id = ?, event_type = ?,
                payload = ?, payload_sha256 = ?, occurred_at = ?, received_at = ?,
                causation_id = ?, idempotency_key = ?, status = ?, version = ?,
                processed_at = ?, outcome_reference = ?, last_error = ?
            WHERE entry_id = ? AND version = ?
            """,
            (*values[1:], values[0], expected_version),
        )
        if cursor.rowcount != 1:
            raise InboxStateError("inbox optimistic version conflict")
