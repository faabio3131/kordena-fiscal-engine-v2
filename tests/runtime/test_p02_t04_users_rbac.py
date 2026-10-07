from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

import psycopg
import pytest
from fastapi.testclient import TestClient

from kordena_fiscal.control_plane.models import (
    ControlPlaneAuditAction,
    ControlPlaneAuditEvent,
    FiscalOrganization,
    FiscalUnitRegistration,
)
from kordena_fiscal.domain import FiscalEnvironment
from kordena_fiscal.persistence import SqliteFiscalDatabase
from kordena_fiscal.persistence.postgres import PostgresFiscalDatabase
from kordena_fiscal.runtime.composition import build_postgres_runtime_composition
from kordena_fiscal.security.human_administration import (
    HumanAdministrationService,
    InMemoryHumanAdministrationStore,
)
from kordena_fiscal.security.human_identity import (
    HumanAccount,
    HumanIdentityService,
    InMemoryWebSessionRepository,
    PortalRole,
    ScryptPasswordHasher,
)
from kordena_fiscal.web import create_app
from kordena_fiscal.web.human_auth import CSRF_COOKIE, CSRF_HEADER
from kordena_fiscal.web.portal_runtime import DurableHumanPortalExecutor

PASSWORD = "correct-horse-nfcore-2026"
NOW = datetime(2026, 10, 7, 15, 30, tzinfo=UTC)


def human(
    name: str,
    role: PortalRole,
    hasher: ScryptPasswordHasher,
    *,
    tenant: str = "tenant-a",
    units: frozenset[str] | None = None,
    platform_admin: bool = False,
) -> HumanAccount:
    return HumanAccount(
        account_id="account-" + name,
        email=name + "@example.com",
        password_hash=hasher.hash(PASSWORD),
        tenant_id=tenant,
        role=role,
        unit_ids=units,
        platform_admin=platform_admin,
    )


@pytest.fixture
def runtime(tmp_path):
    database = SqliteFiscalDatabase(tmp_path / "t04.sqlite3")
    database.initialize()
    with database() as uow:
        uow.control_plane.add_organization(
            FiscalOrganization(tenant_id="tenant-a", legal_name="Synthetic Tenant A")
        )
        for index, unit_id in enumerate(("unit-a", "unit-b")):
            uow.control_plane.add_unit(
                FiscalUnitRegistration(
                    tenant_id="tenant-a",
                    unit_id=unit_id,
                    display_name="Synthetic " + unit_id,
                    enabled_environments=frozenset({FiscalEnvironment.HOMOLOGATION}),
                )
            )
            uow.control_plane.append_audit(
                ControlPlaneAuditEvent(
                    event_id="unit-audit-" + str(index),
                    occurred_at=NOW,
                    actor_id="synthetic-bootstrap",
                    action=ControlPlaneAuditAction.UNIT_ONBOARDED,
                    target_type="unit",
                    target_id=unit_id,
                    correlation_id="bootstrap-" + unit_id,
                    tenant_id="tenant-a",
                    unit_id=unit_id,
                )
            )
        uow.commit()

    hasher = ScryptPasswordHasher()
    accounts = (
        human("owner", PortalRole.OWNER, hasher),
        human("admin", PortalRole.ADMIN, hasher, units=frozenset({"unit-a"})),
        human("operator", PortalRole.OPERATOR, hasher, units=frozenset({"unit-a"})),
        human("auditor", PortalRole.AUDITOR, hasher, units=frozenset({"unit-a"})),
        human("billing", PortalRole.BILLING, hasher, units=frozenset({"unit-a"})),
        human("platform", PortalRole.OWNER, hasher, platform_admin=True),
        human(
            "foreign",
            PortalRole.OPERATOR,
            hasher,
            tenant="tenant-b",
            units=frozenset({"unit-a"}),
        ),
    )
    store = InMemoryHumanAdministrationStore(accounts)
    sessions = InMemoryWebSessionRepository()
    identity = HumanIdentityService(
        accounts=store,
        sessions=sessions,
        password_hasher=hasher,
        session_ttl=timedelta(hours=8),
    )
    users = HumanAdministrationService(store=store, password_hasher=hasher)
    portal = DurableHumanPortalExecutor(database, user_administration=users)
    app = create_app(human_identity=identity, portal_executor=portal)
    return app, store


def client(runtime, name: str) -> TestClient:
    app, _store = runtime
    http = TestClient(app, base_url="https://nfcore.test")
    login = http.post(
        "/v1/auth/login",
        json={"email": name + "@example.com", "password": PASSWORD},
    )
    assert login.status_code == 200, login.text
    return http


def mutate(http: TestClient, operation: str, payload: dict, key: str = "user-command"):
    return http.post(
        "/v1/portal/operations/" + operation,
        json=payload,
        headers={
            CSRF_HEADER: http.cookies.get(CSRF_COOKIE),
            "Idempotency-Key": key,
        },
    )


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("owner", 200),
        ("admin", 200),
        ("operator", 403),
        ("auditor", 403),
        ("billing", 403),
        ("platform", 200),
    ],
)
def test_users_surface_enforces_existing_role_permissions(runtime, name, expected):
    response = client(runtime, name).get("/v1/portal/surfaces/users")
    assert response.status_code == expected


