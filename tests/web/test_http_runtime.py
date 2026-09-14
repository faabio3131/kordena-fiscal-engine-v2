from __future__ import annotations

from typing import Any, Mapping

from fastapi.testclient import TestClient

from kordena_fiscal.web import (
    AuthorizedBridgeContext,
    BridgeExecutionResult,
    BridgeHttpContext,
    create_app,
)


class AllowingSecurity:
    def authorize(
        self,
        *,
        operation_id: str,
        context: BridgeHttpContext,
    ) -> AuthorizedBridgeContext:
        assert operation_id
        assert context.presented_secret == "s" * 32
        return AuthorizedBridgeContext(
            authority={"caller": context.credential_id},
            correlation_id=context.correlation_id,
        )


class RecordingExecutor:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Mapping[str, Any], str | None]] = []

    def execute(
        self,
        *,
        operation_id: str,
        authorized: AuthorizedBridgeContext,
        payload: Mapping[str, Any],
        idempotency_key: str | None,
    ) -> BridgeExecutionResult:
        assert authorized.authority == {"caller": "cred-demo"}
        self.calls.append((operation_id, payload, idempotency_key))
        return BridgeExecutionResult(
            status_code=202 if operation_id == "issueFiscalDocument" else 200,
            body={"accepted": True, "operation": operation_id},
        )


def headers(*, idempotency: bool = False) -> dict[str, str]:
    result = {
        "Authorization": f"Bearer {'s' * 32}",
        "X-FM-Workload-Credential-Id": "cred-demo",
        "X-FM-Host-Namespace": "fm-nfcore",
        "X-FM-Tenant-Id": "tenant-demo",
        "X-FM-Unit-Id": "unit-demo",
        "X-FM-Environment": "homologation",
        "X-Correlation-Id": "corr-demo",
    }
    if idempotency:
        result["Idempotency-Key"] = "idem-demo"
    return result


def test_default_runtime_is_live_but_not_ready() -> None:
    client = TestClient(create_app())

    live = client.get("/health/live")
    ready = client.get("/health/ready")

    assert live.status_code == 200
    assert live.json() == {"status": "live", "product": "FM NFCORE"}
    assert ready.status_code == 503
    assert ready.json()["reason"] == "bridge_dependencies_not_configured"


def test_operational_routes_fail_closed_without_runtime_dependencies() -> None:
    client = TestClient(create_app())

    response = client.post("/v1/queries", headers=headers(), json={"reference": "DOC-1"})

    assert response.status_code == 503
    assert response.json()["code"] == "RUNTIME_NOT_READY"
    assert response.headers["X-Correlation-Id"] == "corr-demo"


def test_missing_workload_authentication_is_rejected_before_execution() -> None:
    client = TestClient(create_app())
    request_headers = headers()
    del request_headers["Authorization"]

    response = client.post("/v1/queries", headers=request_headers, json={})

    assert response.status_code == 401
    assert response.json()["code"] == "AUTHENTICATION_REQUIRED"


def test_mutating_route_requires_idempotency_key() -> None:
    client = TestClient(create_app())

    response = client.post("/v1/issuances", headers=headers(), json={})

    assert response.status_code == 400
    assert response.json()["code"] == "MISSING_IDEMPOTENCY_KEY"


def test_injected_boundaries_execute_authorized_request() -> None:
    executor = RecordingExecutor()
    client = TestClient(create_app(security=AllowingSecurity(), executor=executor))

    response = client.post(
        "/v1/issuances",
        headers=headers(idempotency=True),
        json={"document_kind": "NFE"},
    )

    assert response.status_code == 202
    assert response.json() == {"accepted": True, "operation": "issueFiscalDocument"}
    assert response.headers["X-Correlation-Id"] == "corr-demo"
    assert executor.calls == [
        ("issueFiscalDocument", {"document_kind": "NFE"}, "idem-demo")
    ]


def test_context_repr_never_exposes_presented_secret() -> None:
    context = BridgeHttpContext(
        host_namespace="fm-nfcore",
        tenant_id="tenant-demo",
        unit_id="unit-demo",
        environment="homologation",
        correlation_id="corr-demo",
        causation_id=None,
        credential_id="cred-demo",
        presented_secret="secret-that-must-not-appear",
        idempotency_key=None,
    )

    rendered = repr(context)
    assert "secret-that-must-not-appear" not in rendered
    assert "<redacted>" in rendered


def test_bridge_routes_keep_canonical_operation_ids() -> None:
    schema = create_app().openapi()
    expected = {
        "/v1/archive/references/query": "queryArchiveReference",
        "/v1/cancellations": "cancelFiscalDocument",
        "/v1/capabilities/query": "queryCapabilities",
        "/v1/inutilizations": "inutilizeFiscalRange",
        "/v1/issuances": "issueFiscalDocument",
        "/v1/queries": "queryFiscalDocument",
        "/v1/reconciliations": "reconcileFiscalOperation",
    }

    for path, operation_id in expected.items():
        assert schema["paths"][path]["post"]["operationId"] == operation_id
