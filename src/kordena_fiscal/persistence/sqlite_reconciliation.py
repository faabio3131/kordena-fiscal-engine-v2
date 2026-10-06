"""SQLite persistence for latest operation/fiscal reconciliation state."""

from __future__ import annotations

import json
import sqlite3
from typing import cast

from kordena_fiscal.domain import ExecutionScope, FiscalValidationError, SourceReference
from kordena_fiscal.reconciliation import (
    FiscalReconciliationResult,
    ReconciliationIssue,
    ReconciliationIssueCode,
    ReconciliationStatus,
)

from ._sqlite_common import host_key, one_row, optional_text, scope_from_values, scoped_page, text
from .ports import PersistenceStateError


class SqliteReconciliationRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def list_for_scope(
        self, scope: ExecutionScope, *, limit: int = 100, offset: int = 0
    ) -> tuple[FiscalReconciliationResult, ...]:
        rows = self._connection.execute(
            """SELECT host_namespace, tenant_id, unit_id, environment, source_type,
                      source_id, correlation_id, status, fingerprint,
                      selected_document_id, issues_json
               FROM fm_fiscal_reconciliation
               WHERE host_namespace = ? AND tenant_id = ? AND unit_id = ?
                 AND environment = ?
               ORDER BY source_type, source_id LIMIT ? OFFSET ?""",
            scoped_page(scope, limit, offset),
        ).fetchall()
        return tuple(self._result(cast(tuple[object, ...], row)) for row in rows)

    @staticmethod
    def _key(scope: ExecutionScope, source: SourceReference) -> tuple[str, ...]:
        return (
            host_key(scope.host_namespace),
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
        scope = scope_from_values(row[0], row[1], row[2], row[3], row[6])
        source = SourceReference(
            source_type=text(row[4], "source_type"),
            source_id=text(row[5], "source_id"),
        )
        raw_issues: object = json.loads(text(row[10], "issues_json"))
        if not isinstance(raw_issues, list):
            raise PersistenceStateError("persisted reconciliation issues must be a list")
        issues: list[ReconciliationIssue] = []
        for item in raw_issues:
            if not isinstance(item, dict):
                raise PersistenceStateError("persisted reconciliation issue must be an object")
            document_id = item.get("document_id")
            issues.append(
                ReconciliationIssue(
                    code=ReconciliationIssueCode(text(item.get("code"), "issue.code")),
                    message=text(item.get("message"), "issue.message"),
                    document_id=(
                        None if document_id is None else text(document_id, "issue.document_id")
                    ),
                )
            )
        return FiscalReconciliationResult(
            status=ReconciliationStatus(text(row[7], "status")),
            scope=scope,
            source=source,
            fingerprint=text(row[8], "fingerprint"),
            selected_document_id=optional_text(row[9], "selected_document_id"),
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
        row = one_row(
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
