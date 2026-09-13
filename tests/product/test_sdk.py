from __future__ import annotations

import hashlib
import hmac
from pathlib import Path

import pytest

from fm_fiscal_sdk import (
    BridgeClient,
    BridgeRequest,
    BridgeResponse,
    RetryableTransportError,
    RetryPolicy,
    verify_webhook_signature,
)


class RecordingTransport:
    def __init__(self, *, failures: int = 0) -> None:
        self.failures = failures
        self.requests: list[BridgeRequest] = []

    def send(self, request: BridgeRequest) -> BridgeResponse:
        self.requests.append(request)
        if len(self.requests) <= self.failures:
            raise RetryableTransportError("synthetic transport failure")
        return BridgeResponse(202, b"{}")


def client(transport: RecordingTransport) -> BridgeClient:
    return BridgeClient(
        transport=transport,
        workload_credential_id="cred-demo",
        bearer_secret="synthetic-token",
        host_namespace="fm.example",
        tenant_id="tenant-demo",
        unit_id="unit-demo",
        environment="HOMOLOGATION",
    )


def test_issue_builds_public_bridge_headers_and_stable_idempotency() -> None:
    transport = RecordingTransport()
    response = client(transport).issue(
        b"{}",
        correlation_id="corr-1",
        idempotency_key="demo:issue:1:v1",
        causation_id="cause-1",
    )
    assert response.status_code == 202
    request = transport.requests[0]
    assert request.path == "/v1/issuances"
    assert request.headers["X-FM-Host-Namespace"] == "fm.example"
    assert request.headers["X-FM-Tenant-Id"] == "tenant-demo"
    assert request.headers["X-FM-Unit-Id"] == "unit-demo"
    assert request.headers["X-FM-Environment"] == "HOMOLOGATION"
    assert request.headers["Idempotency-Key"] == "demo:issue:1:v1"
    assert request.headers["X-Causation-Id"] == "cause-1"


def test_sdk_retries_transport_only_and_reuses_identical_request() -> None:
    transport = RecordingTransport(failures=2)
    sdk = BridgeClient(
        transport=transport,
        workload_credential_id="cred-demo",
        bearer_secret="synthetic-token",
        host_namespace="fm.example",
        tenant_id="tenant-demo",
        unit_id="unit-demo",
        environment="HOMOLOGATION",
        retry_policy=RetryPolicy(max_attempts=3),
    )
    sdk.reconcile(b"{}", correlation_id="corr-2", idempotency_key="reconcile:1")
    assert len(transport.requests) == 3
    assert all(
        item.headers["Idempotency-Key"] == "reconcile:1" for item in transport.requests
    )


def test_retry_exhaustion_propagates_transport_failure() -> None:
    transport = RecordingTransport(failures=3)
    sdk = BridgeClient(
        transport=transport,
        workload_credential_id="cred-demo",
        bearer_secret="synthetic-token",
        host_namespace="fm.example",
        tenant_id="tenant-demo",
        unit_id="unit-demo",
        environment="HOMOLOGATION",
        retry_policy=RetryPolicy(max_attempts=2),
    )
    with pytest.raises(RetryableTransportError):
        sdk.query(b"{}", correlation_id="corr-3")
    assert len(transport.requests) == 2


def test_webhook_signature_verification_is_constant_time_hmac_contract() -> None:
    payload = b'{"event":"demo"}'
    key = b"synthetic-key"
    signature = hmac.new(key, payload, hashlib.sha256).hexdigest()
    assert verify_webhook_signature(payload, signature_hex=signature, key=key) is True
    assert verify_webhook_signature(payload, signature_hex="00" * 32, key=key) is False


def test_python_sdk_does_not_import_private_fiscal_package() -> None:
    source = Path("src/fm_fiscal_sdk/client.py").read_text(encoding="utf-8")
    assert "kordena_fiscal" not in source
    assert "provider_id" not in source
    assert "production_approved" not in source.lower()


def test_typescript_sdk_uses_public_bridge_only() -> None:
    source = Path("sdks/typescript/src/index.ts").read_text(encoding="utf-8")
    for path in (
        "/v1/capabilities/query",
        "/v1/issuances",
        "/v1/queries",
        "/v1/reconciliations",
    ):
        assert path in source
    assert "kordena_fiscal" not in source
    assert "database" not in source.lower()
