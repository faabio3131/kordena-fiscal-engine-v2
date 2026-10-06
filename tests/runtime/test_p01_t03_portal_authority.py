from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from kordena_fiscal.application.service import FiscalApplicationService
from kordena_fiscal.control_plane import FiscalOrganization, FiscalUnitRegistration
from kordena_fiscal.domain import ExecutionScope, FiscalEnvironment
from kordena_fiscal.persistence import SqliteFiscalDatabase
from kordena_fiscal.runtime.fiscal_runtime import (
    CanonicalFiscalOperationPath,
    CanonicalPortalOperationExecutor,
)
from kordena_fiscal.security.human_identity import (
    HumanAccount,
    HumanIdentityService,
    InMemoryHumanAccountRepository,
    InMemoryWebSessionRepository,
    PortalRole,
    ScryptPasswordHasher,
)
from kordena_fiscal.web import create_app
from kordena_fiscal.web.human_auth import CSRF_COOKIE, CSRF_HEADER
from kordena_fiscal.web.portal_runtime import DurableHumanPortalExecutor

PASSWORD = "correct-horse-nfcore-2026"


class _RecordingHandler:
    def __init__(self) -> None:
        self.calls: list[tuple[ExecutionScope, Mapping[str, Any], str | None]] = []

    def __call__(
        self,
        scope: ExecutionScope,
        payload: Mapping[str, Any],
        idempotency_key: str | None,
    ) -> Mapping[str, Any]:
        self.calls.append((scope, payload, idempotency_key))
        return {
            "tenant_id": scope.tenant_id,
            "unit_id": scope.unit_id,
            "idempotency_key": idempotency_key,
        }


def _database(tmp_path: Path) -> SqliteFiscalDatabase:
    database = SqliteFiscalDatabase(tmp_path / "portal-authority.sqlite3")
    database.initialize()
    with database() as uow:
        uow.control_plane.add_organization(
            FiscalOrganization(
                tenant_id="tenant-a",
                legal_name="Tenant A Ltda",
            )
        )
        for unit_id in ("unit-a", "unit-b"):
            uow.control_plane.add_unit(
                FiscalUnitRegistration(
                    tenant_id="tenant-a",
                    unit_id=unit_id,
                    display_name=f"Unit {unit_id}",
                    enabled_environments=frozenset(
                        {FiscalEnvironment.HOMOLOGATION}
                    ),
                )
            )
        uow.commit()
    return database


def _identity() -> HumanIdentityService:
    hasher = ScryptPasswordHasher()
    accounts = (
        HumanAccount(
            account_id="operator-a",
            email="operator@example.com",
            password_hash=hasher.hash(PASSWORD),
            tenant_id="tenant-a",
            role=PortalRole.OPERATOR,
            unit_ids=frozenset({"unit-a"}),
        ),
        HumanAccount(
            account_id="auditor-a",
            email="auditor@example.com",
            password_hash=hasher.hash(PASSWORD),
            tenant_id="tenant-a",
            role=PortalRole.AUDITOR,
            unit_ids=frozenset({"unit-a"}),
        ),
    )
    return HumanIdentityService(
        accounts=InMemoryHumanAccountRepository(accounts),
        sessions=InMemoryWebSessionRepository(),
        password_hasher=hasher,
    )


def _client(
    database: SqliteFiscalDatabase,
    handler: _RecordingHandler,
) -> TestClient:
    path = CanonicalFiscalOperationPath(
        FiscalApplicationService(database),
        handlers={"issueFiscalDocument": handler},
    )
    fiscal_executor = CanonicalPortalOperationExecutor(
        unit_of_work_factory=database,
        path=path,
    )
    portal = DurableHumanPortalExecutor(
        database,
        operation_executor=fiscal_executor,
    )
    return TestClient(
        create_app(
            human_identity=_identity(),
            portal_executor=portal,
        ),
        base_url="https://nfcore.test",
    )


