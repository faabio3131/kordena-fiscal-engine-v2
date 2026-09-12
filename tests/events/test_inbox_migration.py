from __future__ import annotations

import sqlite3

from kordena_fiscal.persistence import SqliteFiscalDatabase


def test_v2_07_database_upgrades_to_durable_inbox_without_reapplying_v1(tmp_path) -> None:
    database = SqliteFiscalDatabase(tmp_path / "fm-fiscal-upgrade.sqlite3")
    assert database.initialize() == (1, 2)

    # Reconstruct the exact migration-ledger state of a certified V2-07 database:
    # migration 1 is preserved, while the V2-08 inbox migration is absent.
    with sqlite3.connect(database.path) as connection:
        connection.execute("DROP INDEX fm_fiscal_inbox_status_idx")
        connection.execute("DROP TABLE fm_fiscal_inbox")
        connection.execute("DELETE FROM fm_schema_migrations WHERE version = 2")
        connection.commit()

    assert database.applied_migrations() == (1,)
    assert database.initialize() == (2,)
    assert database.applied_migrations() == (1, 2)

    with sqlite3.connect(database.path) as connection:
        row = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'fm_fiscal_inbox'"
        ).fetchone()
    assert row == ("fm_fiscal_inbox",)
