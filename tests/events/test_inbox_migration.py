from __future__ import annotations

import sqlite3

from kordena_fiscal.persistence import SqliteFiscalDatabase


def _remove_v3(connection: sqlite3.Connection) -> None:
    connection.execute("DROP INDEX fm_fiscal_delivery_attempts_status_idx")
    connection.execute("DROP TABLE fm_fiscal_delivery_attempts")
    connection.execute("DROP INDEX fm_fiscal_outbox_ordering_key_idx")
    connection.execute("DROP TABLE fm_fiscal_outbox_ordering")
    connection.execute("DELETE FROM fm_schema_migrations WHERE version = 3")


def test_v2_07_database_upgrades_through_inbox_and_delivery_audit_without_reapplying_v1(
    tmp_path,
) -> None:
    database = SqliteFiscalDatabase(tmp_path / "fm-fiscal-upgrade.sqlite3")
    assert database.initialize() == (1, 2, 3)

    # Reconstruct the exact migration-ledger state of a certified V2-07 database:
    # migration 1 remains; V2-08 inbox and delivery-audit migrations are absent.
    with sqlite3.connect(database.path) as connection:
        _remove_v3(connection)
        connection.execute("DROP INDEX fm_fiscal_inbox_status_idx")
        connection.execute("DROP TABLE fm_fiscal_inbox")
        connection.execute("DELETE FROM fm_schema_migrations WHERE version = 2")
        connection.commit()

    assert database.applied_migrations() == (1,)
    assert database.initialize() == (2, 3)
    assert database.applied_migrations() == (1, 2, 3)

    with sqlite3.connect(database.path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
    assert "fm_fiscal_inbox" in tables
    assert "fm_fiscal_outbox_ordering" in tables
    assert "fm_fiscal_delivery_attempts" in tables


def test_v2_08_inbox_checkpoint_upgrades_only_delivery_audit_and_ordering_v3(tmp_path) -> None:
    database = SqliteFiscalDatabase(tmp_path / "fm-fiscal-v2-08-upgrade.sqlite3")
    assert database.initialize() == (1, 2, 3)

    with sqlite3.connect(database.path) as connection:
        _remove_v3(connection)
        connection.commit()

    assert database.applied_migrations() == (1, 2)
    assert database.initialize() == (3,)
    assert database.applied_migrations() == (1, 2, 3)

    with sqlite3.connect(database.path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
    assert "fm_fiscal_inbox" in tables
    assert "fm_fiscal_outbox_ordering" in tables
    assert "fm_fiscal_delivery_attempts" in tables
