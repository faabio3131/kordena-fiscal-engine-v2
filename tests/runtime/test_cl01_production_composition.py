from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
from types import TracebackType
from typing import Iterator

from fastapi.testclient import TestClient

from kordena_fiscal.control_plane.models import (
    ControlPlaneAuditAction,
    ControlPlaneAuditEvent,
    FiscalOrganization,
    FiscalUnitRegistration,
)
from kordena_fiscal.domain import FiscalEnvironment
from kordena_fiscal.runtime import api as runtime_api
from kordena_fiscal.runtime.config import RuntimeSettings
from kordena_fiscal.security.human_identity import (
    HumanAccount,
    InMemoryHumanAccountRepository,
    InMemoryWebSessionRepository,
    PortalRole,
    ScryptPasswordHasher,
)
from kordena_fiscal.security.human_recovery import InMemoryPasswordResetRepository

PASSWORD = "commercial-runtime-password-2026"
NOW = datetime(2026, 9, 16, 15, 30, tzinfo=UTC)


class _Cursor:
    def fetchone(self) -> tuple[int]:
        return (1,)


class _Connection:
    def execute(self, _statement: str) -> _Cursor:
        return _Cursor()


class _ControlPlane:
    def __init__(self) -> None:
        self.organization = FiscalOrganization(
            tenant_id="tenant-a",
            legal_name="Empresa Piloto Ltda",
        )
        self.unit = FiscalUnitRegistration(
            tenant_id="tenant-a",
            unit_id="unit-a",
            display_name="Matriz",
            enabled_environments=frozenset({FiscalEnvironment.HOMOLOGATION}),
        )
        self.events = (
            ControlPlaneAuditEvent(
                event_id="audit-unit-a",
                occurred_at=NOW,
                actor_id="admin-a",
                action=ControlPlaneAuditAction.UNIT_ONBOARDED,
                target_type="unit",
                target_id="unit-a",
                correlation_id="corr-unit-a",
                tenant_id="tenant-a",
                unit_id="unit-a",
            ),
        )

    def get_organization(self, tenant_id: str) -> FiscalOrganization | None:
        return self.organization if tenant_id == "tenant-a" else None

    def get_unit(self, tenant_id: str, unit_id: str) -> FiscalUnitRegistration | None:
        if tenant_id == "tenant-a" and unit_id == "unit-a":
            return self.unit
        return None

    def list_audit(self, tenant_id: str | None = None) -> tuple[ControlPlaneAuditEvent, ...]:
        if tenant_id is None or tenant_id == "tenant-a":
            return self.events
        return ()


class _UnitOfWork:
    def __init__(self, control_plane: _ControlPlane) -> None:
        self.control_plane = control_plane

    def __enter__(self) -> _UnitOfWork:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc, traceback


class _RuntimeDatabase:
    last: _RuntimeDatabase | None = None

    def __init__(self, _dsn: str) -> None:
        type(self).last = self
        hasher = ScryptPasswordHasher()
        self.accounts = InMemoryHumanAccountRepository(
            (
                HumanAccount(
                    account_id="owner-a",
                    email="owner@example.com",
                    password_hash=hasher.hash(PASSWORD),
                    tenant_id="tenant-a",
                    role=PortalRole.OWNER,
                ),
            )
        )
        self.sessions = InMemoryWebSessionRepository()
        self.resets = InMemoryPasswordResetRepository()
        self.control_plane = _ControlPlane()
        self.closed = False

    def initialize(self) -> tuple[int]:
        return (1,)

    @contextmanager
    def connection(self) -> Iterator[_Connection]:
        yield _Connection()

    def applied_migrations(self) -> tuple[int]:
        return (1,)

    def human_accounts(self) -> InMemoryHumanAccountRepository:
        return self.accounts

    def web_sessions(self) -> InMemoryWebSessionRepository:
        return self.sessions

    def password_resets(self) -> InMemoryPasswordResetRepository:
        return self.resets

    def __call__(self) -> _UnitOfWork:
        return _UnitOfWork(self.control_plane)

    def close(self) -> None:
        self.closed = True


def _settings() -> RuntimeSettings:
    return RuntimeSettings.from_mapping(
        {
            "NFCORE_ENVIRONMENT": "staging",
            "NFCORE_PERSISTENCE_BACKEND": "postgres",
            "DATABASE_URL": "postgresql://user:password@db:5432/nfcore",
            "NFCORE_SECRET_BACKEND": "external",
            "NFCORE_REQUIRE_HTTPS": "true",
        }
    )


def test_postgres_runtime_composes_human_identity_recovery_and_durable_portal(
    monkeypatch,
) -> None:
    monkeypatch.setattr(runtime_api, "PostgresFiscalDatabase", _RuntimeDatabase)

    with TestClient(
        runtime_api.create_runtime_app(_settings()),
        base_url="https://testserver",
    ) as client:
        profile = client.get("/runtime/profile").json()
        assert profile["human_identity_configured"] is True
        assert profile["portal_executor_configured"] is True
        assert profile["password_recovery_configured"] is True
        assert profile["fiscal_production_activated"] is False

        login = client.post(
            "/v1/auth/login",
            json={"email": "owner@example.com", "password": PASSWORD},
        )
        assert login.status_code == 200

        bootstrap = client.get("/v1/portal/bootstrap")
        assert bootstrap.status_code == 200
        projection = bootstrap.json()["projection"]
        assert projection["organization_onboarded"] is True
        assert projection["legal_name"] == "Empresa Piloto Ltda"
        assert projection["unit_count"] == 1
        assert projection["fiscal_operations_configured"] is False

        units = client.get("/v1/portal/surfaces/units")
        assert units.status_code == 200
        assert units.json()["rows"][0]["unit_id"] == "unit-a"

        unsupported = client.get("/v1/portal/surfaces/documents")
        assert unsupported.status_code == 503
        assert unsupported.json()["detail"]["code"] == "PORTAL_RUNTIME_NOT_READY"

    database = _RuntimeDatabase.last
    assert database is not None
    assert database.closed is True


def test_postgres_runtime_reports_composition_failure_separately(monkeypatch) -> None:
    monkeypatch.setattr(runtime_api, "PostgresFiscalDatabase", _RuntimeDatabase)

    def fail_composition(*_args, **_kwargs):
        raise RuntimeError("synthetic composition failure")

    monkeypatch.setattr(runtime_api, "build_postgres_runtime_composition", fail_composition)
    client = TestClient(runtime_api.create_runtime_app(_settings()), base_url="https://testserver")

    response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json() == {"status": "not_ready", "reason": "composition_unavailable"}
