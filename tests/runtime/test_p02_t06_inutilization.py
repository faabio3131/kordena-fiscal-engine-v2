from __future__ import annotations

import importlib.util
import os
from datetime import UTC, datetime
from pathlib import Path

import psycopg
import pytest
from fastapi.testclient import TestClient

from kordena_fiscal.application.service import FiscalApplicationService
from kordena_fiscal.contingency import FiscalOutboxEntry, InMemoryFiscalOutboxStore
from kordena_fiscal.persistence import SqliteFiscalDatabase
from kordena_fiscal.persistence.postgres import PostgresFiscalDatabase
from kordena_fiscal.runtime.fiscal_runtime import (
    CanonicalFiscalOperationPath,
    CanonicalPortalOperationExecutor,
)
from kordena_fiscal.security.human_identity import (
    HumanAccount,
    InMemoryHumanAccountRepository,
    PortalRole,
    ScryptPasswordHasher,
)
from kordena_fiscal.web import create_app
from kordena_fiscal.web.human_auth import CSRF_COOKIE, CSRF_HEADER
from kordena_fiscal.web.portal_runtime import DurableHumanPortalExecutor


def module(name):
    spec = importlib.util.spec_from_file_location(
        name, Path(__file__).parents[1] / "support" / (name + ".py")
    )
    assert spec and spec.loader
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


fixture = module("p02_fiscal_fixture")
receipts = module("p02_inutilization_fixture")
ENDPOINT = "/v1/portal/operations/inutilizeFiscalRange"
BODY = {
    "unit_id": "unit-a",
    "environment": "homologation",
    "model": 55,
    "series": 1,
    "first_number": 10,
    "last_number": 12,
    "justification": "Justificativa sintetica de teste",
}


@pytest.fixture(params=("sqlite", "postgres"))
def database(request, tmp_path):
    if request.param == "postgres":
        dsn = os.environ.get("NFCORE_TEST_POSTGRES_DSN", "")
        if not dsn:
            pytest.skip("real PostgreSQL DSN required; remote CI supplies it")
        with psycopg.connect(dsn, autocommit=True) as connection:
            connection.execute("DROP SCHEMA public CASCADE")
            connection.execute("CREATE SCHEMA public")
        database = PostgresFiscalDatabase(dsn)
    else:
        database = SqliteFiscalDatabase(tmp_path / "t06.sqlite3")
    database.initialize()
    fixture.seed(database)
    yield database
    if isinstance(database, PostgresFiscalDatabase):
        database.close()


def app(database, *, configured=True, response_loss=False):
    accounts = InMemoryHumanAccountRepository()
    identity = fixture.identity(accounts)
    for name, role, platform in (
        ("admin", PortalRole.ADMIN, False),
        ("platform", PortalRole.BILLING, True),
    ):
        accounts.save(
            HumanAccount(
                account_id="synthetic-" + name,
                email=name + "@example.com",
                password_hash=ScryptPasswordHasher().hash(fixture.PASSWORD),
                tenant_id="tenant-a",
                role=role,
                platform_admin=platform,
            )
        )
    handlers = (
        {"inutilizeFiscalRange": receipts.internal_handler(database, response_loss=response_loss)}
        if configured
        else {}
    )
    path = CanonicalFiscalOperationPath(FiscalApplicationService(database), handlers=handlers)
    return create_app(
        human_identity=identity,
        portal_executor=DurableHumanPortalExecutor(
            database,
            operation_executor=CanonicalPortalOperationExecutor(
                unit_of_work_factory=database, path=path
            ),
        ),
    )


def client(database, name="operator", **options):
    http = TestClient(app(database, **options), base_url="https://nfcore.test")
    assert (
        http.post(
            "/v1/auth/login", json={"email": name + "@example.com", "password": fixture.PASSWORD}
        ).status_code
        == 200
    )
    return http


def post(http, body=None, key="synthetic-inutilization"):
    return http.post(
        ENDPOINT,
        json=BODY if body is None else body,
        headers={CSRF_HEADER: http.cookies.get(CSRF_COOKIE) or "", "Idempotency-Key": key},
    )


@pytest.mark.parametrize("role", ("owner", "admin", "operator"))
def test_existing_mutating_roles_reach_canonical_contract_and_durable_outbox(database, role):
    http = client(database, role)
    assert (
        "inutilizations"
        in http.get("/v1/portal/bootstrap").json()["projection"]["available_surfaces"]
    )
    result = post(http)
    assert result.status_code == 200
    assert result.json()["status"] == "internal_outbox_only"
    replay = post(client(database, role))
    assert replay.status_code == 200 and replay.json()["replay"]
    assert post(http, {**BODY, "last_number": 13}).status_code == 409
    with database() as uow:
        entries = uow.outbox.list_for_scope(fixture.scope(), operations=frozenset({"inutilize"}))
        assert len(entries) == 1
        assert entries[0].scope.tenant_id == "tenant-a"
        assert BODY["justification"].encode() in entries[0].payload
    rows = http.get("/v1/portal/surfaces/inutilizations?unit_id=unit-a").json()["rows"]
    assert len(rows) == 1 and rows[0]["status"] == "pending"
    assert rows[0]["fiscal_confirmation"] == "not_inferred_from_outbox"
    assert BODY["justification"] not in str(rows)
    assert "payload" not in str(rows) and "deduplication_key" not in str(rows)


