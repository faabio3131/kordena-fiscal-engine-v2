from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import psycopg
import pytest
from fastapi.testclient import TestClient

from kordena_fiscal.domain import FiscalEnvironment
from kordena_fiscal.persistence import SqliteFiscalDatabase
from kordena_fiscal.persistence.postgres import PostgresFiscalDatabase
from kordena_fiscal.security.human_identity import (
    HumanAccount,
    InMemoryHumanAccountRepository,
    PortalRole,
    ScryptPasswordHasher,
)
from kordena_fiscal.web import create_app
from kordena_fiscal.web.portal_runtime import DurableHumanPortalExecutor

ROOT = Path(__file__).parents[1]


def load_fixture(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "support" / (name + ".py"))
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fiscal = load_fixture("p02_fiscal_fixture")
configuration = load_fixture("p02_configuration_fixture")
SURFACES = ("certificates", "providers", "webhooks", "integrations", "settings")


@pytest.fixture(params=("sqlite", "postgres"))
def database(request, tmp_path):
    if request.param == "postgres":
        dsn = os.environ.get("NFCORE_TEST_POSTGRES_DSN", "")
        if not dsn:
            pytest.skip("real PostgreSQL DSN required; remote CI supplies it")
        with psycopg.connect(dsn, autocommit=True) as connection:
            connection.execute("DROP SCHEMA public CASCADE")
            connection.execute("CREATE SCHEMA public")
        db = PostgresFiscalDatabase(dsn)
    else:
        db = SqliteFiscalDatabase(tmp_path / "p03.sqlite3")
    db.initialize()
    fiscal.seed(db)
    configuration.seed(db)
    try:
        yield db
    finally:
        if isinstance(db, PostgresFiscalDatabase):
            db.close()


def app(database):
    accounts = InMemoryHumanAccountRepository()
    identity = fiscal.identity(accounts)
    hasher = ScryptPasswordHasher()
    for name, role in (("admin", PortalRole.ADMIN), ("restricted", PortalRole.OWNER)):
        accounts.save(
            HumanAccount(
                account_id="synthetic-" + name, email=name + "@example.com",
                password_hash=hasher.hash(fiscal.PASSWORD), tenant_id="tenant-a",
                role=role, unit_ids=frozenset({"unit-a"}),
            )
        )
    return create_app(human_identity=identity, portal_executor=DurableHumanPortalExecutor(database))


def client(database, name="owner"):
    http = TestClient(app(database), base_url="https://nfcore.test")
    response = http.post(
        "/v1/auth/login", json={"email": name + "@example.com", "password": fiscal.PASSWORD}
    )
    assert response.status_code == 200
    return http


@pytest.mark.parametrize("surface", SURFACES)
def test_configuration_is_persisted_scoped_sanitized_and_not_promoted(database, surface):
    http = client(database)
    response = http.get(
        "/v1/portal/surfaces/" + surface + "?unit_id=unit-a",
        headers={"X-FM-Tenant-Id": "tenant-b"},
    )
    assert response.status_code == 200, response.text
    rows = response.json()["rows"]
    assert rows and all(row["unit_id"] == "unit-a" for row in rows)
    assert all(row["environment"] == "homologation" for row in rows)
    assert all(row["operational_verification"] == "not_confirmed" for row in rows)
    for forbidden in (
        configuration.PROTECTED_QUERY, "callback.example.invalid", "secret_sha256",
        "binding-other", "policy-other", "events-other", "module-other",
        "ref:synthetic-other", "ref:synthetic-prod", "events-prod", "policy-prod",
    ):
        assert forbidden not in response.text
    assert "read_only_pending_security_decision" in response.text
    # New executor/client after HTTP recomposition reads the same persisted configuration.
    restarted = client(database).get("/v1/portal/surfaces/" + surface + "?unit_id=unit-a")
    assert restarted.json() == response.json()


@pytest.mark.parametrize("surface", SURFACES)
def test_existing_roles_and_unit_environment_authority_are_preserved(database, surface):
    endpoint = "/v1/portal/surfaces/" + surface
    anonymous = TestClient(app(database), base_url="https://nfcore.test")
    assert anonymous.get(endpoint).status_code == 401
    for role in ("operator", "auditor", "billing"):
        assert client(database, role).get(endpoint + "?unit_id=unit-a").status_code == 403
    for role in ("admin", "restricted"):
        http = client(database, role)
        assert http.get(endpoint + "?unit_id=unit-a").status_code == 200
        assert http.get(endpoint + "?unit_id=unit-b").status_code == 403
    owner = client(database)
    assert owner.get(endpoint).status_code == 409
    assert owner.get(endpoint + "?unit_id=missing").status_code == 409
    assert owner.get(endpoint + "?unit_id=unit-b").status_code == 200
    assert owner.get(endpoint + "?unit_id=unit-a&environment=production").status_code == 200
    with database() as uow:
        unit = uow.control_plane.get_unit("tenant-a", "unit-a")
    assert unit is not None and FiscalEnvironment.PRODUCTION in unit.enabled_environments
    # This only proves a read of existing production-labelled metadata, not production execution.


def test_pages_are_bounded_and_cannot_change_configuration(database):
    http = client(database)
    endpoint = "/v1/portal/surfaces/certificates?unit_id=unit-a"
    first = http.get(endpoint + "&limit=1&offset=0").json()["rows"]
    second = http.get(endpoint + "&limit=1&offset=1").json()["rows"]
    assert len(first) == len(second) == 1 and first != second
    assert http.get(endpoint + "&limit=101").status_code == 400
    assert http.get(endpoint + "&offset=-1").status_code == 400
    assert http.post("/v1/portal/operations/setWebhookDestination", json={}).status_code == 404
    assert http.post("/v1/portal/surfaces/webhooks", json={}).status_code == 405
    rows = http.get("/v1/portal/surfaces/webhooks?unit_id=unit-a").json()["rows"]
    assert rows[0]["destination_id"] == "events-a"
