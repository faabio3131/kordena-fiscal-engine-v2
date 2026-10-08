from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import psycopg
import pytest
from fastapi.testclient import TestClient

from kordena_fiscal.persistence import SqliteFiscalDatabase
from kordena_fiscal.persistence.postgres import PostgresFiscalDatabase

spec = importlib.util.spec_from_file_location(
    "t07_fixture", Path(__file__).parents[1] / "support/p02_fiscal_fixture.py"
)
assert spec and spec.loader
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)


@pytest.fixture(params=("sqlite", "postgres"))
def database(request, tmp_path):
    if request.param == "postgres":
        dsn = os.environ.get("NFCORE_TEST_POSTGRES_DSN", "")
        if not dsn:
            pytest.skip("real PostgreSQL DSN required; remote CI supplies it")
        with psycopg.connect(dsn, autocommit=True) as connection:
            connection.execute("DROP SCHEMA public CASCADE")
            connection.execute("CREATE SCHEMA public")
        result = PostgresFiscalDatabase(dsn)
    else:
        result = SqliteFiscalDatabase(tmp_path / "t07.sqlite3")
    result.initialize()
    fixture.seed(result)
    yield result
    if isinstance(result, PostgresFiscalDatabase):
        result.close()


def client(database, account="owner"):
    http = TestClient(fixture.app(database), base_url="https://nfcore.test")
    assert (
        http.post(
            "/v1/auth/login", json={"email": account + "@example.com", "password": fixture.PASSWORD}
        ).status_code
        == 200
    )
    return http


@pytest.mark.parametrize("account", ("owner", "operator", "auditor", "billing", "other"))
def test_support_reads_only_existing_authorized_configuration_without_sla_or_health_claim(
    database, account
):
    http = client(database, account)
    assert "support" in http.get("/v1/portal/bootstrap").json()["projection"]["available_surfaces"]
    response = http.get("/v1/portal/surfaces/support")
    assert response.status_code == 200
    rows = response.json()["rows"]
    assert len(rows) == (4 if account == "owner" else 2)
    assert {row["unit_id"] for row in rows} == (
        {"unit-a", "unit-b"} if account == "owner" else {"unit-a"}
    )
    for row in rows:
        assert row["status"] == "operational_evidence_required"
        assert row["support_delivery"] == "not_configured"
        assert row["production"] == "not_authorized_by_portal"
        assert row["fiscal_executor"] == row["capability_authority"] == "unavailable"
        assert set(row) == {
            "unit_id",
            "environment",
            "record_type",
            "status",
            "fiscal_executor",
            "capability_authority",
            "support_delivery",
            "production",
        }
    assert "payload" not in response.text and fixture.PROTECTED not in response.text
    assert "tenant-b" not in response.text and "secret" not in response.text


def test_support_filter_pagination_scope_and_absent_session_fail_closed(database):
    http = client(database)
    rows = http.get("/v1/portal/surfaces/support?unit_id=unit-b&environment=production").json()[
        "rows"
    ]
    assert (
        len(rows) == 1 and rows[0]["unit_id"] == "unit-b" and rows[0]["environment"] == "production"
    )
    assert len(http.get("/v1/portal/surfaces/support?limit=1&offset=1").json()["rows"]) == 1
    assert http.get("/v1/portal/surfaces/support?offset=100").json()["rows"] == []
    assert (
        client(database, "operator").get("/v1/portal/surfaces/support?unit_id=unit-b").status_code
        == 403
    )
    assert http.get("/v1/portal/surfaces/support?unit_id=missing").status_code == 409
    anonymous = TestClient(fixture.app(database), base_url="https://nfcore.test")
    assert anonymous.get("/v1/portal/surfaces/support").status_code == 401