def _login(client: TestClient, email: str) -> str:
    response = client.post(
        "/v1/auth/login",
        json={"email": email, "password": PASSWORD},
    )
    assert response.status_code == 200
    csrf = client.cookies.get(CSRF_COOKIE)
    assert csrf
    return csrf


def test_portal_rejects_browser_tenant_authority_and_cross_unit_scope(
    tmp_path: Path,
) -> None:
    handler = _RecordingHandler()
    client = _client(_database(tmp_path), handler)
    csrf = _login(client, "operator@example.com")

    tenant_spoof = client.post(
        "/v1/portal/operations/issueFiscalDocument",
        headers={
            CSRF_HEADER: csrf,
            "Idempotency-Key": "idem-tenant-spoof",
        },
        json={
            "tenant_id": "tenant-b",
            "unit_id": "unit-a",
            "document_kind": "nfe",
        },
    )
    assert tenant_spoof.status_code == 400
    assert tenant_spoof.json()["detail"]["code"] == "BROWSER_AUTHORITY_REJECTED"

    cross_unit = client.post(
        "/v1/portal/operations/issueFiscalDocument",
        headers={
            CSRF_HEADER: csrf,
            "Idempotency-Key": "idem-cross-unit",
        },
        json={"unit_id": "unit-b", "document_kind": "nfe"},
    )
    assert cross_unit.status_code == 403
    assert cross_unit.json()["detail"]["code"] == "PORTAL_FORBIDDEN"
    assert handler.calls == []


def test_portal_rbac_and_session_fail_closed_before_execution(
    tmp_path: Path,
) -> None:
    handler = _RecordingHandler()
    database = _database(tmp_path)

    anonymous = _client(database, handler)
    without_session = anonymous.post(
        "/v1/portal/operations/issueFiscalDocument",
        headers={"Idempotency-Key": "idem-no-session"},
        json={"unit_id": "unit-a", "document_kind": "nfe"},
    )
    assert without_session.status_code == 401
    assert without_session.json()["detail"]["code"] == "SESSION_REQUIRED"

    auditor = _client(database, handler)
    csrf = _login(auditor, "auditor@example.com")
    forbidden = auditor.post(
        "/v1/portal/operations/issueFiscalDocument",
        headers={
            CSRF_HEADER: csrf,
            "Idempotency-Key": "idem-auditor",
        },
        json={"unit_id": "unit-a", "document_kind": "nfe"},
    )
    assert forbidden.status_code == 403
    assert forbidden.json()["detail"]["code"] == "PORTAL_FORBIDDEN"
    assert handler.calls == []


def test_portal_valid_session_scope_and_idempotency_reach_canonical_path(
    tmp_path: Path,
) -> None:
    handler = _RecordingHandler()
    client = _client(_database(tmp_path), handler)
    csrf = _login(client, "operator@example.com")

    missing_key = client.post(
        "/v1/portal/operations/issueFiscalDocument",
        headers={CSRF_HEADER: csrf},
        json={"unit_id": "unit-a", "document_kind": "nfe"},
    )
    assert missing_key.status_code == 400
    assert missing_key.json()["detail"]["code"] == "MISSING_IDEMPOTENCY_KEY"

    accepted = client.post(
        "/v1/portal/operations/issueFiscalDocument",
        headers={
            CSRF_HEADER: csrf,
            "Idempotency-Key": "idem-portal-001",
        },
        json={"unit_id": "unit-a", "document_kind": "nfe"},
    )

    assert accepted.status_code == 200
    assert accepted.json()["tenant_id"] == "tenant-a"
    assert accepted.json()["unit_id"] == "unit-a"
    assert accepted.json()["idempotency_key"] == "idem-portal-001"
    assert len(handler.calls) == 1
    scope, _payload, key = handler.calls[0]
    assert scope.tenant_id == "tenant-a"
    assert scope.unit_id == "unit-a"
    assert key == "idem-portal-001"
