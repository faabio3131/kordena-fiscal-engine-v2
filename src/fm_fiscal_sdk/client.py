"""Thin provider-neutral client contracts for the public FM Fiscal Bridge."""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from typing import Protocol


class SDKValidationError(ValueError):
    """Raised when a client request is unsafe or incomplete."""


class RetryableTransportError(RuntimeError):
    """Transport-only retry signal; fiscal semantic errors are not retried here."""


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    max_attempts: int = 3

    def __post_init__(self) -> None:
        if not isinstance(self.max_attempts, int) or isinstance(self.max_attempts, bool):
            raise SDKValidationError("max_attempts must be integer")
        if not 1 <= self.max_attempts <= 10:
            raise SDKValidationError("max_attempts must be between 1 and 10")


@dataclass(frozen=True, slots=True)
class BridgeRequest:
    method: str
    path: str
    headers: dict[str, str]
    body: bytes


@dataclass(frozen=True, slots=True)
class BridgeResponse:
    status_code: int
    body: bytes

    def __post_init__(self) -> None:
        if not 100 <= self.status_code <= 599:
            raise SDKValidationError("status_code must be valid HTTP status")


class BridgeTransport(Protocol):
    def send(self, request: BridgeRequest) -> BridgeResponse: ...


class BridgeClient:
    """Public Bridge client with scope, trace and idempotency handling."""

    def __init__(
        self,
        *,
        transport: BridgeTransport,
        workload_credential_id: str,
        bearer_secret: str,
        host_namespace: str,
        tenant_id: str,
        unit_id: str,
        environment: str,
        retry_policy: RetryPolicy | None = None,
    ) -> None:
        self._transport = transport
        self._credential_id = _required(workload_credential_id, "workload_credential_id")
        self._bearer_secret = _required(bearer_secret, "bearer_secret")
        self._host_namespace = _required(host_namespace, "host_namespace")
        self._tenant_id = _required(tenant_id, "tenant_id")
        self._unit_id = _required(unit_id, "unit_id")
        normalized_environment = environment.strip().upper()
        if normalized_environment not in {"HOMOLOGATION", "PRODUCTION"}:
            raise SDKValidationError("environment must be HOMOLOGATION or PRODUCTION")
        self._environment = normalized_environment
        self._retry_policy = retry_policy or RetryPolicy()

    def capability_query(self, body: bytes, *, correlation_id: str) -> BridgeResponse:
        return self._send(
            path="/v1/capabilities/query",
            body=body,
            correlation_id=correlation_id,
        )

    def issue(
        self,
        body: bytes,
        *,
        correlation_id: str,
        idempotency_key: str,
        causation_id: str | None = None,
    ) -> BridgeResponse:
        return self._send(
            path="/v1/issuances",
            body=body,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
            causation_id=causation_id,
        )

    def query(self, body: bytes, *, correlation_id: str) -> BridgeResponse:
        return self._send(
            path="/v1/queries",
            body=body,
            correlation_id=correlation_id,
        )

    def reconcile(
        self,
        body: bytes,
        *,
        correlation_id: str,
        idempotency_key: str,
        causation_id: str | None = None,
    ) -> BridgeResponse:
        return self._send(
            path="/v1/reconciliations",
            body=body,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
            causation_id=causation_id,
        )

    def _send(
        self,
        *,
        path: str,
        body: bytes,
        correlation_id: str,
        idempotency_key: str | None = None,
        causation_id: str | None = None,
    ) -> BridgeResponse:
        correlation = _required(correlation_id, "correlation_id")
        headers = {
            "Authorization": f"Bearer {self._bearer_secret}",
            "X-FM-Workload-Credential-Id": self._credential_id,
            "X-FM-Host-Namespace": self._host_namespace,
            "X-FM-Tenant-Id": self._tenant_id,
            "X-FM-Unit-Id": self._unit_id,
            "X-FM-Environment": self._environment,
            "X-Correlation-Id": correlation,
            "Content-Type": "application/json",
        }
        if idempotency_key is not None:
            headers["Idempotency-Key"] = _required(idempotency_key, "idempotency_key")
        if causation_id is not None:
            headers["X-Causation-Id"] = _required(causation_id, "causation_id")
        request = BridgeRequest(method="POST", path=path, headers=headers, body=body)
        for attempt in range(1, self._retry_policy.max_attempts + 1):
            try:
                return self._transport.send(request)
            except RetryableTransportError:
                if attempt == self._retry_policy.max_attempts:
                    raise
        raise RuntimeError("unreachable retry state")


def verify_webhook_signature(payload: bytes, *, signature_hex: str, key: bytes) -> bool:
    if not key:
        raise SDKValidationError("webhook key must not be empty")
    signature = signature_hex.strip().lower()
    if not signature:
        return False
    expected = hmac.new(key, payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def _required(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise SDKValidationError(f"{field_name} must not be blank")
    if len(normalized) > 2048:
        raise SDKValidationError(f"{field_name} is too long")
    return normalized
