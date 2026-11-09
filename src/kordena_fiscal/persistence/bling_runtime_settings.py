"""Versioned, scope-checked Bling installation runtime settings (migration 21).

Only status mapping and approved fiscal-policy digest live here. Tax rules and
credentials remain under their existing authorities. All writes use CAS.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime

from kordena_fiscal.domain import ExecutionScope, FiscalValidationError
from kordena_fiscal.persistence.bling_installations import (
    BlingInstallationRepository,
    Database,
)
from kordena_fiscal.persistence.ports import PersistenceConflictError


@dataclass(frozen=True, slots=True)
class BlingRuntimeSettings:
    installation_id: str
    authorized_status_id: int | None
    rejected_status_id: int | None
    fiscal_policy_sha256: str | None
    revision: int

    def __post_init__(self) -> None:
        a, r = self.authorized_status_id, self.rejected_status_id
        if (a is None) != (r is None):
            raise FiscalValidationError("Bling status mapping must be complete")
        if a is not None and (
            type(a) is not int or type(r) is not int or a <= 0 or r <= 0 or a == r
        ):
            raise FiscalValidationError("Bling status mapping invalid")
        if self.fiscal_policy_sha256 is not None and not re.fullmatch(
            "[0-9a-f]{64}", self.fiscal_policy_sha256,
        ):
            raise FiscalValidationError("Bling policy pin invalid")
        if self.revision < 1:
            raise FiscalValidationError("Bling configuration revision invalid")


class BlingRuntimeSettingsRepository:
    def __init__(self, database: Database, installations: BlingInstallationRepository) -> None:
        self.database = database
        self.installations = installations

    def get(
        self, scope: ExecutionScope, installation_id: str,
    ) -> BlingRuntimeSettings | None:
        if self.installations.get_for_scope(scope, installation_id) is None:
            return None
        with self.database.connection() as connection:
            row = connection.execute(
                "SELECT authorized_status_id, rejected_status_id, "
                "fiscal_policy_sha256, revision "
                "FROM fm_bling_installation_runtime WHERE installation_id = ?",
                (installation_id,),
            ).fetchone()
        if row is None:
            return None
        return BlingRuntimeSettings(
            installation_id=installation_id,
            authorized_status_id=None if row[0] is None else int(str(row[0])),
            rejected_status_id=None if row[1] is None else int(str(row[1])),
            fiscal_policy_sha256=None if row[2] is None else str(row[2]),
            revision=int(str(row[3])),
        )

    def put(
        self, scope: ExecutionScope, installation_id: str, *,
        expected_revision: int, authorized_status_id: int | None,
        rejected_status_id: int | None, fiscal_policy_sha256: str | None,
    ) -> BlingRuntimeSettings:
        if self.installations.get_for_scope(scope, installation_id) is None:
            raise PersistenceConflictError("Bling installation not authorized")
        if type(expected_revision) is not int or expected_revision < 0:
            raise FiscalValidationError("Bling expected revision invalid")
        expected = BlingRuntimeSettings(
            installation_id=installation_id,
            authorized_status_id=authorized_status_id,
            rejected_status_id=rejected_status_id,
            fiscal_policy_sha256=fiscal_policy_sha256,
            revision=expected_revision + 1,
        )
        now = datetime.now(UTC).isoformat()
        with self.database.connection() as connection:
            try:
                if expected_revision == 0:
                    changed = connection.execute(
                        "INSERT INTO fm_bling_installation_runtime "
                        "(installation_id, authorized_status_id, rejected_status_id, "
                        "fiscal_policy_sha256, revision, updated_at) "
                        "VALUES (?, ?, ?, ?, 1, ?) ON CONFLICT (installation_id) DO NOTHING",
                        (
                            installation_id, expected.authorized_status_id,
                            expected.rejected_status_id, expected.fiscal_policy_sha256,
                            now,
                        ),
                    )
                else:
                    changed = connection.execute(
                        "UPDATE fm_bling_installation_runtime SET "
                        "authorized_status_id = ?, rejected_status_id = ?, "
                        "fiscal_policy_sha256 = ?, revision = revision + 1, updated_at = ? "
                        "WHERE installation_id = ? AND revision = ?",
                        (
                            expected.authorized_status_id, expected.rejected_status_id,
                            expected.fiscal_policy_sha256, now, installation_id,
                            expected_revision,
                        ),
                    )
                if changed.rowcount != 1:
                    connection.rollback()
                    raise PersistenceConflictError("Bling runtime configuration changed")
                connection.commit()
            except PersistenceConflictError:
                raise
            except Exception:
                connection.rollback()
                raise PersistenceConflictError("Bling runtime configuration unavailable") from None
        result = self.get(scope, installation_id)
        if result is None:
            raise PersistenceConflictError("Bling configuration could not be read")
        return result
