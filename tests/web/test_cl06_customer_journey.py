from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from kordena_fiscal.control_plane.durable import DurableControlPlaneService
from kordena_fiscal.control_plane.models import AdminPrincipal, ControlPlanePermission
from kordena_fiscal.persistence import SqliteFiscalDatabase
from kordena_fiscal.security.human_identity import (
    HumanAccount,
    HumanIdentityService,
    InMemoryHumanAccountRepository,
    InMemoryWebSessionRepository,
    PortalRole,
    ScryptPasswordHasher,
)
from kordena_fiscal.security.human_recovery import (
    InMemoryPasswordResetRepository,
    IssuedPasswordReset,
    PasswordRecoveryService,
)
from kordena_fiscal.web import create_app
from kordena_fiscal.web.human_auth import CSRF_COOKIE, CSRF_HEADER
from kordena_fiscal.web.portal_runtime import DurableHumanPortalExecutor

NOW = datetime(2026, 9, 16, 17, 30, tzinfo=UTC)
PASSWORD = "commercial-owner-password-2026"
NEW_PASSWORD = "commercial-owner-password-2027"
TENANT_ID = "commercial-tenant"
EMAIL = "owner@commercial.example"


@dataclass(slots=True)
class RecordingResetDelivery:
    delivered: list[tuple[str, IssuedPasswordReset]] = field(default_factory=list)

    def deliver(self, *, email: str, reset: IssuedPasswordReset) -> None:
        self.delivered.append((email, reset))


def _identity_stack() -> tuple[
    HumanIdentityService,
    PasswordRecoveryService,
    InMemoryHumanAccountRepository,
    InMemoryWebSessionRepository,
]:
    hasher = ScryptPasswordHasher()
    accounts = InMemoryHumanAccountRepository(
        (
            HumanAccount(
                account_id="commercial-owner",
                email=EMAIL,
                password_hash=hasher.hash(PASSWORD),
                tenant_id=TENANT_ID,
                role=PortalRole.OWNER,
                unit_ids=None,
            ),
        )
    )
    sessions = InMemoryWebSessionRepository()
    identity = HumanIdentityService(
        accounts=accounts,
        sessions=sessions,
        password_hasher=hasher,
        session_ttl=timedelta(hours=8),
    )
    recovery = PasswordRecoveryService(
        accounts=accounts,
        sessions=sessions,
        resets=InMemoryPasswordResetRepository(),
        password_hasher=hasher,
    )
    return identity, recovery, accounts, sessions


def test_password_recovery_is_generic_one_time_and_revokes_existing_sessions() -> None:
    identity, recovery, _accounts, _sessions = _identity_stack()
    delivery = RecordingResetDelivery()
    web = TestClient(
        create_app(
            human_identity=identity,
            password_recovery=recovery,
            password_reset_delivery=delivery,
        ),
        base_url="https://nfcore.test",
    )

    logged_in = web.post(
        "/v1/auth/login",
        json={"email": EMAIL, "password": PASSWORD},
    )
    assert logged_in.status_code == 200
    assert web.get("/v1/auth/me").status_code == 200

    unknown = web.post(
        "/v1/auth/password-reset/request",
        json={"email": "unknown@commercial.example"},
    )
    known = web.post(
        "/v1/auth/password-reset/request",
        json={"email": EMAIL},
    )
    assert unknown.status_code == known.status_code == 202
    assert unknown.json() == known.json() == {"status": "accepted"}
    assert "token" not in known.text.casefold()
    assert len(delivery.delivered) == 1

    reset = delivery.delivered[0][1]
    completed = web.post(
        "/v1/auth/password-reset/complete",
        json={"reset_token": reset.reset_token, "new_password": NEW_PASSWORD},
    )
    assert completed.status_code == 204
    assert web.get("/v1/auth/me").status_code == 401

    reused = web.post(
        "/v1/auth/password-reset/complete",
        json={"reset_token": reset.reset_token, "new_password": PASSWORD},
    )
    assert reused.status_code == 400
    assert reused.json()["detail"]["code"] == "PASSWORD_RESET_NOT_USABLE"

    assert web.post(
        "/v1/auth/login",
        json={"email": EMAIL, "password": PASSWORD},
    ).status_code == 401
    assert web.post(
        "/v1/auth/login",
        json={"email": EMAIL, "password": NEW_PASSWORD},
    ).status_code == 200


