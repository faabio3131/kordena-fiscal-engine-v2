from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from kordena_fiscal.application.service import FiscalApplicationService
from kordena_fiscal.domain import (
    ExecutionScope,
    FiscalAccountBinding,
    FiscalAccountId,
    FiscalUnitId,
    HostNamespace,
    HostScope,
)
from kordena_fiscal.persistence import SqliteFiscalDatabase
from kordena_fiscal.runtime.fiscal_runtime import (
    CanonicalBridgeRequestExecutor,
    CanonicalBridgeSecurityBoundary,
    CanonicalFiscalOperationPath,
)
from kordena_fiscal.security.s2s import (
    CallerIdentity,
    FiscalCapability,
    HostScopeGrant,
    InMemorySecurityAuditSink,
    S2SAuthorizer,
    WorkloadAuthenticator,
    WorkloadCredentialRecord,
)
from kordena_fiscal.web import create_app

WORKLOAD_SECRET = "s" * 40
VALID_FROM = datetime(2026, 1, 1, tzinfo=UTC)
EXPIRES_AT = datetime(2027, 1, 1, tzinfo=UTC)

OPERATIONS: tuple[tuple[str, str, int, bool], ...] = (
    ("/v1/archive/references/query", "queryArchiveReference", 200, False),
    ("/v1/cancellations", "cancelFiscalDocument", 202, True),
    ("/v1/capabilities/query", "queryCapabilities", 200, False),
    ("/v1/inutilizations", "inutilizeFiscalRange", 202, True),
    ("/v1/issuances", "issueFiscalDocument", 202, True),
    ("/v1/queries", "queryFiscalDocument", 200, False),
    ("/v1/reconciliations", "reconcileFiscalOperation", 200, True),
)


class _Recorder:
    def __init__(self) -> None:
        self.calls: list[
            tuple[str, ExecutionScope, Mapping[str, Any], str | None]
        ] = []

    def handler(self, operation_id: str):
        def execute(
            scope: ExecutionScope,
            payload: Mapping[str, Any],
            idempotency_key: str | None,
        ) -> Mapping[str, Any]:
            self.calls.append((operation_id, scope, payload, idempotency_key))
            return {
                "operation_id": operation_id,
                "tenant_id": scope.tenant_id,
                "unit_id": scope.unit_id,
                "environment": scope.environment.value,
                "idempotency_key": idempotency_key,
            }

        return execute


def _database(tmp_path: Path) -> SqliteFiscalDatabase:
    database = SqliteFiscalDatabase(tmp_path / "t04-fiscal-api.sqlite3")
    database.initialize()
    with database() as uow:
        uow.bindings.add(
            FiscalAccountBinding(
                binding_id="binding-api-cert",
                host_scope=HostScope(
                    namespace=HostNamespace("fm-nfcore"),
                    tenant_id="tenant-api",
                    unit_id="unit-api",
                ),
                fiscal_account_id=FiscalAccountId("fiscal-account-api"),
                fiscal_unit_id=FiscalUnitId("fiscal-unit-api"),
            )
        )
        uow.commit()
    return database


def _security(
    path: CanonicalFiscalOperationPath,
) -> CanonicalBridgeSecurityBoundary:
    caller = CallerIdentity(
        caller_id="nfcore-api-cert",
        host_namespace=HostNamespace("fm-nfcore"),
        capabilities=frozenset(
            {
                FiscalCapability.ARCHIVE_READ,
                FiscalCapability.CANCEL,
                FiscalCapability.CAPABILITIES_READ,
                FiscalCapability.INUTILIZE,
                FiscalCapability.ISSUE,
                FiscalCapability.QUERY,
                FiscalCapability.RECONCILE,
            }
        ),
        scope_grants=(
            HostScopeGrant(tenant_id="tenant-api", unit_id="unit-api"),
        ),
    )
    credential = WorkloadCredentialRecord.from_secret(
        credential_id="credential-api-cert",
        caller=caller,
        secret=WORKLOAD_SECRET,
        valid_from=VALID_FROM,
        expires_at=EXPIRES_AT,
    )
    return CanonicalBridgeSecurityBoundary(
        authenticator=WorkloadAuthenticator((credential,)),
        authorizer=S2SAuthorizer(
            bindings=path,
            audit_sink=InMemorySecurityAuditSink(),
        ),
    )


