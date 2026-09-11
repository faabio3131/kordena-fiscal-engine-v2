"""Durable SQLite reference adapter for FM Fiscal V2 application state.

SQLite is used as the zero-extra-dependency durable reference adapter. The
schema is intentionally private to this adapter; domain and public Bridge
contracts remain database-agnostic. Every application transaction enters with
``BEGIN IMMEDIATE`` so writers serialize before reading mutable fiscal state.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from pathlib import Path
from types import TracebackType
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
from kordena_fiscal.domain import (
    ElectronicInvoiceModel,
    ExecutionScope,
    FiscalAccountBinding,
    FiscalAccountId,
    FiscalEnvironment,
    FiscalUnitId,
    FiscalValidationError,
    HostNamespace,
    HostScope,
    SourceReference,
)
from kordena_fiscal.lifecycle import (
    IdempotencyConflictError,
    IdempotencyKey,
    IdempotencyReservation,
    IdempotencyStateError,
    IssuanceAttempt,
    IssuanceAttemptStatus,
    FiscalDocumentState,
    FiscalStateSnapshot,
    FiscalStateTransition,
)
from kordena_fiscal.numbering import (
    FiscalNumberReservation,
    FiscalSequenceKey,
    FiscalSequencePolicy,
    SequenceExhaustedError,
    SequenceStateError,
)
from kordena_fiscal.reconciliation import (
    FiscalReconciliationResult,
    ReconciliationIssue,
    ReconciliationIssueCode,
    ReconciliationStatus,
)

from .ports import (
    PersistenceConflictError,
    PersistenceStateError,
)


@dataclass(frozen=True, slots=True)
class _Migration:
    version: int
    name: str
    statements: tuple[str, ...]


_MIGRATIONS = (
    _Migration(
        version=1,
        name="v2_07_durable_fiscal_state",
        statements=(
            """
            CREATE TABLE fm_idempotency_attempts (
                key TEXT NOT NULL,
                generation INTEGER NOT NULL,
                request_fingerprint TEXT NOT NULL,
                document_id TEXT NOT NULL,
                status TEXT NOT NULL,
                result_reference TEXT,
                rejection_reason TEXT,
                PRIMARY KEY (key, generation)
            )
            """,
            """
            CREATE TABLE fm_fiscal_sequences (
                host_namespace TEXT NOT NULL,
                tenant_id TEXT NOT NULL,
                unit_id TEXT NOT NULL,
                environment TEXT NOT NULL,
                model INTEGER NOT NULL,
                series INTEGER NOT NULL,
                first_number INTEGER NOT NULL,
                max_number INTEGER,
                last_reserved INTEGER NOT NULL,
                PRIMARY KEY (
                    host_namespace, tenant_id, unit_id, environment, model, series
                )
            )
            """,
            """
            CREATE TABLE fm_fiscal_lifecycle (
                document_id TEXT PRIMARY KEY,
                state TEXT NOT NULL,
                version INTEGER NOT NULL,
                updated_at TEXT NOT NULL,
                history_json TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE fm_fiscal_bindings (
                binding_id TEXT PRIMARY KEY,
                host_namespace TEXT NOT NULL,
                external_tenant_id TEXT NOT NULL,
                external_unit_id TEXT NOT NULL,
                fiscal_account_id TEXT NOT NULL,
                fiscal_unit_id TEXT NOT NULL,
                UNIQUE (host_namespace, external_tenant_id, external_unit_id)
            )
            """,
            """
            CREATE TABLE fm_fiscal_outbox (
                entry_id TEXT PRIMARY KEY,
                host_namespace TEXT NOT NULL,
                tenant_id TEXT NOT NULL,
                unit_id TEXT NOT NULL,
                environment TEXT NOT NULL,
                correlation_id TEXT NOT NULL,
                operation TEXT NOT NULL,
                deduplication_key TEXT NOT NULL,
                payload BLOB NOT NULL,
                payload_sha256 TEXT NOT NULL,
                created_at TEXT NOT NULL,
                available_at TEXT NOT NULL,
                status TEXT NOT NULL,
                attempt_count INTEGER NOT NULL,
                lease_until TEXT,
                last_error TEXT,
                completion_reference TEXT
            )
            """,
            """
            CREATE INDEX fm_fiscal_outbox_due_idx
            ON fm_fiscal_outbox (status, available_at, lease_until)
            """,
            """
            CREATE TABLE fm_fiscal_archive (
                entry_id TEXT PRIMARY KEY,
                host_namespace TEXT NOT NULL,
                tenant_id TEXT NOT NULL,
                unit_id TEXT NOT NULL,
                environment TEXT NOT NULL,
                correlation_id TEXT NOT NULL,
                document_reference TEXT NOT NULL,
                kind TEXT NOT NULL,
                content BLOB NOT NULL,
                content_sha256 TEXT NOT NULL,
                media_type TEXT NOT NULL,
                archived_at TEXT NOT NULL,
                retention_policy_id TEXT NOT NULL,
                retention_policy_version INTEGER NOT NULL,
                retain_until TEXT,
                legal_basis_reference TEXT,
                previous_manifest_sha256 TEXT
            )
            """,
            """
            CREATE INDEX fm_fiscal_archive_document_idx
            ON fm_fiscal_archive (
                host_namespace, tenant_id, unit_id, environment, document_reference
            )
            """,
            """
            CREATE TABLE fm_fiscal_reconciliation (
                host_namespace TEXT NOT NULL,
                tenant_id TEXT NOT NULL,
                unit_id TEXT NOT NULL,
                environment TEXT NOT NULL,
                source_type TEXT NOT NULL,
                source_id TEXT NOT NULL,
                correlation_id TEXT NOT NULL,
                status TEXT NOT NULL,
                fingerprint TEXT NOT NULL,
                selected_document_id TEXT,
                issues_json TEXT NOT NULL,
                PRIMARY KEY (
                    host_namespace, tenant_id, unit_id, environment, source_type, source_id
                )
            )
            """,
        ),
    ),
)


def _host(value: str | None) -> str:
    return value or ""


def _host_or_none(value: str) -> str | None:
    return value or None


def _iso(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise FiscalValidationError("persisted datetime must be timezone-aware")
    return value.isoformat()


def _dt(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise PersistenceStateError("persisted datetime is not timezone-aware")
    return parsed


def _text(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise PersistenceStateError(f"persisted {field_name} must be text")
    return value


def _integer(value: object, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise PersistenceStateError(f"persisted {field_name} must be integer")
    return value


def _blob(value: object, field_name: str) -> bytes:
    if isinstance(value, bytes):
        return value
    raise PersistenceStateError(f"persisted {field_name} must be bytes")


def _optional_text(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    return _text(value, field_name)


def _row(cursor: sqlite3.Cursor) -> tuple[object, ...] | None:
    value = cursor.fetchone()
    if value is None:
        return None
    return cast(tuple[object, ...], value)


def _scope_from_row(
    host_namespace: object,
    tenant_id: object,
    unit_id: object,
    environment: object,
    correlation_id: object,
) -> ExecutionScope:
    return ExecutionScope(
        host_namespace=_host_or_none(_text(host_namespace, "host_namespace")),
        tenant_id=_text(tenant_id, "tenant_id"),
        unit_id=_text(unit_id, "unit_id"),
        environment=FiscalEnvironment(_text(environment, "environment")),
        correlation_id=_text(correlation_id, "correlation_id"),
    )


def _sequence_token(key: FiscalSequenceKey, number: int) -> str:
    return hashlib.sha256(f"{key.canonical_material}|{number}".encode()).hexdigest()


class SqliteIdempotencyStore:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    @staticmethod
    def _attempt(row: tuple[object, ...]) -> IssuanceAttempt:
        return IssuanceAttempt(
            key=IdempotencyKey(_text(row[0], "key")),
            generation=_integer(row[1], "generation"),
            request_fingerprint=_text(row[2], "request_fingerprint"),
            document_id=_text(row[3], "document_id"),
            status=IssuanceAttemptStatus(_text(row[4], "status")),
            result_reference=_optional_text(row[5], "result_reference"),
            rejection_reason=_optional_text(row[6], "rejection_reason"),
        )

    def _latest(self, key: IdempotencyKey) -> IssuanceAttempt | None:
        row = _row(
            self._connection.execute(
                """
                SELECT key, generation, request_fingerprint, document_id, status,
                       result_reference, rejection_reason
                FROM fm_idempotency_attempts
                WHERE key = ?
                ORDER BY generation DESC
                LIMIT 1
                """,
                (key.value,),
            )
        )
        return None if row is None else self._attempt(row)

    def reserve(
        self,
        key: IdempotencyKey,
        request_fingerprint: str,
        document_id: str,
    ) -> IdempotencyReservation:
        if not isinstance(key, IdempotencyKey):
            raise FiscalValidationError("key must be IdempotencyKey")
        latest = self._latest(key)
        if latest is None:
            attempt = IssuanceAttempt(
                key=key,
                generation=1,
                request_fingerprint=request_fingerprint,
                document_id=document_id,
            )
            self._insert(attempt)
            return IdempotencyReservation(attempt=attempt, replay=False)
        if latest.request_fingerprint == request_fingerprint:
            return IdempotencyReservation(attempt=latest, replay=True)
        if latest.status is not IssuanceAttemptStatus.REJECTED:
            raise IdempotencyConflictError(
                "issuance intent already exists with different content and is not safely rejected"
            )
        attempt = IssuanceAttempt(
            key=key,
            generation=latest.generation + 1,
            request_fingerprint=request_fingerprint,
            document_id=document_id,
        )
        self._insert(attempt)
        return IdempotencyReservation(attempt=attempt, replay=False)

    def _insert(self, attempt: IssuanceAttempt) -> None:
        self._connection.execute(
            """
            INSERT INTO fm_idempotency_attempts (
                key, generation, request_fingerprint, document_id, status,
                result_reference, rejection_reason
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                attempt.key.value,
                attempt.generation,
                attempt.request_fingerprint,
                attempt.document_id,
                attempt.status.value,
                attempt.result_reference,
                attempt.rejection_reason,
            ),
        )

    def mark_authorized(
        self,
        key: IdempotencyKey,
        generation: int,
        result_reference: str,
    ) -> IssuanceAttempt:
        reference = result_reference.strip()
        if not reference:
            raise FiscalValidationError("result_reference must not be blank")
        latest = self._latest_for_update(key, generation)
        if latest.status is IssuanceAttemptStatus.AUTHORIZED:
            if latest.result_reference != reference:
                raise IdempotencyStateError("authorized attempt cannot change result_reference")
            return latest
        if latest.status is not IssuanceAttemptStatus.RESERVED:
            raise IdempotencyStateError("only reserved attempt can become authorized")
        updated = replace(
            latest,
            status=IssuanceAttemptStatus.AUTHORIZED,
            result_reference=reference,
        )
        self._connection.execute(
            """
            UPDATE fm_idempotency_attempts
            SET status = ?, result_reference = ?, rejection_reason = NULL
            WHERE key = ? AND generation = ?
            """,
            (updated.status.value, reference, key.value, generation),
        )
        return updated

    def mark_rejected(
        self,
        key: IdempotencyKey,
        generation: int,
        rejection_reason: str,
    ) -> IssuanceAttempt:
        reason = rejection_reason.strip()
        if not reason:
            raise FiscalValidationError("rejection_reason must not be blank")
        latest = self._latest_for_update(key, generation)
        if latest.status is IssuanceAttemptStatus.REJECTED:
            if latest.rejection_reason != reason:
                raise IdempotencyStateError("rejected attempt cannot change rejection_reason")
            return latest
        if latest.status is not IssuanceAttemptStatus.RESERVED:
            raise IdempotencyStateError("only reserved attempt can become rejected")
        updated = replace(
            latest,
            status=IssuanceAttemptStatus.REJECTED,
            rejection_reason=reason,
        )
        self._connection.execute(
            """
            UPDATE fm_idempotency_attempts
            SET status = ?, rejection_reason = ?, result_reference = NULL
            WHERE key = ? AND generation = ?
            """,
            (updated.status.value, reason, key.value, generation),
        )
        return updated

    def attempts(self, key: IdempotencyKey) -> tuple[IssuanceAttempt, ...]:
        rows = self._connection.execute(
            """
            SELECT key, generation, request_fingerprint, document_id, status,
                   result_reference, rejection_reason
            FROM fm_idempotency_attempts
            WHERE key = ?
            ORDER BY generation
            """,
            (key.value,),
        ).fetchall()
        return tuple(self._attempt(cast(tuple[object, ...], row)) for row in rows)

    def _latest_for_update(self, key: IdempotencyKey, generation: int) -> IssuanceAttempt:
        latest = self._latest(key)
        if latest is None:
            raise IdempotencyStateError("idempotency key has no reserved attempt")
        if latest.generation != generation:
            raise IdempotencyStateError("only the latest generation can be updated")
        return latest