@pytest.mark.parametrize(
    ("name", "visible"),
    [
        ("owner", True),
        ("admin", True),
        ("operator", False),
        ("auditor", False),
        ("billing", False),
    ],
)
def test_bootstrap_navigation_is_filtered_by_backend_permission(runtime, name, visible):
    bootstrap = client(runtime, name).get("/v1/portal/bootstrap")
    assert bootstrap.status_code == 200
    surfaces = set(bootstrap.json()["projection"]["available_surfaces"])
    assert ("users" in surfaces) is visible


def test_restricted_admin_only_sees_and_grants_authority_it_already_holds(runtime):
    admin = client(runtime, "admin")
    rows = admin.get("/v1/portal/surfaces/users").json()["rows"]
    emails = {row["email"] for row in rows}
    assert emails == {
        "admin@example.com",
        "operator@example.com",
        "auditor@example.com",
        "billing@example.com",
    }

    denied_owner = mutate(
        admin,
        "createUser",
        {
            "email": "new-owner@example.com",
            "target_role": "owner",
            "target_unit_ids": ["unit-a"],
        },
        "deny-owner",
    )
    assert denied_owner.status_code == 403

    denied_admin = mutate(
        admin,
        "createUser",
        {
            "email": "new-admin@example.com",
            "target_role": "admin",
            "target_unit_ids": ["unit-a"],
        },
        "deny-admin",
    )
    assert denied_admin.status_code == 403

    denied_scope = mutate(
        admin,
        "createUser",
        {
            "email": "new-other-unit@example.com",
            "target_role": "operator",
            "target_unit_ids": ["unit-b"],
        },
        "deny-unit-b",
    )
    assert denied_scope.status_code == 403

    for allowed_role in ("operator", "auditor", "billing"):
        allowed = mutate(
            admin,
            "createUser",
            {
                "email": f"new-{allowed_role}@example.com",
                "target_role": allowed_role,
                "target_unit_ids": ["unit-a"],
            },
            "allow-" + allowed_role,
        )
        assert allowed.status_code == 200, allowed.text
        assert allowed.json()["role"] == allowed_role
        assert allowed.json()["platform_admin"] is False


def test_owner_create_is_replay_safe_and_browser_cannot_grant_platform_admin(runtime):
    owner = client(runtime, "owner")
    payload = {
        "email": "new-billing@example.com",
        "target_role": "billing",
        "target_unit_ids": None,
    }
    first = mutate(owner, "createUser", payload, "create-billing")
    assert first.status_code == 200, first.text
    assert first.json()["created"] is True
    assert first.json()["activation"] == "password_recovery"
    assert "password_hash" not in first.text.lower()
    assert "reset_token" not in first.text.lower()

    replay = mutate(owner, "createUser", payload, "create-billing")
    assert replay.status_code == 200
    assert replay.json()["replay"] is True
    assert replay.json()["account_id"] == first.json()["account_id"]

    spoof = mutate(
        owner,
        "createUser",
        {
            **payload,
            "email": "spoof@example.com",
            "platform_admin": True,
        },
        "spoof-platform",
    )
    assert spoof.status_code == 400
    assert spoof.json()["detail"]["code"] == "BROWSER_AUTHORITY_REJECTED"


def test_platform_account_and_self_are_not_mutable_by_tenant_user_admin(runtime):
    owner = client(runtime, "owner")
    rows = owner.get("/v1/portal/surfaces/users").json()["rows"]
    by_email = {row["email"]: row for row in rows}
    assert by_email["platform@example.com"]["platform_admin"] is True
    assert by_email["platform@example.com"]["mutable"] is False
    assert by_email["owner@example.com"]["mutable"] is False

    platform = by_email["platform@example.com"]
    denied = mutate(
        owner,
        "updateUser",
        {
            "target_account_id": platform["account_id"],
            "expected_version": platform["version"],
            "target_role": "operator",
            "target_unit_ids": ["unit-a"],
            "enabled": True,
        },
        "tenant-cannot-touch-platform",
    )
    assert denied.status_code == 403


