"""Canonical durable Bling installation metadata; no tokens and no second tenant authority."""

from __future__ import annotations

import base64
import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from uuid import uuid4

from kordena_fiscal.application.service import FiscalApplicationService
from kordena_fiscal.domain import (
    ExecutionScope,
    FiscalEnvironment,
    FiscalValidationError,
    HostNamespace,
    HostScope,
)
from kordena_fiscal.integrations.bling_contracts import (
    BlingInstallationState,
    BlingInstallationView,
)
from kordena_fiscal.persistence.ports import PersistenceConflictError, PersistenceStateError
from kordena_fiscal.persistence.postgres import PostgresFiscalDatabase
from kordena_fiscal.persistence.sqlite import SqliteFiscalDatabase

Database = PostgresFiscalDatabase | SqliteFiscalDatabase

_FIELDS = (
    "installation_id, company_id, external_tenant_id, external_unit_id, "
    "tenant_id, unit_id, environment, state, revision, created_at, updated_at"
)


class BlingInstallationRepository:
    """All tenant/unit data comes from the existing fiscal binding.

    Access from HTTP MUST have passed canonical session authentication,
    INTEGRATION_MANAGE permission and CSRF on mutations. This repository is
    also used by webhook/worker code, which must independently authenticate.
    """

    def __init__(self, database: Database) -> None:
        self.database = database

    @staticmethod
    def _row(row: tuple[object, ...]) -> BlingInstallationView:
        return BlingInstallationView(
            installation_id=str(row[0]),
            company_id=str(row[1]),
            tenant_id=str(row[4]),
            unit_id=str(row[5]),
            environment=FiscalEnvironment(str(row[6])),
            state=BlingInstallationState(str(row[7])),
            health_code="ready" if row[7] == "connected" else str(row[7]),
            credential_status="configured" if row[7] == "connected" else "unavailable",
            updated_at=datetime.fromisoformat(str(row[10])),
            revision=int(str(row[8])),
        )

    @staticmethod
    def _require_scope(scope: ExecutionScope) -> None:
        if scope.host_namespace != "bling":
            raise FiscalValidationError("Bling host namespace required")

    def create(
        self,
        *,
        host_scope: HostScope,
        company_id: str,
        environment: FiscalEnvironment,
    ) -> BlingInstallationView:
        if host_scope.namespace != HostNamespace("bling"):
            raise FiscalValidationError("Bling host namespace required")
        if not isinstance(company_id, str) or not company_id.strip() or len(company_id) > 96:
            raise FiscalValidationError("Bling company ID is invalid")
        # This is the ONLY tenant/unit resolution authority.
        scope = FiscalApplicationService(self.database).resolve_scope(
            host_scope, environment=environment, correlation_id="bling-installation",
        )
        installation_id = uuid4().hex
        now = datetime.now(UTC).isoformat()
        with self.database.connection() as connection:
            try:
                connection.execute(
                    """INSERT INTO fm_bling_installations (
                        installation_id, company_id, external_tenant_id, external_unit_id,
                        tenant_id, unit_id, environment, state, revision, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        installation_id, company_id,
                        host_scope.tenant_id, host_scope.unit_id, scope.tenant_id,
                        scope.unit_id, environment.value,
                        BlingInstallationState.NOT_CONFIGURED.value, 1, now, now,
                    ),
                )
                connection.commit()
            except (sqlite3.IntegrityError, ValueError) as exc:
                connection.rollback()
                raise PersistenceConflictError("Bling installation already bound") from exc
        found = self.get_for_scope(scope, installation_id)
        if found is None:
            raise PersistenceStateError("created Bling installation unavailable")
        return found

    def get_by_id(self, installation_id: str) -> BlingInstallationView | None:
        if not isinstance(installation_id, str) or len(installation_id) != 32:
            return None
        with self.database.connection() as connection:
            row = connection.execute(
                f"SELECT {_FIELDS} FROM fm_bling_installations WHERE installation_id = ?",
                (installation_id,),
            ).fetchone()
        return None if row is None else self._row(row)

    def get_for_scope(
        self, scope: ExecutionScope, installation_id: str
    ) -> BlingInstallationView | None:
        self._require_scope(scope)
        if not isinstance(installation_id, str) or len(installation_id) != 32:
            return None
        with self.database.connection() as connection:
            row = connection.execute(
                f"SELECT {_FIELDS} FROM fm_bling_installations "
                "WHERE installation_id = ? AND tenant_id = ? AND unit_id = ? "
                "AND environment = ?",
                (installation_id, scope.tenant_id, scope.unit_id, scope.environment.value),
            ).fetchone()
        return None if row is None else self._row(row)

    def host_binding(self, installation_id: str) -> HostScope | None:
        """Resolve external namespace for a cryptographically authenticated webhook."""
        if not isinstance(installation_id, str) or len(installation_id) != 32:
            return None
        with self.database.connection() as connection:
            row = connection.execute(
                "SELECT external_tenant_id, external_unit_id "
                "FROM fm_bling_installations WHERE installation_id = ?",
                (installation_id,),
            ).fetchone()
        if row is None:
            return None
        return HostScope(HostNamespace("bling"), str(row[0]), str(row[1]))

    @staticmethod
    def _decode_cursor(cursor: str | None, scope: ExecutionScope) -> str:
        if cursor is None:
            return ""
        try:
            if len(cursor) > 256:
                raise ValueError
            value = json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))
            checksum = hashlib.sha256(
                json.dumps(scope.identity_material, separators=(",", ":")).encode()
            ).hexdigest()
            if (
                not isinstance(value, dict)
                or set(value) != {"scope", "after"}
                or value["scope"] != checksum
                or not isinstance(value["after"], str)
                or len(value["after"]) != 32
            ):
                raise ValueError
            return value["after"]
        except (ValueError, TypeError, KeyError, UnicodeDecodeError):
            raise FiscalValidationError("invalid Bling pagination cursor") from None

    def list_for_scope(
        self, scope: ExecutionScope, *,
        cursor: str | None = None, limit: int = 50,
    ) -> tuple[tuple[BlingInstallationView, ...], str | None]:
        self._require_scope(scope)
        if type(limit) is not int or not 1 <= limit <= 100:
            raise FiscalValidationError("invalid Bling page size")
        after = self._decode_cursor(cursor, scope)
        with self.database.connection() as connection:
            rows = connection.execute(
                f"SELECT {_FIELDS} FROM fm_bling_installations "
                "WHERE tenant_id = ? AND unit_id = ? AND environment = ? "
                "AND installation_id > ? ORDER BY installation_id LIMIT ?",
                (scope.tenant_id, scope.unit_id, scope.environment.value, after, limit + 1),
            ).fetchall()
        views = tuple(self._row(row) for row in rows[:limit])
        continuation = None
        if len(rows) > limit and views:
            scope_digest = hashlib.sha256(
                json.dumps(scope.identity_material, separators=(",", ":")).encode()
            ).hexdigest()
            cursor_bytes = json.dumps({
                "scope": scope_digest,
                "after": views[-1].installation_id,
            }, separators=(",", ":"), sort_keys=True).encode()
            continuation = base64.urlsafe_b64encode(cursor_bytes).decode().rstrip("=")
        return views, continuation

    def transition(
        self, scope: ExecutionScope, installation_id: str, *,
        expected_revision: int, state: BlingInstallationState,
    ) -> BlingInstallationView:
        self._require_scope(scope)
        if type(expected_revision) is not int or expected_revision < 1:
            raise PersistenceConflictError("Bling installation revision invalid")
        if not isinstance(state, BlingInstallationState):
            raise PersistenceStateError("invalid Bling installation state")
        with self.database.connection() as connection:
            updated = connection.execute(
                "UPDATE fm_bling_installations SET state = ?, revision = revision + 1, "
                "updated_at = ? WHERE installation_id = ? AND tenant_id = ? "
                "AND unit_id = ? AND environment = ? AND revision = ?",
                (state.value, datetime.now(UTC).isoformat(),
                 installation_id, scope.tenant_id, scope.unit_id,
                 scope.environment.value, expected_revision),
            )
            if updated.rowcount != 1:
                connection.rollback()
                raise PersistenceConflictError("Bling installation changed or unavailable")
            connection.commit()
        result = self.get_for_scope(scope, installation_id)
        if result is None:
            raise PersistenceStateError("Bling installation transition not observable")
        return result

    def list_connected_for_worker(
        self, *, after: str = "", limit: int = 100,
    ) -> tuple[tuple[BlingInstallationView, ...], str | None]:
        """Trusted worker-only discovery; each item is re-resolved before claiming."""
        if type(limit) is not int or not 1 <= limit <= 100:
            raise FiscalValidationError("invalid Bling worker page size")
        if after and (len(after) != 32 or any(c not in "0123456789abcdef" for c in after)):
            raise FiscalValidationError("invalid Bling worker pagination cursor")
        with self.database.connection() as connection:
            rows = connection.execute(
                f"SELECT {_FIELDS} FROM fm_bling_installations "
                "WHERE state = 'connected' AND installation_id > ? "
                "ORDER BY installation_id LIMIT ?",
                (after, limit + 1),
            ).fetchall()
        views = tuple(self._row(row) for row in rows[:limit])
        return views, (views[-1].installation_id if len(rows) > limit and views else None)

    def status_mapping_for_scope(
        self, scope: ExecutionScope, installation_id: str,
    ) -> tuple[int, int] | None:
        """Read-only per-installation writeback policy; absent means no dispatch."""
        self._require_scope(scope)
        if len(installation_id) != 32:
            return None
        with self.database.connection() as connection:
            row = connection.execute(
                "SELECT authorized_status_id, rejected_status_id "
                "FROM fm_bling_installations WHERE installation_id = ? "
                "AND tenant_id = ? AND unit_id = ? AND environment = ? "
                "AND state = 'connected'",
                (installation_id, scope.tenant_id, scope.unit_id, scope.environment.value),
            ).fetchone()
        if row is None or row[0] is None or row[1] is None:
            return None
        try:
            authorized, rejected = int(str(row[0])), int(str(row[1]))
        except ValueError:
            raise PersistenceStateError("invalid Bling status mapping") from None
        if authorized <= 0 or rejected <= 0 or authorized == rejected:
            raise PersistenceStateError("invalid Bling status mapping")
        return authorized, rejected

    def configure_status_mapping(
        self, scope: ExecutionScope, installation_id: str, *,
        authorized_status_id: int, rejected_status_id: int,
        expected_revision: int,
    ) -> BlingInstallationView:
        self._require_scope(scope)
        if (
            type(authorized_status_id) is not int or type(rejected_status_id) is not int
            or min(authorized_status_id, rejected_status_id) <= 0
            or authorized_status_id == rejected_status_id
        ):
            raise FiscalValidationError("invalid Bling status policy")
        if type(expected_revision) is not int or expected_revision < 1:
            raise PersistenceConflictError("invalid Bling policy revision")
        with self.database.connection() as connection:
            updated = connection.execute(
                "UPDATE fm_bling_installations SET authorized_status_id = ?, "
                "rejected_status_id = ?, revision = revision + 1, updated_at = ? "
                "WHERE installation_id = ? AND tenant_id = ? AND unit_id = ? "
                "AND environment = ? AND revision = ?",
                (
                    authorized_status_id, rejected_status_id,
                    datetime.now(UTC).isoformat(), installation_id, scope.tenant_id,
                    scope.unit_id, scope.environment.value, expected_revision,
                ),
            )
            if updated.rowcount != 1:
                connection.rollback()
                raise PersistenceConflictError("Bling installation status policy conflict")
            connection.commit()
        view = self.get_for_scope(scope, installation_id)
        if view is None:
            raise PersistenceStateError("Bling status policy update unavailable")
        return view
