"""SQLite adapters for durable fiscal outbox and immutable archive records."""

from __future__ import annotations

import sqlite3
from dataclasses import replace
from datetime import datetime, timedelta
from typing import cast

from kordena_fiscal.archive import (
    ArchiveConflictError,
    FiscalArchiveEntry,
    FiscalArchiveKind,
    RetentionPolicyMetadata,
)
from kordena_fiscal.contingency import (
    FiscalOutboxEnqueueResult,
    FiscalOutboxEntry,
    FiscalOutboxStatus,
    OutboxConflictError,
    OutboxStateError,
)
from kordena_fiscal.domain import ExecutionScope, FiscalValidationError

from ._sqlite_common import (
    blob,
    dt,
    host_key,
    integer,
    iso,
    one_row,
    optional_text,
    scope_from_values,
    scoped_page,
    text,
    validate_sha256,
)


class SqliteFiscalOutboxStore:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def counts_by_status(self) -> dict[FiscalOutboxStatus, int]:
        """Aggregate in the database without payloads, scope IDs or pagination."""
        counts = dict.fromkeys(FiscalOutboxStatus, 0)
        for status, count in self._connection.execute(
            "SELECT status, COUNT(*) FROM fm_fiscal_outbox GROUP BY status"
        ).fetchall():
            counts[FiscalOutboxStatus(text(status, "status"))] = integer(count, "count")
        return counts

    def list_for_scope(
        self,
        scope: ExecutionScope,
        *,
        limit: int = 100,
        offset: int = 0,
        statuses: frozenset[FiscalOutboxStatus] | None = None,
        operations: frozenset[str] | None = None,
    ) -> tuple[FiscalOutboxEntry, ...]:
        page = scoped_page(scope, limit, offset)
        if statuses is not None and not statuses:
            return ()
        filtering = (
            "" if statuses is None else " AND status IN (" + ",".join("?" for _ in statuses) + ")"
        )
        values = () if statuses is None else tuple(sorted(item.value for item in statuses))
        if operations is not None:
            if not operations:
                return ()
            filtering += " AND operation IN (" + ",".join("?" for _ in operations) + ")"
            values += tuple(sorted(operations))
        rows = self._connection.execute(
            f"""SELECT entry_id, host_namespace, tenant_id, unit_id, environment,
                      correlation_id, operation, deduplication_key, payload, payload_sha256,
                      created_at, available_at, status, attempt_count, lease_until,
                      last_error, completion_reference
               FROM fm_fiscal_outbox
               WHERE host_namespace = ? AND tenant_id = ? AND unit_id = ?
                 AND environment = ? {filtering}
               ORDER BY created_at DESC, entry_id DESC LIMIT ? OFFSET ?""",
            (*page[:4], *values, *page[4:]),
        ).fetchall()
        return tuple(self._entry(cast(tuple[object, ...], row)) for row in rows)

    @staticmethod
    def _entry(row: tuple[object, ...]) -> FiscalOutboxEntry:
        lease_until = optional_text(row[14], "lease_until")
        return FiscalOutboxEntry(
            entry_id=text(row[0], "entry_id"),
            scope=scope_from_values(row[1], row[2], row[3], row[4], row[5]),
            operation=text(row[6], "operation"),
            deduplication_key=text(row[7], "deduplication_key"),
            payload=blob(row[8], "payload"),
            payload_sha256=text(row[9], "payload_sha256"),
            created_at=dt(text(row[10], "created_at")),
            available_at=dt(text(row[11], "available_at")),
            status=FiscalOutboxStatus(text(row[12], "status")),
            attempt_count=integer(row[13], "attempt_count"),
            lease_until=None if lease_until is None else dt(lease_until),
            last_error=optional_text(row[15], "last_error"),
            completion_reference=optional_text(row[16], "completion_reference"),
        )

    @staticmethod
    def _values(entry: FiscalOutboxEntry) -> tuple[object, ...]:
        return (
            entry.entry_id,
            host_key(entry.scope.host_namespace),
            entry.scope.tenant_id,
            entry.scope.unit_id,
            entry.scope.environment.value,
            entry.scope.correlation_id,
            entry.operation,
            entry.deduplication_key,
            entry.payload,
            entry.payload_sha256,
            iso(entry.created_at),
            iso(entry.available_at),
            entry.status.value,
            entry.attempt_count,
            None if entry.lease_until is None else iso(entry.lease_until),
            entry.last_error,
            entry.completion_reference,
        )

    def _get_row(self, entry_id: str) -> tuple[object, ...] | None:
        return one_row(
            self._connection.execute(
                """
                SELECT entry_id, host_namespace, tenant_id, unit_id, environment,
                       correlation_id, operation, deduplication_key, payload,
                       payload_sha256, created_at, available_at, status, attempt_count,
                       lease_until, last_error, completion_reference
                FROM fm_fiscal_outbox WHERE entry_id = ?
                """,
                (entry_id,),
            )
        )

    def enqueue(self, entry: FiscalOutboxEntry) -> FiscalOutboxEnqueueResult:
        if not isinstance(entry, FiscalOutboxEntry):
            raise FiscalValidationError("entry must be FiscalOutboxEntry")
        existing = self.get(entry.entry_id)
        if existing is not None:
            if (
                existing.scope != entry.scope
                or existing.operation != entry.operation
                or existing.deduplication_key != entry.deduplication_key
                or existing.payload_sha256 != entry.payload_sha256
                or existing.payload != entry.payload
            ):
                raise OutboxConflictError(
                    "outbox deduplication identity was reused with different content"
                )
            return FiscalOutboxEnqueueResult(entry=existing, replay=True)
        self._connection.execute(
            """
            INSERT INTO fm_fiscal_outbox VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            self._values(entry),
        )
        return FiscalOutboxEnqueueResult(entry=entry, replay=False)

    def claim_due(
        self,
        *,
        now: datetime,
        limit: int,
        lease_duration: timedelta,
    ) -> tuple[FiscalOutboxEntry, ...]:
        now_iso = iso(now)
        if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
            raise FiscalValidationError("limit must be a positive integer")
        if lease_duration <= timedelta(0):
            raise FiscalValidationError("lease_duration must be positive")
        rows = self._connection.execute(
            """
            SELECT current.entry_id, current.host_namespace, current.tenant_id,
                   current.unit_id, current.environment, current.correlation_id,
                   current.operation, current.deduplication_key, current.payload,
                   current.payload_sha256, current.created_at, current.available_at,
                   current.status, current.attempt_count, current.lease_until,
                   current.last_error, current.completion_reference
            FROM fm_fiscal_outbox AS current
            LEFT JOIN fm_fiscal_outbox_ordering AS current_ordering
              ON current_ordering.entry_id = current.entry_id
            WHERE (
                (current.status IN (?, ?) AND current.available_at <= ?)
                OR (
                    current.status = ? AND current.lease_until IS NOT NULL
                    AND current.lease_until <= ?
                )
            )
            AND (
                current_ordering.ordering_key IS NULL
                OR NOT EXISTS (
                    SELECT 1
                    FROM fm_fiscal_outbox AS previous
                    JOIN fm_fiscal_outbox_ordering AS previous_ordering
                      ON previous_ordering.entry_id = previous.entry_id
                    WHERE previous.host_namespace = current.host_namespace
                      AND previous.tenant_id = current.tenant_id
                      AND previous.unit_id = current.unit_id
                      AND previous.environment = current.environment
                      AND previous_ordering.ordering_key = current_ordering.ordering_key
                      AND previous.status NOT IN (?, ?)
                      AND (
                          previous.created_at < current.created_at
                          OR (
                              previous.created_at = current.created_at
                              AND previous.entry_id < current.entry_id
                          )
                      )
                )
            )
            ORDER BY current.available_at, current.created_at, current.entry_id
            LIMIT ?
            """,
            (
                FiscalOutboxStatus.PENDING.value,
                FiscalOutboxStatus.RETRY_WAIT.value,
                now_iso,
                FiscalOutboxStatus.IN_FLIGHT.value,
                now_iso,
                FiscalOutboxStatus.SUCCEEDED.value,
                FiscalOutboxStatus.DEAD_LETTER.value,
                limit,
            ),
        ).fetchall()
        claimed: list[FiscalOutboxEntry] = []
        for raw in rows:
            entry = self._entry(cast(tuple[object, ...], raw))
            updated = replace(
                entry,
                status=FiscalOutboxStatus.IN_FLIGHT,
                attempt_count=entry.attempt_count + 1,
                lease_until=now + lease_duration,
                last_error=None,
            )
            if self._replace(
                updated, expected_status=entry.status, expected_attempt=entry.attempt_count
            ):
                claimed.append(updated)
        return tuple(claimed)

    def mark_succeeded(
        self,
        entry_id: str,
        *,
        expected_attempt: int,
        completion_reference: str,
    ) -> FiscalOutboxEntry:
        current = self._expect_in_flight(entry_id, expected_attempt)
        reference = completion_reference.strip()
        if not reference:
            raise FiscalValidationError("completion_reference must not be blank")
        updated = replace(
            current,
            status=FiscalOutboxStatus.SUCCEEDED,
            lease_until=None,
            last_error=None,
            completion_reference=reference,
        )
        self._replace_in_flight(updated, expected_attempt)
        return updated

    def reschedule(
        self,
        entry_id: str,
        *,
        expected_attempt: int,
        available_at: datetime,
        error: str,
    ) -> FiscalOutboxEntry:
        iso(available_at)
        current = self._expect_in_flight(entry_id, expected_attempt)
        normalized_error = error.strip()
        if not normalized_error:
            raise FiscalValidationError("error must not be blank")
        updated = replace(
            current,
            status=FiscalOutboxStatus.RETRY_WAIT,
            available_at=available_at,
            lease_until=None,
            last_error=normalized_error,
            completion_reference=None,
        )
        self._replace_in_flight(updated, expected_attempt)
        return updated

    def dead_letter(
        self,
        entry_id: str,
        *,
        expected_attempt: int,
        error: str,
    ) -> FiscalOutboxEntry:
        current = self._expect_in_flight(entry_id, expected_attempt)
        normalized_error = error.strip()
        if not normalized_error:
            raise FiscalValidationError("error must not be blank")
        updated = replace(
            current,
            status=FiscalOutboxStatus.DEAD_LETTER,
            lease_until=None,
            last_error=normalized_error,
            completion_reference=None,
        )
        self._replace_in_flight(updated, expected_attempt)
        return updated

    def get(self, entry_id: str) -> FiscalOutboxEntry | None:
        normalized = validate_sha256(entry_id, "entry_id")
        row = self._get_row(normalized)
        return None if row is None else self._entry(row)

    def _expect_in_flight(self, entry_id: str, expected_attempt: int) -> FiscalOutboxEntry:
        current = self.get(entry_id)
        if current is None:
            raise OutboxStateError("outbox entry does not exist")
        if current.status is not FiscalOutboxStatus.IN_FLIGHT:
            raise OutboxStateError("outbox entry is not in flight")
        if current.attempt_count != expected_attempt:
            raise OutboxStateError("outbox attempt version does not match")
        return current

    def _replace_in_flight(self, entry: FiscalOutboxEntry, expected_attempt: int) -> None:
        if not self._replace(
            entry,
            expected_status=FiscalOutboxStatus.IN_FLIGHT,
            expected_attempt=expected_attempt,
        ):
            raise OutboxStateError("outbox attempt version or state changed during transition")

    def _replace(
        self,
        entry: FiscalOutboxEntry,
        *,
        expected_status: FiscalOutboxStatus,
        expected_attempt: int,
    ) -> bool:
        # A read is not a fence: another PostgreSQL transaction can finish/reclaim
        # between SELECT and UPDATE. Compare both state and attempt in the write.
        values = self._values(entry)
        cursor = self._connection.execute(
            """
            UPDATE fm_fiscal_outbox SET
                host_namespace = ?, tenant_id = ?, unit_id = ?, environment = ?,
                correlation_id = ?, operation = ?, deduplication_key = ?, payload = ?,
                payload_sha256 = ?, created_at = ?, available_at = ?, status = ?,
                attempt_count = ?, lease_until = ?, last_error = ?, completion_reference = ?
            WHERE entry_id = ? AND status = ? AND attempt_count = ?
            """,
            (*values[1:], values[0], expected_status.value, expected_attempt),
        )
        return cursor.rowcount == 1


class SqliteFiscalArchiveStore:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def list_for_scope(
        self, scope: ExecutionScope, *, limit: int = 100, offset: int = 0
    ) -> tuple[FiscalArchiveEntry, ...]:
        rows = self._connection.execute(
            """SELECT entry_id, host_namespace, tenant_id, unit_id, environment,
                      correlation_id, document_reference, kind, content, content_sha256,
                      media_type, archived_at, retention_policy_id, retention_policy_version,
                      retain_until, legal_basis_reference, previous_manifest_sha256
               FROM fm_fiscal_archive
               WHERE host_namespace = ? AND tenant_id = ? AND unit_id = ?
                 AND environment = ?
               ORDER BY archived_at DESC, entry_id DESC LIMIT ? OFFSET ?""",
            scoped_page(scope, limit, offset),
        ).fetchall()
        return tuple(self._entry(cast(tuple[object, ...], row)) for row in rows)

    @staticmethod
    def _entry(row: tuple[object, ...]) -> FiscalArchiveEntry:
        retain_until = optional_text(row[14], "retain_until")
        return FiscalArchiveEntry(
            entry_id=text(row[0], "entry_id"),
            scope=scope_from_values(row[1], row[2], row[3], row[4], row[5]),
            document_reference=text(row[6], "document_reference"),
            kind=FiscalArchiveKind(text(row[7], "kind")),
            content=blob(row[8], "content"),
            content_sha256=text(row[9], "content_sha256"),
            media_type=text(row[10], "media_type"),
            archived_at=dt(text(row[11], "archived_at")),
            retention=RetentionPolicyMetadata(
                policy_id=text(row[12], "retention_policy_id"),
                policy_version=integer(row[13], "retention_policy_version"),
                retain_until=None if retain_until is None else dt(retain_until),
                legal_basis_reference=optional_text(row[15], "legal_basis_reference"),
            ),
            previous_manifest_sha256=optional_text(row[16], "previous_manifest_sha256"),
        )

    @staticmethod
    def _values(entry: FiscalArchiveEntry) -> tuple[object, ...]:
        return (
            entry.entry_id,
            host_key(entry.scope.host_namespace),
            entry.scope.tenant_id,
            entry.scope.unit_id,
            entry.scope.environment.value,
            entry.scope.correlation_id,
            entry.document_reference,
            entry.kind.value,
            entry.content,
            entry.content_sha256,
            entry.media_type,
            iso(entry.archived_at),
            entry.retention.policy_id,
            entry.retention.policy_version,
            None if entry.retention.retain_until is None else iso(entry.retention.retain_until),
            entry.retention.legal_basis_reference,
            entry.previous_manifest_sha256,
        )

    def append(self, entry: FiscalArchiveEntry) -> FiscalArchiveEntry:
        if not isinstance(entry, FiscalArchiveEntry):
            raise FiscalValidationError("entry must be FiscalArchiveEntry")
        existing = self.get(entry.entry_id)
        if existing is not None:
            if existing == entry:
                return existing
            raise ArchiveConflictError("archive entry identity already exists with other content")
        self._connection.execute(
            """
            INSERT INTO fm_fiscal_archive (
                entry_id, host_namespace, tenant_id, unit_id, environment, correlation_id,
                document_reference, kind, content, content_sha256, media_type, archived_at,
                retention_policy_id, retention_policy_version, retain_until,
                legal_basis_reference, previous_manifest_sha256
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            self._values(entry),
        )
        return entry

    def get(self, entry_id: str) -> FiscalArchiveEntry | None:
        normalized = validate_sha256(entry_id, "entry_id")
        row = one_row(
            self._connection.execute(
                """
                SELECT entry_id, host_namespace, tenant_id, unit_id, environment,
                       correlation_id, document_reference, kind, content, content_sha256,
                       media_type, archived_at, retention_policy_id,
                       retention_policy_version, retain_until, legal_basis_reference,
                       previous_manifest_sha256
                FROM fm_fiscal_archive WHERE entry_id = ?
                """,
                (normalized,),
            )
        )
        return None if row is None else self._entry(row)

    def list_for_document(
        self,
        scope: ExecutionScope,
        document_reference: str,
    ) -> tuple[FiscalArchiveEntry, ...]:
        if not isinstance(scope, ExecutionScope):
            raise FiscalValidationError("scope must be ExecutionScope")
        reference = document_reference.strip()
        if not reference:
            raise FiscalValidationError("document_reference must not be blank")
        rows = self._connection.execute(
            """
            SELECT entry_id, host_namespace, tenant_id, unit_id, environment,
                   correlation_id, document_reference, kind, content, content_sha256,
                   media_type, archived_at, retention_policy_id,
                   retention_policy_version, retain_until, legal_basis_reference,
                   previous_manifest_sha256
            FROM fm_fiscal_archive
            WHERE host_namespace = ? AND tenant_id = ? AND unit_id = ?
              AND environment = ? AND document_reference = ?
            ORDER BY archived_at, entry_id
            """,
            (
                host_key(scope.host_namespace),
                scope.tenant_id,
                scope.unit_id,
                scope.environment.value,
                reference,
            ),
        ).fetchall()
        return tuple(self._entry(cast(tuple[object, ...], row)) for row in rows)
