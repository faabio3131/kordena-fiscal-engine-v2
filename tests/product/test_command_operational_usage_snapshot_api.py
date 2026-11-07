from __future__ import annotations

import json
from datetime import UTC, datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient

from kordena_fiscal.product.command_commercial_snapshot_api import (
    CommandCommercialSnapshotReader,
)
from kordena_fiscal.product.command_operational_usage_snapshot_api import (
    TOKEN_ENV,
    CommandOperationalUsageSnapshotReader,
    create_command_operational_usage_snapshot_router,
)

TOKEN = "u" * 40


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


def _seeded_reader() -> CommandOperationalUsageSnapshotReader:
    table_rows = {
        "purchases": [],
        "subscriptions": [
            (
                "sub-1", "tenant-a", "starter", "active", "2026-11-01", "2026-12-01",
                json.dumps(["ent-docs"]),
                json.dumps({"documents": 300, "ai_requests": 500}),
                json.dumps({"documents": 42}),
            ),
            (
                "sub-2", "tenant-b", "trial", "trial", "2026-11-01", "2026-11-15",
                json.dumps(["ent-trial"]), json.dumps({}), json.dumps({}),
            ),
        ],
    }
    commercial = CommandCommercialSnapshotReader(_FakeAcquire(table_rows))  # type: ignore[arg-type]
    return CommandOperationalUsageSnapshotReader(commercial)


def command_client(reader: CommandOperationalUsageSnapshotReader | None, **env: str) -> TestClient:
    app = FastAPI()
    app.include_router(
        create_command_operational_usage_snapshot_router(
            reader, env, clock=lambda: datetime(2026, 11, 6, tzinfo=UTC)
        )
    )
    return TestClient(app)


def auth(token: str = TOKEN, correlation: str | None = "corr-usage-1") -> dict[str, str]:
    headers = {"Authorization": f"Bearer {token}"}
    if correlation:
        headers["X-Correlation-Id"] = correlation
    return headers


def test_snapshot_reports_configured_quota_with_measured_usage() -> None:
    client = command_client(_seeded_reader(), **{TOKEN_ENV: TOKEN})
    response = client.get("/v1/command/operational-usage/snapshot", headers=auth())
    assert response.status_code == 200
    assert response.headers["cache-control"].startswith("no-store")
    body = response.json()
    assert body["schema_version"] == "nfcore.fmcc.operational-usage.v1"
    assert body["product_code"] == "NFCORE"
    assert body["correlationId"] == "corr-usage-1"
    assert len(body["consumption"]) == 1
    row = body["consumption"][0]
    assert row["subscription_id"] == "sub-1"
    assert row["tenant_id"] == "tenant-a"
    metrics = {m["metric_id"]: m for m in row["metrics"]}
    assert metrics["documents"]["limit"] == 300
    assert metrics["documents"]["used"] == 42
    assert metrics["documents"]["unavailable"] is False


def test_metric_without_measured_usage_is_unavailable_not_zero() -> None:
    client = command_client(_seeded_reader(), **{TOKEN_ENV: TOKEN})
    response = client.get("/v1/command/operational-usage/snapshot", headers=auth())
    body = response.json()
    metrics = {m["metric_id"]: m for m in body["consumption"][0]["metrics"]}
    assert metrics["ai_requests"]["limit"] == 500
    assert metrics["ai_requests"]["used"] is None
    assert metrics["ai_requests"]["unavailable"] is True


def test_subscription_without_configured_quota_is_omitted() -> None:
    client = command_client(_seeded_reader(), **{TOKEN_ENV: TOKEN})
    response = client.get("/v1/command/operational-usage/snapshot", headers=auth())
    body = response.json()
    ids = [row["subscription_id"] for row in body["consumption"]]
    assert "sub-2" not in ids


def test_summary_counts_subscriptions_and_unavailable_metrics() -> None:
    client = command_client(_seeded_reader(), **{TOKEN_ENV: TOKEN})
    response = client.get("/v1/command/operational-usage/snapshot", headers=auth())
    body = response.json()
    assert body["summary"] == {
        "subscriptions_with_quotas": 1,
        "metrics_reported": 2,
        "metrics_unavailable": 1,
    }


def test_envelope_never_carries_an_amount_or_financial_authority() -> None:
    client = command_client(_seeded_reader(), **{TOKEN_ENV: TOKEN})
    response = client.get("/v1/command/operational-usage/snapshot", headers=auth())
    dumped = json.dumps(response.json())
    assert "amount" not in dumped
    assert "price_brl" not in dumped
    assert "mrr" not in dumped.lower()
    assert TOKEN not in dumped


def test_fact_payload_is_deterministic_hash_of_summary_only() -> None:
    client = command_client(_seeded_reader(), **{TOKEN_ENV: TOKEN})
    response = client.get("/v1/command/operational-usage/snapshot", headers=auth())
    body = response.json()
    facts = body["facts"]
    assert len(facts) == 1
    fact = facts[0]
    assert fact["external_id"].startswith("nfcore-operational-usage-v1:")
    assert fact["fact_type"] == "nfcore.operational_usage.snapshot"
    assert fact["payload"] == {"as_of": body["as_of"], **body["summary"]}
    assert fact["source_timestamp"] == body["as_of"]


def test_unconfigured_reader_fails_closed_with_503() -> None:
    client = command_client(None, **{TOKEN_ENV: TOKEN})
    response = client.get("/v1/command/operational-usage/snapshot", headers=auth())
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "COMMAND_OPERATIONAL_USAGE_NOT_CONFIGURED"


def test_missing_token_configuration_fails_closed_with_503() -> None:
    client = command_client(_seeded_reader())
    response = client.get("/v1/command/operational-usage/snapshot", headers=auth())
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "COMMAND_CONTROL_PLANE_NOT_CONFIGURED"


def test_wrong_token_is_rejected() -> None:
    client = command_client(_seeded_reader(), **{TOKEN_ENV: TOKEN})
    response = client.get(
        "/v1/command/operational-usage/snapshot", headers=auth(token="wrong" * 10)
    )
    assert response.status_code == 401


def test_missing_correlation_id_is_rejected() -> None:
    client = command_client(_seeded_reader(), **{TOKEN_ENV: TOKEN})
    response = client.get(
        "/v1/command/operational-usage/snapshot", headers=auth(correlation=None)
    )
    assert response.status_code == 400
