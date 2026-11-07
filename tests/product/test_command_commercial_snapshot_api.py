from __future__ import annotations

import json
from datetime import UTC, datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient

from kordena_fiscal.product.command_commercial_snapshot_api import (
    TOKEN_ENV,
    CommandCommercialSnapshotReader,
    create_command_commercial_snapshot_router,
)

TOKEN = "t" * 40


class _FakeCursor:
    def __init__(self, rows: list[tuple[object, ...]]) -> None:
        self._rows = rows

    def fetchall(self) -> list[tuple[object, ...]]:
        return self._rows


class _FakeConnection:
    def __init__(self, table_rows: dict[str, list[tuple[object, ...]]]) -> None:
        self._table_rows = table_rows

    def execute(self, sql: str, params: tuple[object, ...] = ()) -> _FakeCursor:
        if "SET LOCAL" in sql:
            return _FakeCursor([])
        if "fm_commercial_purchases" in sql:
            return _FakeCursor(self._table_rows.get("purchases", []))
        if "fm_commercial_subscriptions" in sql:
            rows = self._table_rows.get("subscriptions", [])
            if "WHERE status" in sql:
                status = params[0]
                rows = [r for r in rows if r[3] == status]
            return _FakeCursor(rows)
        raise AssertionError(f"unexpected query: {sql}")


class _FakeAcquire:
    def __init__(self, table_rows: dict[str, list[tuple[object, ...]]]) -> None:
        self._connection = _FakeConnection(table_rows)

    def __call__(self):  # type: ignore[no-untyped-def]
        return self

    def __enter__(self):  # type: ignore[no-untyped-def]
        return self._connection

    def __exit__(self, *exc: object) -> None:
        return None


def _seeded_reader(*, limit: int = 50) -> CommandCommercialSnapshotReader:
    table_rows = {
        "purchases": [
            ("purchase-1", "cakto", "active", "evt-1", "2026-11-01T00:00:00Z", "tenant-a"),
        ],
        "subscriptions": [
            (
                "sub-1", "tenant-a", "starter", "active", "2026-11-01", "2026-12-01",
                json.dumps(["ent-docs"]), json.dumps({"documents": 300}), json.dumps({}),
            ),
            (
                "sub-2", "tenant-b", "trial", "trial", "2026-11-01", "2026-11-15",
                json.dumps(["ent-trial"]), json.dumps({"documents": 50}), json.dumps({}),
            ),
        ],
    }
    return CommandCommercialSnapshotReader(_FakeAcquire(table_rows), limit=limit)  # type: ignore[arg-type]


def command_client(reader: CommandCommercialSnapshotReader | None, **env: str) -> TestClient:
    app = FastAPI()
    app.include_router(
        create_command_commercial_snapshot_router(
            reader, env, clock=lambda: datetime(2026, 11, 6, tzinfo=UTC)
        )
    )
    return TestClient(app)


def auth(token: str = TOKEN, correlation: str | None = "corr-9") -> dict[str, str]:
    headers = {"Authorization": f"Bearer {token}"}
    if correlation:
        headers["X-Correlation-Id"] = correlation
    return headers


def test_snapshot_envelope_reports_real_rows_and_never_an_amount() -> None:
    client = command_client(_seeded_reader(), **{TOKEN_ENV: TOKEN})
    response = client.get("/v1/command/commercial/snapshot", headers=auth())
    assert response.status_code == 200
    assert response.headers["cache-control"].startswith("no-store")
    body = response.json()
    assert body["schema_version"] == "nfcore.fmcc.commercial.v1"
    assert body["product_code"] == "NFCORE"
    assert body["correlationId"] == "corr-9"
    assert len(body["subscriptions"]) == 2
    assert len(body["trials"]) == 1
    assert body["trials"][0]["tenant_id"] == "tenant-b"
    assert len(body["billing_transactions"]) == 1
    # Never a financial authority: no amount/price field anywhere in the envelope.
    dumped = json.dumps(body)
    assert "amount" not in dumped and "price_brl" not in dumped and "mrr" not in dumped.lower()
    assert TOKEN not in dumped
    # Generic Command-side coverage projection (shared with Kordena/Iron) needs
    # these three fields: a single reportable fact, a coverage disclosure that
    # never claims NFCore is the billing authority, and a status-derived summary.
    assert body["coverage"] == {"billing_transactions": "FM_COMMAND_AUTHORITY"}
    assert body["summary"]["customers"] == 1
    assert body["summary"]["active_subscriptions"] == 1
    assert body["summary"]["trial_subscriptions"] == 1
    assert body["summary"]["grace_subscriptions"] == 0
    assert body["summary"]["suspended_subscriptions"] == 0
    assert body["summary"]["canceled_subscriptions"] == 0
    assert len(body["facts"]) == 1
    fact = body["facts"][0]
    assert fact["external_id"].startswith("nfcore-commercial-v1:")
    assert fact["fact_type"] == "nfcore.commercial.snapshot"
    assert fact["source_timestamp"] == body["as_of"]
    assert fact["payload"]["active_subscriptions"] == 1


def test_snapshot_security_matches_the_already_proven_command_pattern() -> None:
    client = command_client(_seeded_reader(), **{TOKEN_ENV: TOKEN})
    assert client.get(
        "/v1/command/commercial/snapshot", headers=auth("x" * 40)
    ).status_code == 401
    assert client.get("/v1/command/commercial/snapshot").status_code == 401
    missing_correlation = client.get(
        "/v1/command/commercial/snapshot", headers=auth(correlation=None)
    )
    assert missing_correlation.status_code == 400


def test_snapshot_fails_closed_without_a_strong_token() -> None:
    for env in ({}, {TOKEN_ENV: "short"}):
        client = command_client(_seeded_reader(), **env)
        response = client.get(
            "/v1/command/commercial/snapshot", headers=auth("short")
        )
        assert response.status_code == 503


def test_snapshot_fails_closed_with_clear_code_when_reader_is_unavailable() -> None:
    """No PostgreSQL composition: never a 404, a clear 503 instead."""
    client = command_client(None, **{TOKEN_ENV: TOKEN})
    response = client.get("/v1/command/commercial/snapshot", headers=auth())
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "COMMAND_COMMERCIAL_NOT_CONFIGURED"


def test_reader_rejects_an_out_of_range_row_budget() -> None:
    import pytest

    with pytest.raises(ValueError):
        _seeded_reader(limit=0)
    with pytest.raises(ValueError):
        _seeded_reader(limit=201)
