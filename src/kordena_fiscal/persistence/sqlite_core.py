"""SQLite adapters for numbering, lifecycle and host/fiscal bindings."""

from __future__ import annotations

import hashlib
import json
import sqlite3

from kordena_fiscal.domain import (
    FiscalAccountBinding,
    FiscalAccountId,
    FiscalUnitId,
    FiscalValidationError,
    HostNamespace,
    HostScope,
)
from kordena_fiscal.lifecycle import (
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

from ._sqlite_common import dt, host_key, integer, iso, one_row, text
from .ports import PersistenceConflictError, PersistenceStateError


def _sequence_token(key: FiscalSequenceKey, number: int) -> str:
    return hashlib.sha256(f"{key.canonical_material}|{number}".encode()).hexdigest()


class SqliteFiscalSequenceStore:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    @staticmethod
    def _identity(key: FiscalSequenceKey) -> tuple[object, ...]:
        return (
            host_key(key.host_namespace),
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
        row = one_row(
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
            stored_first = integer(row[0], "first_number")
            stored_max = None if row[1] is None else integer(row[1], "max_number")
            if stored_first != policy.first_number or stored_max != policy.max_number:
                raise SequenceStateError("sequence policy cannot change after first reservation")
            candidate = integer(row[2], "last_reserved") + 1
            if policy.max_number is not None and candidate > policy.max_number:
                raise SequenceExhaustedError("fiscal sequence has reached its configured maximum")
            self._connection.execute(
                """
                UPDATE fm_fiscal_sequences SET last_reserved = ?
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
        row = one_row(
            self._connection.execute(
                """
                SELECT last_reserved FROM fm_fiscal_sequences
                WHERE host_namespace = ? AND tenant_id = ? AND unit_id = ?
                  AND environment = ? AND model = ? AND series = ?
                """,
                self._identity(key),
            )
        )
        return None if row is None else integer(row[0], "last_reserved")


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
        raw_history: object = json.loads(text(row[4], "history_json"))
        if not isinstance(raw_history, list):
            raise PersistenceStateError("persisted lifecycle history must be a list")
        history: list[FiscalStateTransition] = []
        for item in raw_history:
            if not isinstance(item, dict):
                raise PersistenceStateError("persisted lifecycle transition must be an object")
            history.append(
                FiscalStateTransition(
                    sequence=integer(item.get("sequence"), "transition.sequence"),
                    from_state=FiscalDocumentState(
                        text(item.get("from_state"), "transition.from_state")
                    ),
                    to_state=FiscalDocumentState(
                        text(item.get("to_state"), "transition.to_state")
                    ),
                    occurred_at=dt(text(item.get("occurred_at"), "transition.occurred_at")),
                    reason=text(item.get("reason"), "transition.reason"),
                    correlation_id=text(
                        item.get("correlation_id"), "transition.correlation_id"
                    ),
                )
            )
        return FiscalStateSnapshot(
            document_id=text(row[0], "document_id"),
            state=FiscalDocumentState(text(row[1], "state")),
            version=integer(row[2], "version"),
            updated_at=dt(text(row[3], "updated_at")),
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
                iso(snapshot.updated_at),
                self._history_json(snapshot),
            ),
        )
        return snapshot

    def get(self, document_id: str) -> FiscalStateSnapshot | None:
        normalized = document_id.strip()
        if not normalized:
            raise FiscalValidationError("document_id must not be blank")
        row = one_row(
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
                iso(snapshot.updated_at),
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
            binding_id=text(row[0], "binding_id"),
            host_scope=HostScope(
                namespace=HostNamespace(text(row[1], "host_namespace")),
                tenant_id=text(row[2], "external_tenant_id"),
                unit_id=text(row[3], "external_unit_id"),
            ),
            fiscal_account_id=FiscalAccountId(text(row[4], "fiscal_account_id")),
            fiscal_unit_id=FiscalUnitId(text(row[5], "fiscal_unit_id")),
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
        row = one_row(
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
        row = one_row(
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
