from dataclasses import replace

import pytest

from kordena_fiscal.domain import (
    ExecutionScope,
    FiscalEnvironment,
    FiscalValidationError,
)
from kordena_fiscal.gateway import (
    AuthorizationRequest,
    AuthorizationResult,
    AuthorizationStatus,
    FakeFiscalGateway,
    FakeGatewayMode,
    FiscalGatewayClient,
    GatewayContractError,
    GatewayProviderMetadata,
)
from kordena_fiscal.lifecycle import IdempotencyKey
from kordena_fiscal.xml import NfeAccessKey

_ACCESS_KEY = NfeAccessKey("35260912345678000195650010000000011123456784")
_OTHER_ACCESS_KEY = NfeAccessKey("35260912345678000195650010000000021123456781")


def _scope(
    *,
    tenant: str = "tenant-a",
    unit: str = "unit-a",
    environment: FiscalEnvironment = FiscalEnvironment.HOMOLOGATION,
) -> ExecutionScope:
    return ExecutionScope(
        tenant_id=tenant,
        unit_id=unit,
        environment=environment,
        correlation_id="corr-gateway-1",
    )


def _request(**overrides: object) -> AuthorizationRequest:
    values: dict[str, object] = {
        "scope": _scope(),
        "access_key": _ACCESS_KEY,
        "signed_xml": b"<synthetic-signed-xml/>",
        "idempotency_key": IdempotencyKey("1" * 64),
        "request_fingerprint": "2" * 64,
    }
    values.update(overrides)
    return AuthorizationRequest(**values)  # type: ignore[arg-type]


def test_authorized_result_is_normalized_and_auditable() -> None:
    request = _request()
    gateway = FakeFiscalGateway(FakeGatewayMode.AUTHORIZE)

    result = FiscalGatewayClient(gateway).authorize(request)

    assert result.status is AuthorizationStatus.AUTHORIZED
    assert result.scope == request.scope
    assert result.access_key == request.access_key
    assert result.idempotency_key == request.idempotency_key
    assert result.request_fingerprint == request.request_fingerprint
    assert result.protocol_reference == "SYNTHETIC-PROTOCOL-1"
    assert result.provider.provider_name == "synthetic-fiscal-gateway"
    assert gateway.calls == (request,)


def test_rejected_result_requires_explicit_code_and_message() -> None:
    result = FiscalGatewayClient(FakeFiscalGateway(FakeGatewayMode.REJECT)).authorize(
        _request()
    )

    assert result.status is AuthorizationStatus.REJECTED
    assert result.protocol_reference is None
    assert result.rejection_code == "SYNTHETIC-REJECTION"
    assert result.rejection_message


def test_pending_result_carries_no_false_authorization_or_rejection() -> None:
    result = FiscalGatewayClient(FakeFiscalGateway(FakeGatewayMode.PENDING)).authorize(
        _request()
    )

    assert result.status is AuthorizationStatus.PENDING
    assert result.protocol_reference is None
    assert result.rejection_code is None
    assert result.rejection_message is None


def test_result_status_invariants_fail_closed() -> None:
    common = {
        "scope": _scope(),
        "access_key": _ACCESS_KEY,
        "idempotency_key": IdempotencyKey("1" * 64),
        "request_fingerprint": "2" * 64,
        "provider": GatewayProviderMetadata("synthetic", "v1"),
    }

    with pytest.raises(FiscalValidationError, match="protocol_reference"):
        AuthorizationResult(
            status=AuthorizationStatus.AUTHORIZED,
            **common,  # type: ignore[arg-type]
        )
    with pytest.raises(FiscalValidationError, match="rejection_code"):
        AuthorizationResult(
            status=AuthorizationStatus.REJECTED,
            **common,  # type: ignore[arg-type]
        )
    with pytest.raises(FiscalValidationError, match="pending"):
        AuthorizationResult(
            status=AuthorizationStatus.PENDING,
            protocol_reference="must-not-exist",
            **common,  # type: ignore[arg-type]
        )


class _MutatingGateway:
    def __init__(self, mutation: str) -> None:
        self._mutation = mutation

    def authorize(self, request: AuthorizationRequest) -> AuthorizationResult:
        result = FakeFiscalGateway().authorize(request)
        if self._mutation == "access_key":
            return replace(result, access_key=_OTHER_ACCESS_KEY)
        if self._mutation == "idempotency":
            return replace(result, idempotency_key=IdempotencyKey("3" * 64))
        if self._mutation == "fingerprint":
            return replace(result, request_fingerprint="4" * 64)
        if self._mutation == "scope":
            return replace(result, scope=_scope(unit="unit-b"))
        raise AssertionError("unknown mutation")


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("access_key", "access key"),
        ("idempotency", "idempotency key"),
        ("fingerprint", "fingerprint"),
        ("scope", "execution scope"),
    ],
)
def test_gateway_client_rejects_adapter_identity_mismatch(
    mutation: str,
    message: str,
) -> None:
    with pytest.raises(GatewayContractError, match=message):
        FiscalGatewayClient(_MutatingGateway(mutation)).authorize(_request())


def test_request_rejects_empty_xml_and_invalid_fingerprint() -> None:
    with pytest.raises(FiscalValidationError, match="signed_xml"):
        _request(signed_xml=b"")
    with pytest.raises(FiscalValidationError, match="request_fingerprint"):
        _request(request_fingerprint="not-a-digest")


def test_fake_gateway_records_each_call_without_reusing_provider_request_id() -> None:
    gateway = FakeFiscalGateway()
    client = FiscalGatewayClient(gateway)
    request = _request()

    first = client.authorize(request)
    second = client.authorize(request)

    assert first.provider_request_id == "fake-request-1"
    assert second.provider_request_id == "fake-request-2"
    assert gateway.calls == (request, request)