def test_role_scope_change_revokes_existing_session_and_is_versioned(runtime):
    target_session = client(runtime, "operator")
    assert target_session.get("/v1/portal/bootstrap").status_code == 200

    owner = client(runtime, "owner")
    target = next(
        row
        for row in owner.get("/v1/portal/surfaces/users").json()["rows"]
        if row["email"] == "operator@example.com"
    )
    changed = mutate(
        owner,
        "updateUser",
        {
            "target_account_id": target["account_id"],
            "expected_version": target["version"],
            "target_role": "auditor",
            "target_unit_ids": ["unit-a"],
            "enabled": True,
        },
        "role-change",
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["role"] == "auditor"
    assert changed.json()["version"] == target["version"] + 1

    assert target_session.get("/v1/portal/bootstrap").status_code == 401

    replay = mutate(
        owner,
        "updateUser",
        {
            "target_account_id": target["account_id"],
            "expected_version": target["version"],
            "target_role": "auditor",
            "target_unit_ids": ["unit-a"],
            "enabled": True,
        },
        "role-change",
    )
    assert replay.status_code == 200
    assert replay.json()["replay"] is True


def test_restricted_auditor_only_receives_audit_from_authorized_units(runtime):
    auditor = client(runtime, "auditor")
    response = auditor.get("/v1/portal/surfaces/audit")
    assert response.status_code == 200
    rows = response.json()["rows"]
    assert rows
    assert {row["unit_id"] for row in rows} == {"unit-a"}
    assert all(row["target_id"] != "unit-b" for row in rows)


def test_cross_tenant_account_is_not_disclosed(runtime):
    owner = client(runtime, "owner")
    denied = mutate(
        owner,
        "updateUser",
        {
            "target_account_id": "account-foreign",
            "expected_version": 0,
            "target_role": "operator",
            "target_unit_ids": ["unit-a"],
            "enabled": True,
        },
        "cross-tenant",
    )
    assert denied.status_code == 404
    assert denied.json()["detail"]["code"] == "USER_NOT_FOUND"


def test_postgres_runtime_user_update_is_atomic_audited_and_revokes_session():
    dsn = os.environ.get("NFCORE_TEST_POSTGRES_DSN", "")
    if not dsn:
        pytest.skip("real PostgreSQL DSN required; remote CI supplies it")

    with psycopg.connect(dsn, autocommit=True) as connection:
        connection.execute("DROP SCHEMA public CASCADE")
        connection.execute("CREATE SCHEMA public")

    database = PostgresFiscalDatabase(dsn)
    try:
        database.initialize()
        with database() as uow:
            uow.control_plane.add_organization(
                FiscalOrganization(tenant_id="tenant-a", legal_name="Synthetic Tenant A")
            )
            uow.control_plane.add_unit(
                FiscalUnitRegistration(
                    tenant_id="tenant-a",
                    unit_id="unit-a",
                    display_name="Synthetic unit-a",
                    enabled_environments=frozenset({FiscalEnvironment.HOMOLOGATION}),
                )
            )
            uow.control_plane.append_audit(
                ControlPlaneAuditEvent(
                    event_id="postgres-unit-audit",
                    occurred_at=NOW,
                    actor_id="synthetic-bootstrap",
                    action=ControlPlaneAuditAction.UNIT_ONBOARDED,
                    target_type="unit",
                    target_id="unit-a",
                    correlation_id="postgres-bootstrap-unit-a",
                    tenant_id="tenant-a",
                    unit_id="unit-a",
                )
            )
            uow.commit()

        hasher = ScryptPasswordHasher()
        accounts = database.human_accounts()
        accounts.save(human("owner", PortalRole.OWNER, hasher))
        accounts.save(
            human(
                "operator",
                PortalRole.OPERATOR,
                hasher,
                units=frozenset({"unit-a"}),
            )
        )
        composition = build_postgres_runtime_composition(database)
        app = create_app(
            human_identity=composition.human_identity,
            portal_executor=composition.portal_executor,
        )

        operator = TestClient(app, base_url="https://nfcore.test")
        assert (
            operator.post(
                "/v1/auth/login",
                json={"email": "operator@example.com", "password": PASSWORD},
            ).status_code
            == 200
        )
        owner = TestClient(app, base_url="https://nfcore.test")
        assert (
            owner.post(
                "/v1/auth/login",
                json={"email": "owner@example.com", "password": PASSWORD},
            ).status_code
            == 200
        )

        target = next(
            row
            for row in owner.get("/v1/portal/surfaces/users").json()["rows"]
            if row["email"] == "operator@example.com"
        )
        changed = mutate(
            owner,
            "updateUser",
            {
                "target_account_id": target["account_id"],
                "expected_version": target["version"],
                "target_role": "auditor",
                "target_unit_ids": ["unit-a"],
                "enabled": True,
            },
            "postgres-role-change",
        )
        assert changed.status_code == 200, changed.text
        assert operator.get("/v1/portal/bootstrap").status_code == 401

        persisted = accounts.by_id("account-operator")
        assert persisted is not None
        assert persisted.role is PortalRole.AUDITOR
        assert persisted.session_epoch == 1
        with database() as uow:
            events = uow.control_plane.list_audit("tenant-a")
        account_events = [
            event
            for event in events
            if event.action is ControlPlaneAuditAction.HUMAN_ACCOUNT_UPDATED
        ]
        assert len(account_events) == 1
        assert account_events[0].target_id == "account-operator"
        assert "operator@example.com" not in repr(account_events[0])
    finally:
        database.close()