def test_password_reset_request_without_delivery_never_exposes_account_state() -> None:
    identity, recovery, _accounts, _sessions = _identity_stack()
    web = TestClient(
        create_app(
            human_identity=identity,
            password_recovery=recovery,
            password_reset_delivery=None,
        ),
        base_url="https://nfcore.test",
    )

    known = web.post("/v1/auth/password-reset/request", json={"email": EMAIL})
    unknown = web.post(
        "/v1/auth/password-reset/request",
        json={"email": "unknown@commercial.example"},
    )

    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json() == {"status": "accepted"}


def _onboarding_client(tmp_path: Path) -> tuple[TestClient, SqliteFiscalDatabase]:
    database = SqliteFiscalDatabase(tmp_path / "cl06-onboarding.sqlite3")
    database.initialize()
    service = DurableControlPlaneService(database)
    service.onboard_organization(
        actor=AdminPrincipal(
            actor_id="commercial-provisioner",
            permissions=frozenset({ControlPlanePermission.ORGANIZATION_WRITE}),
            global_scope=True,
        ),
        tenant_id=TENANT_ID,
        legal_name="Commercial Tenant Ltda",
        correlation_id="commercial-provisioning-evidence",
    )
    identity, _recovery, _accounts, _sessions = _identity_stack()
    portal = DurableHumanPortalExecutor(database)
    web = TestClient(
        create_app(human_identity=identity, portal_executor=portal),
        base_url="https://nfcore.test",
    )
    login = web.post(
        "/v1/auth/login",
        json={"email": EMAIL, "password": PASSWORD},
    )
    assert login.status_code == 200
    return web, database


def test_owner_can_finish_basic_unit_onboarding_without_browser_tenant_authority(
    tmp_path: Path,
) -> None:
    web, database = _onboarding_client(tmp_path)
    before = web.get("/v1/portal/bootstrap")
    assert before.status_code == 200
    assert before.json()["projection"]["onboarding_stage"] == "unit_setup_required"
    assert "onboarding" in before.json()["projection"]["available_surfaces"]

    csrf = web.cookies.get(CSRF_COOKIE)
    assert csrf
    headers = {
        CSRF_HEADER: csrf,
        "Idempotency-Key": "cl06-onboard-unit-a",
    }
    created = web.post(
        "/v1/portal/operations/onboardUnit",
        headers=headers,
        json={"unit_id": "matriz", "display_name": "Matriz"},
    )
    assert created.status_code == 200
    assert created.json() == {
        "status": "onboarded",
        "unit_id": "matriz",
        "environment": "homologation",
    }

    replay = web.post(
        "/v1/portal/operations/onboardUnit",
        headers=headers,
        json={"unit_id": "matriz", "display_name": "Matriz"},
    )
    assert replay.status_code == 200
    assert replay.json()["status"] == "already_onboarded"

    after = web.get("/v1/portal/bootstrap")
    assert after.status_code == 200
    assert after.json()["projection"]["onboarding_stage"] == "basic_setup_complete"
    assert after.json()["projection"]["basic_onboarding_complete"] is True

    with database.unit_of_work() as uow:
        unit = uow.control_plane.get_unit(TENANT_ID, "matriz")
    assert unit is not None
    assert {environment.value for environment in unit.enabled_environments} == {
        "homologation"
    }


def test_browser_cannot_mass_assign_tenant_during_self_service_onboarding(
    tmp_path: Path,
) -> None:
    web, _database = _onboarding_client(tmp_path)
    csrf = web.cookies.get(CSRF_COOKIE)
    assert csrf

    response = web.post(
        "/v1/portal/operations/onboardUnit",
        headers={CSRF_HEADER: csrf, "Idempotency-Key": "tenant-spoof"},
        json={
            "tenant_id": "attacker-tenant",
            "unit_id": "matriz",
            "display_name": "Matriz",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "BROWSER_AUTHORITY_REJECTED"