class SqliteFiscalSequenceStore:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    @staticmethod
    def _identity(key: FiscalSequenceKey) -> tuple[object, ...]:
        return (
            _host(key.host_namespace),
            key.tenant_id,
            key.unit_id,
            key.environment.value,
            key.model.value,
            key.series,
        )

    def reserve_next(
        self,
        key: FiscalSequenceKey,
        policy: FiscalSequencePolicy,
    ) -> FiscalNumberReservation:
        if not isinstance(key, FiscalSequenceKey):
            raise FiscalValidationError("key must be FiscalSequenceKey")
        if not isinstance(policy, FiscalSequencePolicy):
            raise FiscalValidationError("policy must be FiscalSequencePolicy")
        identity = self._identity(key)
        row = _row(
            self._connection.execute(
                """
                SELECT first_number, max_number, last_reserved
                FROM fm_fiscal_sequences
                WHERE host_namespace = ? AND tenant_id = ? AND unit_id = ?
                  AND environment = ? AND model = ? AND series = ?
                """,
                identity,
            )
        )
        if row is None:
            candidate = policy.first_number
            if policy.max_number is not None and candidate > policy.max_number:
                raise SequenceExhaustedError("fiscal sequence has reached its configured maximum")
            self._connection.execute(
                """
                INSERT INTO fm_fiscal_sequences (
                    host_namespace, tenant_id, unit_id, environment, model, series,
                    first_number, max_number, last_reserved
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (*identity, policy.first_number, policy.max_number, candidate),
            )
        else:
            stored_first = _integer(row[0], "first_number")
            stored_max = None if row[1] is None else _integer(row[1], "max_number")
            if stored_first != policy.first_number or stored_max != policy.max_number:
                raise SequenceStateError("sequence policy cannot change after first reservation")
            candidate = _integer(row[2], "last_reserved") + 1
            if policy.max_number is not None and candidate > policy.max_number:
                raise SequenceExhaustedError("fiscal sequence has reached its configured maximum")
            self._connection.execute(
                """
                UPDATE fm_fiscal_sequences
                SET last_reserved = ?
                WHERE host_namespace = ? AND tenant_id = ? AND unit_id = ?
                  AND environment = ? AND model = ? AND series = ?
                """,
                (candidate, *identity),
            )
        return FiscalNumberReservation(
            key=key,
            number=candidate,
            reservation_token=_sequence_token(key, candidate),
        )

    def last_reserved(self, key: FiscalSequenceKey) -> int | None:
        if not isinstance(key, FiscalSequenceKey):
            raise FiscalValidationError("key must be FiscalSequenceKey")
        row = _row(
            self._connection.execute(
                """
                SELECT last_reserved FROM fm_fiscal_sequences
                WHERE host_namespace = ? AND tenant_id = ? AND unit_id = ?
                  AND environment = ? AND model = ? AND series = ?
                """,
                self._identity(key),
            )
        )
        return None if row is None else _integer(row[0], "last_reserved")


class SqliteLifecycleRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    @staticmethod
    def _history_json(snapshot: FiscalStateSnapshot) -> str:
        payload = [
            {
                "sequence": item.sequence,
                "from_state": item.from_state.value,
                "to_state": item.to_state.value,
                "occurred_at": item.occurred_at.isoformat(),
                "reason": item.reason,
                "correlation_id": item.correlation_id,
            }
            for item in snapshot.history
        ]
        return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    @staticmethod
    def _snapshot(row: tuple[object, ...]) -> FiscalStateSnapshot:
        raw_history = json.loads(_text(row[4], "history_json"))
        if not isinstance(raw_history, list):
            raise PersistenceStateError("persisted lifecycle history must be a list")
        history: list[FiscalStateTransition] = []
        for item in raw_history:
            if not isinstance(item, dict):
                raise PersistenceStateError("persisted lifecycle transition must be an object")
            history.append(
                FiscalStateTransition(
                    sequence=_integer(item.get("sequence"), "transition.sequence"),
                    from_state=FiscalDocumentState(
                        _text(item.get("from_state"), "transition.from_state")
                    ),
                    to_state=FiscalDocumentState(
                        _text(item.get("to_state"), "transition.to_state")
                    ),
                    occurred_at=_dt(_text(item.get("occurred_at"), "transition.occurred_at")),
                    reason=_text(item.get("reason"), "transition.reason"),
                    correlation_id=_text(
                        item.get("correlation_id"), "transition.correlation_id"
                    ),
                )
            )
        return FiscalStateSnapshot(
            document_id=_text(row[0], "document_id"),
            state=FiscalDocumentState(_text(row[1], "state")),
            version=_integer(row[2], "version"),
            updated_at=_dt(_text(row[3], "updated_at")),
            history=tuple(history),
        )

    def add(self, snapshot: FiscalStateSnapshot) -> FiscalStateSnapshot:
        if not isinstance(snapshot, FiscalStateSnapshot):
            raise FiscalValidationError("snapshot must be FiscalStateSnapshot")
        existing = self.get(snapshot.document_id)
        if existing is not None:
            if existing == snapshot:
                return existing
            raise PersistenceConflictError("lifecycle document_id already exists")
        self._connection.execute(
            """
            INSERT INTO fm_fiscal_lifecycle (
                document_id, state, version, updated_at, history_json
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                snapshot.document_id,
                snapshot.state.value,
                snapshot.version,
                _iso(snapshot.updated_at),
                self._history_json(snapshot),
            ),
        )
        return snapshot

    def get(self, document_id: str) -> FiscalStateSnapshot | None:
        normalized = document_id.strip()
        if not normalized:
            raise FiscalValidationError("document_id must not be blank")
        row = _row(
            self._connection.execute(
                """
                SELECT document_id, state, version, updated_at, history_json
                FROM fm_fiscal_lifecycle WHERE document_id = ?
                """,
                (normalized,),
            )
        )
        return None if row is None else self._snapshot(row)

    def save(
        self,
        snapshot: FiscalStateSnapshot,
        *,
        expected_version: int,
    ) -> FiscalStateSnapshot:
        if not isinstance(snapshot, FiscalStateSnapshot):
            raise FiscalValidationError("snapshot must be FiscalStateSnapshot")
        if snapshot.version != expected_version + 1:
            raise PersistenceConflictError(
                "lifecycle save requires exactly one transition after expected_version"
            )
        cursor = self._connection.execute(
            """
            UPDATE fm_fiscal_lifecycle
            SET state = ?, version = ?, updated_at = ?, history_json = ?
            WHERE document_id = ? AND version = ?
            """,
            (
                snapshot.state.value,
                snapshot.version,
                _iso(snapshot.updated_at),
                self._history_json(snapshot),
                snapshot.document_id,
                expected_version,
            ),
        )
        if cursor.rowcount != 1:
            raise PersistenceConflictError("lifecycle optimistic version conflict")
        return snapshot


class SqliteBindingRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    @staticmethod
    def _binding(row: tuple[object, ...]) -> FiscalAccountBinding:
        return FiscalAccountBinding(
            binding_id=_text(row[0], "binding_id"),
            host_scope=HostScope(
                namespace=HostNamespace(_text(row[1], "host_namespace")),
                tenant_id=_text(row[2], "external_tenant_id"),
                unit_id=_text(row[3], "external_unit_id"),
            ),
            fiscal_account_id=FiscalAccountId(_text(row[4], "fiscal_account_id")),
            fiscal_unit_id=FiscalUnitId(_text(row[5], "fiscal_unit_id")),
        )

    def add(self, binding: FiscalAccountBinding) -> FiscalAccountBinding:
        if not isinstance(binding, FiscalAccountBinding):
            raise FiscalValidationError("binding must be FiscalAccountBinding")
        existing_id = self.get_by_id(binding.binding_id)
        if existing_id is not None:
            if existing_id == binding:
                return existing_id
            raise PersistenceConflictError("binding_id already maps to another host scope")
        try:
            self._connection.execute(
                """
                INSERT INTO fm_fiscal_bindings (
                    binding_id, host_namespace, external_tenant_id, external_unit_id,
                    fiscal_account_id, fiscal_unit_id
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    binding.binding_id,
                    binding.host_scope.namespace.value,
                    binding.host_scope.tenant_id,
                    binding.host_scope.unit_id,
                    binding.fiscal_account_id.value,
                    binding.fiscal_unit_id.value,
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise PersistenceConflictError(
                "an exact fiscal binding already exists for this host scope"
            ) from exc
        return binding

    def resolve(self, host_scope: HostScope) -> FiscalAccountBinding:
        if not isinstance(host_scope, HostScope):
            raise FiscalValidationError("host_scope must be HostScope")
        row = _row(
            self._connection.execute(
                """
                SELECT binding_id, host_namespace, external_tenant_id, external_unit_id,
                       fiscal_account_id, fiscal_unit_id
                FROM fm_fiscal_bindings
                WHERE host_namespace = ? AND external_tenant_id = ? AND external_unit_id = ?
                """,
                host_scope.canonical_key,
            )
        )
        if row is None:
            raise PersistenceStateError("no durable fiscal binding exists for exact host scope")
        return self._binding(row)

    def get_by_id(self, binding_id: str) -> FiscalAccountBinding | None:
        normalized = binding_id.strip()
        if not normalized:
            raise FiscalValidationError("binding_id must not be blank")
        row = _row(
            self._connection.execute(
                """
                SELECT binding_id, host_namespace, external_tenant_id, external_unit_id,
                       fiscal_account_id, fiscal_unit_id
                FROM fm_fiscal_bindings WHERE binding_id = ?
                """,
                (normalized,),
            )
        )
        return None if row is None else self._binding(row)


class SqliteFiscalOutboxStore:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    @staticmethod
    def _entry(row: tuple[object, ...]) -> FiscalOutboxEntry:
        lease = _optional_text(row[13], "lease_until")
        return FiscalOutboxEntry(
            entry_id=_text(row[0], "entry_id"),
            scope=_scope_from_row(row[1], row[2], row[3], row[4], row[5]),
            operation=_text(row[6], "operation"),
            deduplication_key=_text(row[7], "deduplication_key"),
            payload=_blob(row[8], "payload"),
            payload_sha256=_text(row[9], "payload_sha256"),
            created_at=_dt(_text(row[10], "created_at")),
            available_at=_dt(_text(row[11], "available_at")),
            status=FiscalOutboxStatus(_text(row[12], "status")),
            attempt_count=_integer(row[13 - 1], "attempt_count"),
            lease_until=None if lease is None else _dt(lease),
            last_error=_optional_text(row[14], "last_error"),
            completion_reference=_optional_text(row[15], "completion_reference"),
        )

    @staticmethod
    def _values(entry: FiscalOutboxEntry) -> tuple[object, ...]:
        return (
            entry.entry_id,
            _host(entry.scope.host_namespace),
            entry.scope.tenant_id,
            entry.scope.unit_id,
            entry.scope.environment.value,
            entry.scope.correlation_id,
            entry.operation,
            entry.deduplication_key,
            entry.payload,
            entry.payload_sha256,
            _iso(entry.created_at),
            _iso(entry.available_at),
            entry.status.value,
            entry.attempt_count,
            None if entry.lease_until is None else _iso(entry.lease_until),
            entry.last_error,
            entry.completion_reference,
        )

    def _get_row(self, entry_id: str) -> tuple[object, ...] | None:
        return _row(
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
        _iso(now)
        if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
            raise FiscalValidationError("limit must be a positive integer")
        if lease_duration <= timedelta(0):
            raise FiscalValidationError("lease_duration must be positive")
        rows = self._connection.execute(
            """
            SELECT entry_id, host_namespace, tenant_id, unit_id, environment,
                   correlation_id, operation, deduplication_key, payload,
                   payload_sha256, created_at, available_at, status, attempt_count,
                   lease_until, last_error, completion_reference
            FROM fm_fiscal_outbox
            WHERE (
                status IN (?, ?) AND available_at <= ?
            ) OR (
                status = ? AND lease_until IS NOT NULL AND lease_until <= ?
            )
            ORDER BY available_at, created_at, entry_id
            LIMIT ?
            """,
            (
                FiscalOutboxStatus.PENDING.value,
                FiscalOutboxStatus.RETRY_WAIT.value,
                _iso(now),
                FiscalOutboxStatus.IN_FLIGHT.value,
                _iso(now),
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
            self._replace(updated)
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
        self._replace(updated)
        return updated

    def reschedule(
        self,
        entry_id: str,
        *,
        expected_attempt: int,
        available_at: datetime,
        error: str,
    ) -> FiscalOutboxEntry:
        _iso(available_at)
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
        self._replace(updated)
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
        self._replace(updated)
        return updated

    def get(self, entry_id: str) -> FiscalOutboxEntry | None:
        normalized = entry_id.strip().lower()
        if len(normalized) != 64:
            raise FiscalValidationError("entry_id must be SHA-256 hex")
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

    def _replace(self, entry: FiscalOutboxEntry) -> None:
        values = self._values(entry)
        self._connection.execute(
            """
            UPDATE fm_fiscal_outbox SET
                host_namespace = ?, tenant_id = ?, unit_id = ?, environment = ?,
                correlation_id = ?, operation = ?, deduplication_key = ?, payload = ?,
                payload_sha256 = ?, created_at = ?, available_at = ?, status = ?,
                attempt_count = ?, lease_until = ?, last_error = ?, completion_reference = ?
            WHERE entry_id = ?
            """,
            (*values[1:], values[0]),
        )


class SqliteFiscalArchiveStore:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    @staticmethod
    def _entry(row: tuple[object, ...]) -> FiscalArchiveEntry:
        retain_until = _optional_text(row[15], "retain_until")
        return FiscalArchiveEntry(
            entry_id=_text(row[0], "entry_id"),
            scope=_scope_from_row(row[1], row[2], row[3], row[4], row[5]),
            document_reference=_text(row[6], "document_reference"),
            kind=FiscalArchiveKind(_text(row[7], "kind")),
            content=_blob(row[8], "content"),
            content_sha256=_text(row[9], "content_sha256"),
            media_type=_text(row[10], "media_type"),
            archived_at=_dt(_text(row[11], "archived_at")),
            retention=RetentionPolicyMetadata(
                policy_id=_text(row[12], "retention_policy_id"),
                policy_version=_integer(row[13], "retention_policy_version"),
                retain_until=None if retain_until is None else _dt(retain_until),
                legal_basis_reference=_optional_text(row[16], "legal_basis_reference"),
            ),
            previous_manifest_sha256=_optional_text(row[17], "previous_manifest_sha256"),
        )

    @staticmethod
    def _values(entry: FiscalArchiveEntry) -> tuple[object, ...]:
        return (
            entry.entry_id,
            _host(entry.scope.host_namespace),
            entry.scope.tenant_id,
            entry.scope.unit_id,
            entry.scope.environment.value,
            entry.scope.correlation_id,
            entry.document_reference,
            entry.kind.value,
            entry.content,
            entry.content_sha256,
            entry.media_type,
            _iso(entry.archived_at),
            entry.retention.policy_id,
            entry.retention.policy_version,
            None,
            None if entry.retention.retain_until is None else _iso(entry.retention.retain_until),
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
        values = self._values(entry)
        self._connection.execute(
            """
            INSERT INTO fm_fiscal_archive (
                entry_id, host_namespace, tenant_id, unit_id, environment, correlation_id,
                document_reference, kind, content, content_sha256, media_type, archived_at,
                retention_policy_id, retention_policy_version, retain_until,
                legal_basis_reference, previous_manifest_sha256
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (*values[:14], *values[15:]),
        )
        return entry

    def get(self, entry_id: str) -> FiscalArchiveEntry | None:
        normalized = entry_id.strip().lower()
        if len(normalized) != 64:
            raise FiscalValidationError("entry_id must be SHA-256 hex")
        row = _row(
            self._connection.execute(
                """
                SELECT entry_id, host_namespace, tenant_id, unit_id, environment,
                       correlation_id, document_reference, kind, content, content_sha256,
                       media_type, archived_at, retention_policy_id,
                       retention_policy_version, NULL, retain_until,
                       legal_basis_reference, previous_manifest_sha256
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
                   retention_policy_version, NULL, retain_until,
                   legal_basis_reference, previous_manifest_sha256
            FROM fm_fiscal_archive
            WHERE host_namespace = ? AND tenant_id = ? AND unit_id = ?
              AND environment = ? AND document_reference = ?
            ORDER BY archived_at, entry_id
            """,
            (
                _host(scope.host_namespace),
                scope.tenant_id,
                scope.unit_id,
                scope.environment.value,
                reference,
            ),
        ).fetchall()
        return tuple(self._entry(cast(tuple[object, ...], row)) for row in rows)


class SqliteReconciliationRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    @staticmethod
    def _key(scope: ExecutionScope, source: SourceReference) -> tuple[str, ...]:
        return (
            _host(scope.host_namespace),
            scope.tenant_id,
            scope.unit_id,
            scope.environment.value,
            source.source_type,
            source.source_id,
        )

    @staticmethod
    def _issues_json(result: FiscalReconciliationResult) -> str:
        payload = [
            {
                "code": issue.code.value,
                "message": issue.message,
                "document_id": issue.document_id,
            }
            for issue in result.issues
        ]
        return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    @staticmethod
    def _result(row: tuple[object, ...]) -> FiscalReconciliationResult:
        scope = _scope_from_row(row[0], row[1], row[2], row[3], row[6])
        source = SourceReference(
            source_type=_text(row[4], "source_type"),
            source_id=_text(row[5], "source_id"),
        )
        raw_issues = json.loads(_text(row[10], "issues_json"))
        if not isinstance(raw_issues, list):
            raise PersistenceStateError("persisted reconciliation issues must be a list")
        issues: list[ReconciliationIssue] = []
        for item in raw_issues:
            if not isinstance(item, dict):
                raise PersistenceStateError("persisted reconciliation issue must be object")
            issues.append(
                ReconciliationIssue(
                    code=ReconciliationIssueCode(_text(item.get("code"), "issue.code")),
                    message=_text(item.get("message"), "issue.message"),
                    document_id=(
                        None
                        if item.get("document_id") is None
                        else _text(item.get("document_id"), "issue.document_id")
                    ),
                )
            )
        return FiscalReconciliationResult(
            status=ReconciliationStatus(_text(row[7], "status")),
            scope=scope,
            source=source,
            fingerprint=_text(row[8], "fingerprint"),
            selected_document_id=_optional_text(row[9], "selected_document_id"),
            issues=tuple(issues),
        )

    def save(self, result: FiscalReconciliationResult) -> FiscalReconciliationResult:
        if not isinstance(result, FiscalReconciliationResult):
            raise FiscalValidationError("result must be FiscalReconciliationResult")
        key = self._key(result.scope, result.source)
        self._connection.execute(
            """
            INSERT INTO fm_fiscal_reconciliation (
                host_namespace, tenant_id, unit_id, environment, source_type, source_id,
                correlation_id, status, fingerprint, selected_document_id, issues_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (
                host_namespace, tenant_id, unit_id, environment, source_type, source_id
            ) DO UPDATE SET
                correlation_id = excluded.correlation_id,
                status = excluded.status,
                fingerprint = excluded.fingerprint,
                selected_document_id = excluded.selected_document_id,
                issues_json = excluded.issues_json
            """,
            (
                *key,
                result.scope.correlation_id,
                result.status.value,
                result.fingerprint,
                result.selected_document_id,
                self._issues_json(result),
            ),
        )
        return result

    def get(
        self,
        scope: ExecutionScope,
        source: SourceReference,
    ) -> FiscalReconciliationResult | None:
        if not isinstance(scope, ExecutionScope):
            raise FiscalValidationError("scope must be ExecutionScope")
        if not isinstance(source, SourceReference):
            raise FiscalValidationError("source must be SourceReference")
        row = _row(
            self._connection.execute(
                """
                SELECT host_namespace, tenant_id, unit_id, environment,
                       source_type, source_id, correlation_id, status, fingerprint,
                       selected_document_id, issues_json
                FROM fm_fiscal_reconciliation
                WHERE host_namespace = ? AND tenant_id = ? AND unit_id = ?
                  AND environment = ? AND source_type = ? AND source_id = ?
                """,
                self._key(scope, source),
            )
        )
        return None if row is None else self._result(row)


class SqliteFiscalUnitOfWork:
    """One explicit SQLite transaction with all V2-07 persistence ports."""

    def __init__(self, database: SqliteFiscalDatabase) -> None:
        self._database = database
        self._connection: sqlite3.Connection | None = None
        self._committed = False
        self._idempotency: SqliteIdempotencyStore | None = None
        self._sequences: SqliteFiscalSequenceStore | None = None
        self._outbox: SqliteFiscalOutboxStore | None = None
        self._archive: SqliteFiscalArchiveStore | None = None
        self._bindings: SqliteBindingRepository | None = None
        self._lifecycle: SqliteLifecycleRepository | None = None
        self._reconciliations: SqliteReconciliationRepository | None = None

    def __enter__(self) -> SqliteFiscalUnitOfWork:
        if self._connection is not None:
            raise PersistenceStateError("unit of work cannot be entered twice")
        connection = self._database._connect()
        connection.execute("BEGIN IMMEDIATE")
        self._connection = connection
        self._idempotency = SqliteIdempotencyStore(connection)
        self._sequences = SqliteFiscalSequenceStore(connection)
        self._outbox = SqliteFiscalOutboxStore(connection)
        self._archive = SqliteFiscalArchiveStore(connection)
        self._bindings = SqliteBindingRepository(connection)
        self._lifecycle = SqliteLifecycleRepository(connection)
        self._reconciliations = SqliteReconciliationRepository(connection)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        connection = self._connection
        if connection is None:
            return
        try:
            if exc_type is not None or not self._committed:
                connection.rollback()
        finally:
            connection.close()
            self._connection = None

    def _require(self, value: object | None, name: str) -> object:
        if self._connection is None or value is None:
            raise PersistenceStateError(f"unit of work {name} repository is not active")
        return value

    @property
    def idempotency(self) -> SqliteIdempotencyStore:
        return cast(SqliteIdempotencyStore, self._require(self._idempotency, "idempotency"))

    @property
    def sequences(self) -> SqliteFiscalSequenceStore:
        return cast(SqliteFiscalSequenceStore, self._require(self._sequences, "sequences"))

    @property
    def outbox(self) -> SqliteFiscalOutboxStore:
        return cast(SqliteFiscalOutboxStore, self._require(self._outbox, "outbox"))

    @property
    def archive(self) -> SqliteFiscalArchiveStore:
        return cast(SqliteFiscalArchiveStore, self._require(self._archive, "archive"))

    @property
    def bindings(self) -> SqliteBindingRepository:
        return cast(SqliteBindingRepository, self._require(self._bindings, "bindings"))

    @property
    def lifecycle(self) -> SqliteLifecycleRepository:
        return cast(SqliteLifecycleRepository, self._require(self._lifecycle, "lifecycle"))

    @property
    def reconciliations(self) -> SqliteReconciliationRepository:
        return cast(
            SqliteReconciliationRepository,
            self._require(self._reconciliations, "reconciliations"),
        )

    def commit(self) -> None:
        if self._connection is None:
            raise PersistenceStateError("unit of work is not active")
        self._connection.commit()
        self._committed = True

    def rollback(self) -> None:
        if self._connection is None:
            raise PersistenceStateError("unit of work is not active")
        self._connection.rollback()
        self._committed = False


class SqliteFiscalDatabase:
    """Durable database handle plus controlled migration and UoW factory."""

    def __init__(self, path: str | Path) -> None:
        raw = str(path).strip()
        if not raw:
            raise FiscalValidationError("SQLite database path must not be blank")
        if raw == ":memory:":
            raise FiscalValidationError(
                "V2-07 durable adapter rejects ':memory:'; use a filesystem database"
            )
        self._path = Path(raw).expanduser().resolve()

    @property
    def path(self) -> Path:
        return self._path

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._path, timeout=30.0)
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 30000")
        return connection

    def initialize(self) -> tuple[int, ...]:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS fm_schema_migrations (
                    version INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    applied_at TEXT NOT NULL
                )
                """
            )
            applied_rows = connection.execute(
                "SELECT version FROM fm_schema_migrations ORDER BY version"
            ).fetchall()
            applied = {int(row[0]) for row in applied_rows}
            new_versions: list[int] = []
            for migration in _MIGRATIONS:
                if migration.version in applied:
                    continue
                for statement in migration.statements:
                    connection.execute(statement)
                connection.execute(
                    """
                    INSERT INTO fm_schema_migrations (version, name, applied_at)
                    VALUES (?, ?, ?)
                    """,
                    (migration.version, migration.name, datetime.now().astimezone().isoformat()),
                )
                new_versions.append(migration.version)
            connection.commit()
            return tuple(new_versions)
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def applied_migrations(self) -> tuple[int, ...]:
        connection = self._connect()
        try:
            rows = connection.execute(
                "SELECT version FROM fm_schema_migrations ORDER BY version"
            ).fetchall()
            return tuple(int(row[0]) for row in rows)
        except sqlite3.OperationalError:
            return ()
        finally:
            connection.close()

    def unit_of_work(self) -> SqliteFiscalUnitOfWork:
        return SqliteFiscalUnitOfWork(self)

    def __call__(self) -> SqliteFiscalUnitOfWork:
        return self.unit_of_work()
