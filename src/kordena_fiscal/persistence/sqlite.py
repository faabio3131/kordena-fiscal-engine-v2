"""Durable SQLite database, migrations and unit-of-work for FM Fiscal V2."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from types import TracebackType
from typing import TypeVar

from kordena_fiscal.domain import FiscalValidationError

from .ports import PersistenceStateError
from .sqlite_core import (
    SqliteBindingRepository,
    SqliteFiscalSequenceStore,
    SqliteLifecycleRepository,
)
from .sqlite_idempotency import SqliteIdempotencyStore
from .sqlite_inbox import SqliteFiscalInboxStore
from .sqlite_outbox_archive import SqliteFiscalArchiveStore, SqliteFiscalOutboxStore
from .sqlite_reconciliation import SqliteReconciliationRepository

_T = TypeVar("_T")


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
    _Migration(
        version=2,
        name="v2_08_durable_inbox",
        statements=(
            """
            CREATE TABLE fm_fiscal_inbox (
                entry_id TEXT PRIMARY KEY,
                host_namespace TEXT NOT NULL,
                tenant_id TEXT NOT NULL,
                unit_id TEXT NOT NULL,
                environment TEXT NOT NULL,
                correlation_id TEXT NOT NULL,
                producer TEXT NOT NULL,
                event_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                payload BLOB NOT NULL,
                payload_sha256 TEXT NOT NULL,
                occurred_at TEXT NOT NULL,
                received_at TEXT NOT NULL,
                causation_id TEXT,
                idempotency_key TEXT,
                status TEXT NOT NULL,
                version INTEGER NOT NULL,
                processed_at TEXT,
                outcome_reference TEXT,
                last_error TEXT,
                UNIQUE (
                    host_namespace, tenant_id, unit_id, environment, producer, event_id
                )
            )
            """,
            """
            CREATE INDEX fm_fiscal_inbox_status_idx
            ON fm_fiscal_inbox (status, received_at, entry_id)
            """,
        ),
    ),
)


class SqliteFiscalUnitOfWork:
    """One explicit local transaction spanning all durable fiscal repositories."""

    def __init__(self, database: SqliteFiscalDatabase) -> None:
        self._database = database
        self._connection: sqlite3.Connection | None = None
        self._committed = False
        self._idempotency: SqliteIdempotencyStore | None = None
        self._sequences: SqliteFiscalSequenceStore | None = None
        self._inbox: SqliteFiscalInboxStore | None = None
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
        self._committed = False
        self._idempotency = SqliteIdempotencyStore(connection)
        self._sequences = SqliteFiscalSequenceStore(connection)
        self._inbox = SqliteFiscalInboxStore(connection)
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

    def _require(self, value: _T | None, name: str) -> _T:
        if self._connection is None or value is None:
            raise PersistenceStateError(f"unit of work {name} repository is not active")
        return value

    @property
    def idempotency(self) -> SqliteIdempotencyStore:
        return self._require(self._idempotency, "idempotency")

    @property
    def sequences(self) -> SqliteFiscalSequenceStore:
        return self._require(self._sequences, "sequences")

    @property
    def inbox(self) -> SqliteFiscalInboxStore:
        return self._require(self._inbox, "inbox")

    @property
    def outbox(self) -> SqliteFiscalOutboxStore:
        return self._require(self._outbox, "outbox")

    @property
    def archive(self) -> SqliteFiscalArchiveStore:
        return self._require(self._archive, "archive")

    @property
    def bindings(self) -> SqliteBindingRepository:
        return self._require(self._bindings, "bindings")

    @property
    def lifecycle(self) -> SqliteLifecycleRepository:
        return self._require(self._lifecycle, "lifecycle")

    @property
    def reconciliations(self) -> SqliteReconciliationRepository:
        return self._require(self._reconciliations, "reconciliations")

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
    """Filesystem-backed database handle with controlled schema migration."""

    def __init__(self, path: str | Path) -> None:
        raw = str(path).strip()
        if not raw:
            raise FiscalValidationError("SQLite database path must not be blank")
        if raw == ":memory:":
            raise FiscalValidationError(
                "durable adapter rejects ':memory:'; use a filesystem database"
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
            rows = connection.execute(
                "SELECT version FROM fm_schema_migrations ORDER BY version"
            ).fetchall()
            applied = {int(row[0]) for row in rows}
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