@pytest.mark.parametrize("role", ("auditor", "billing", "platform"))
def test_no_role_or_platform_flag_bypass(database, role):
    http = client(database, role)
    assert post(http).status_code == 403
    assert http.get("/v1/portal/surfaces/inutilizations?unit_id=unit-a").status_code == 403
    assert (
        "inutilizations"
        not in http.get("/v1/portal/bootstrap").json()["projection"]["available_surfaces"]
    )


@pytest.mark.parametrize(
    "change",
    (
        {"model": True},
        {"model": "55"},
        {"model": 99},
        {"series": True},
        {"series": -1},
        {"series": 1000},
        {"first_number": 0},
        {"first_number": "10"},
        {"last_number": 9},
        {"last_number": 12.5},
        {"justification": "curta"},
        {"justification": "x" * 256},
        {"justification": None},
        {"tenant_id": "tenant-b"},
        {"scope": {"tenant_id": "tenant-b"}},
        {"request_id": "browser-id"},
        {"credentials": "synthetic-protected"},
    ),
)
def test_invalid_or_spoofed_contract_does_not_reach_outbox(database, change):
    assert post(client(database), {**BODY, **change}).status_code == 400
    with database() as uow:
        assert not uow.outbox.list_for_scope(fixture.scope(), operations=frozenset({"inutilize"}))


def test_session_csrf_idempotency_scope_and_missing_dependency_fail_closed(database):
    anonymous = TestClient(app(database), base_url="https://nfcore.test")
    assert post(anonymous).status_code == 401
    http = client(database)
    assert http.post(ENDPOINT, json=BODY).status_code == 403
    assert (
        http.post(
            ENDPOINT, json=BODY, headers={CSRF_HEADER: http.cookies.get(CSRF_COOKIE)}
        ).status_code
        == 400
    )
    assert post(http, {**BODY, "unit_id": "unit-b"}).status_code == 403
    assert post(http, {**BODY, "environment": "invalid"}).status_code == 400
    assert post(client(database, "owner"), {**BODY, "unit_id": "unknown"}).status_code == 409
    blocked = post(client(database, configured=False))
    assert (
        blocked.status_code == 503
        and blocked.json()["detail"]["code"] == "FISCAL_RUNTIME_NOT_READY"
    )
    with database() as uow:
        assert not uow.outbox.list_for_scope(fixture.scope(), operations=frozenset({"inutilize"}))


def test_post_commit_response_loss_replays_once_and_normalizes_reason(database):
    http = client(database, response_loss=True)
    body = {**BODY, "model": 65, "justification": "  " + BODY["justification"] + "  "}
    assert post(http, body).status_code == 503
    retry = post(client(database, response_loss=True), body)
    assert retry.status_code == 200 and retry.json()["replay"]
    with database() as uow:
        entries = uow.outbox.list_for_scope(fixture.scope(), operations=frozenset({"inutilize"}))
        assert len(entries) == 1
        assert b'"justification": "Justificativa' in entries[0].payload


def test_operation_filter_precedes_pagination_and_scope_isolation(database):
    now = datetime.now(UTC)
    entries = []
    for label, scope, operation in (
        ("a", fixture.scope(), "inutilize"),
        ("unit", fixture.scope(unit="unit-b"), "inutilize"),
        ("tenant", fixture.scope(tenant="tenant-b"), "inutilize"),
        ("host", fixture.scope(host="other-host"), "inutilize"),
        ("env", fixture.scope(environment=fixture.FiscalEnvironment.PRODUCTION), "inutilize"),
    ):
        entries.append(
            FiscalOutboxEntry(
                entry_id=fixture.digest(label + "-inutilization"),
                scope=scope,
                operation=operation,
                deduplication_key=label,
                payload=fixture.PROTECTED.encode(),
                payload_sha256=fixture.digest(fixture.PROTECTED),
                created_at=now,
                available_at=now,
            )
        )
    memory = InMemoryFiscalOutboxStore()
    with database() as uow:
        for entry in entries:
            uow.outbox.enqueue(entry)
            memory.enqueue(entry)
        for index in range(101):
            entry = FiscalOutboxEntry(
                entry_id=fixture.digest(str(index) + "-unrelated"),
                scope=fixture.scope(),
                operation="issue",
                deduplication_key="unrelated-" + str(index),
                payload=b"synthetic",
                payload_sha256=fixture.digest("synthetic"),
                created_at=now,
                available_at=now,
            )
            uow.outbox.enqueue(entry)
            memory.enqueue(entry)
        uow.commit()
    with database() as uow:
        for store in (memory, uow.outbox):
            assert (
                len(
                    store.list_for_scope(
                        fixture.scope(), limit=1, operations=frozenset({"inutilize"})
                    )
                )
                == 1
            )
            assert not store.list_for_scope(
                fixture.scope(), offset=1, operations=frozenset({"inutilize"})
            )
            assert not store.list_for_scope(fixture.scope(), operations=frozenset())
    response = client(database).get("/v1/portal/surfaces/inutilizations?unit_id=unit-a&limit=1")
    assert response.status_code == 200 and len(response.json()["rows"]) == 1
    assert fixture.PROTECTED not in response.text
    assert all(e.entry_id not in response.text for e in entries[1:])