def _headers(*, idempotency_key: str | None = None) -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {WORKLOAD_SECRET}",
        "X-FM-Workload-Credential-Id": "credential-api-cert",
        "X-FM-Host-Namespace": "fm-nfcore",
        "X-FM-Tenant-Id": "tenant-api",
        "X-FM-Unit-Id": "unit-api",
        "X-FM-Environment": "homologation",
        "X-Correlation-Id": "corr-t04-api-cert",
    }
    if idempotency_key is not None:
        headers["Idempotency-Key"] = idempotency_key
    return headers


@pytest.mark.parametrize(
    ("route", "operation_id", "expected_status", "mutating"),
    OPERATIONS,
)
def test_launch_scope_routes_execute_through_one_canonical_path(
    tmp_path: Path,
    route: str,
    operation_id: str,
    expected_status: int,
    mutating: bool,
) -> None:
    recorder = _Recorder()
    database = _database(tmp_path)
    handlers = {
        registered_operation: recorder.handler(registered_operation)
        for _, registered_operation, _, _ in OPERATIONS
    }
    path = CanonicalFiscalOperationPath(
        FiscalApplicationService(database),
        handlers=handlers,
    )
    client = TestClient(
        create_app(
            security=_security(path),
            executor=CanonicalBridgeRequestExecutor(path),
        ),
        base_url="https://nfcore.test",
    )
    idempotency_key = f"idem-{operation_id}" if mutating else None

    response = client.post(
        route,
        headers=_headers(idempotency_key=idempotency_key),
        json={"probe": operation_id},
    )

    assert response.status_code == expected_status
    assert response.headers["X-Correlation-Id"] == "corr-t04-api-cert"
    assert response.json() == {
        "operation_id": operation_id,
        "tenant_id": "fiscal-account-api",
        "unit_id": "fiscal-unit-api",
        "environment": "homologation",
        "idempotency_key": idempotency_key,
    }
    assert recorder.calls == [
        (
            operation_id,
            recorder.calls[0][1],
            {"probe": operation_id},
            idempotency_key,
        )
    ]
    assert recorder.calls[0][1].tenant_id == "fiscal-account-api"
    assert recorder.calls[0][1].unit_id == "fiscal-unit-api"


@pytest.mark.parametrize(
    ("route", "operation_id", "_expected_status", "mutating"),
    OPERATIONS,
)
def test_launch_scope_routes_fail_closed_without_operation_dependency(
    tmp_path: Path,
    route: str,
    operation_id: str,
    _expected_status: int,
    mutating: bool,
) -> None:
    database = _database(tmp_path)
    path = CanonicalFiscalOperationPath(FiscalApplicationService(database))
    client = TestClient(
        create_app(
            security=_security(path),
            executor=CanonicalBridgeRequestExecutor(path),
        ),
        base_url="https://nfcore.test",
    )

    response = client.post(
        route,
        headers=_headers(
            idempotency_key=f"idem-{operation_id}" if mutating else None
        ),
        json={"probe": operation_id},
    )

    assert response.status_code == 503
    assert response.json()["code"] == "FISCAL_RUNTIME_NOT_READY"
    assert response.headers["X-Correlation-Id"] == "corr-t04-api-cert"


@pytest.mark.parametrize(
    ("route", "operation_id", "_expected_status", "mutating"),
    tuple(item for item in OPERATIONS if item[3]),
)
def test_launch_scope_mutations_require_idempotency_before_execution(
    tmp_path: Path,
    route: str,
    operation_id: str,
    _expected_status: int,
    mutating: bool,
) -> None:
    assert mutating is True
    recorder = _Recorder()
    database = _database(tmp_path)
    path = CanonicalFiscalOperationPath(
        FiscalApplicationService(database),
        handlers={operation_id: recorder.handler(operation_id)},
    )
    client = TestClient(
        create_app(
            security=_security(path),
            executor=CanonicalBridgeRequestExecutor(path),
        ),
        base_url="https://nfcore.test",
    )

    response = client.post(
        route,
        headers=_headers(),
        json={"probe": operation_id},
    )

    assert response.status_code == 400
    assert response.json()["code"] == "MISSING_IDEMPOTENCY_KEY"
    assert recorder.calls == []
