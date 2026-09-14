from __future__ import annotations

from datetime import UTC, datetime

import pytest

from kordena_fiscal.domain import (
    BrazilianJurisdiction,
    ExecutionScope,
    FiscalDocumentKind,
    FiscalEnvironment,
    FiscalValidationError,
)
from kordena_fiscal.gateway import (
    ProviderAuthenticationError,
    ProviderOperation,
    ProviderRejectedError,
    ProviderRequest,
    ProviderResponse,
    ProviderResponseStatus,
    ProviderTransportError,
)
from kordena_fiscal.resilience import (
    CircuitBreakerPolicy,
    CircuitBreakerRegistry,
    CircuitKey,
    CircuitOpenError,
    CircuitState,
    ResilientProviderGateway,
    RetryPolicy,
    UnknownProviderOutcomeError,
)
from kordena_fiscal.signing import FiscalSignatureResult, SignatureAlgorithm

NOW = datetime(2026, 9, 13, 13, 0, tzinfo=UTC)
JURISDICTION = BrazilianJurisdiction("SP")


class _Clock:
    def __init__(self, value: float = 0.0) -> None:
        self.value = value

    def now(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


class _Sleeper:
    def __init__(self) -> None:
        self.delays: list[float] = []

    def sleep(self, seconds: float) -> None:
        self.delays.append(seconds)


class _Jitter:
    def __init__(self, value: float = 0.5) -> None:
        self._value = value

    def value(self) -> float:
        return self._value


class _Executor:
    def __init__(self, scripted: list[ProviderResponse | Exception]) -> None:
        self.scripted = scripted
        self.calls: list[tuple[ProviderRequest, str | None]] = []

    def execute(
        self,
        request: ProviderRequest,
        *,
        provider_id: str | None = None,
    ) -> ProviderResponse:
        self.calls.append((request, provider_id))
        if not self.scripted:
            raise AssertionError("unexpected provider call")
        item = self.scripted.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _scope(
    *,
    environment: FiscalEnvironment = FiscalEnvironment.HOMOLOGATION,
) -> ExecutionScope:
    return ExecutionScope(
        host_namespace="fm.kordena",
        tenant_id="tenant-resilience",
        unit_id="unit-resilience",
        environment=environment,
        correlation_id="corr-resilience",
    )


def _signature() -> FiscalSignatureResult:
    return FiscalSignatureResult(
        signed_content=b"<signed/>",
        signature=b"synthetic-signature",
        algorithm=SignatureAlgorithm.RSA_SHA256,
        certificate_reference_id="ref:fm-fiscal/synthetic/certificate",
        certificate_fingerprint_sha256="a" * 64,
        signed_at=NOW,
        document_kind=FiscalDocumentKind.NFE,
    )


def _request(
    operation: ProviderOperation = ProviderOperation.QUERY,
    *,
    jurisdiction: BrazilianJurisdiction = JURISDICTION,
    environment: FiscalEnvironment = FiscalEnvironment.HOMOLOGATION,
) -> ProviderRequest:
    return ProviderRequest(
        scope=_scope(environment=environment),
        document_kind=FiscalDocumentKind.NFE,
        jurisdiction=jurisdiction,
        operation=operation,
        payload=b"<payload/>",
        correlation_id="corr-resilience",
        workload_id="resilience-worker",
        signed_artifact=_signature() if operation is ProviderOperation.AUTHORIZE else None,
    )


def _response(status: ProviderResponseStatus = ProviderResponseStatus.FOUND) -> ProviderResponse:
    return ProviderResponse(
        provider_id="provider-a",
        operation=ProviderOperation.QUERY,
        status=status,
        correlation_id="corr-resilience",
    )


def _runtime(
    executor: _Executor,
    *,
    clock: _Clock | None = None,
    retry: RetryPolicy | None = None,
    circuit: CircuitBreakerPolicy | None = None,
    sleeper: _Sleeper | None = None,
) -> tuple[ResilientProviderGateway, CircuitBreakerRegistry, _Sleeper, _Clock]:
    actual_clock = clock or _Clock()
    actual_sleeper = sleeper or _Sleeper()
    circuits = CircuitBreakerRegistry(
        policy=circuit or CircuitBreakerPolicy(
            failure_threshold=5,
            recovery_timeout_seconds=10,
        ),
        clock=actual_clock,
    )
    default_retry = RetryPolicy(
        max_attempts=3,
        base_delay_seconds=1,
        max_delay_seconds=4,
    )
    gateway = ResilientProviderGateway(
        executor=executor,
        retry_policy=retry or default_retry,
        circuits=circuits,
        sleeper=actual_sleeper,
        jitter=_Jitter(),
    )
    return gateway, circuits, actual_sleeper, actual_clock


def _key(
    provider_id: str = "provider-a",
    *,
    environment: str = "homologation",
    state_code: str = "SP",
) -> CircuitKey:
    return CircuitKey(
        provider_id=provider_id,
        environment=environment,
        state_code=state_code,
    )


def test_retry_policy_is_bounded_exponential_with_deterministic_jitter() -> None:
    policy = RetryPolicy(
        max_attempts=5,
        base_delay_seconds=2,
        max_delay_seconds=5,
        jitter_ratio=0.5,
    )
    assert policy.delay(1, 0.5) == 2.0
    assert policy.delay(2, 0.5) == 4.0
    assert policy.delay(3, 0.5) == 5.0
    assert policy.delay(1, 0.0) == 1.0
    assert policy.delay(1, 1.0) == 3.0


def test_safe_query_retries_transient_error_then_succeeds_without_real_sleep() -> None:
    executor = _Executor([ProviderTransportError("temporary"), _response()])
    gateway, _, sleeper, _ = _runtime(executor)
    result = gateway.execute(_request(), provider_id="provider-a")
    assert result.status is ProviderResponseStatus.FOUND
    assert len(executor.calls) == 2
    assert sleeper.delays == [1.0]


def test_retry_stops_at_max_attempts() -> None:
    executor = _Executor(
        [
            ProviderTransportError("temporary-1"),
            ProviderTransportError("temporary-2"),
        ]
    )
    retry = RetryPolicy(max_attempts=2, base_delay_seconds=0, max_delay_seconds=0)
    gateway, _, sleeper, _ = _runtime(executor, retry=retry)
    with pytest.raises(ProviderTransportError, match="temporary-2"):
        gateway.execute(_request(), provider_id="provider-a")
    assert len(executor.calls) == 2
    assert sleeper.delays == [0.0]


def test_unknown_authorization_outcome_never_retries_automatically() -> None:
    executor = _Executor(
        [ProviderTransportError("socket closed", delivery_unknown=True), _response()]
    )
    gateway, _, sleeper, _ = _runtime(executor)
    with pytest.raises(UnknownProviderOutcomeError, match="reconciliation") as raised:
        gateway.execute(_request(ProviderOperation.AUTHORIZE), provider_id="provider-a")
    assert raised.value.requires_reconciliation is True
    assert len(executor.calls) == 1
    assert sleeper.delays == []


def test_fiscal_rejection_exception_is_not_retried_or_counted_as_availability() -> None:
    executor = _Executor([ProviderRejectedError("fiscal rejection")])
    gateway, circuits, sleeper, _ = _runtime(
        executor,
        circuit=CircuitBreakerPolicy(failure_threshold=1, recovery_timeout_seconds=10),
    )
    with pytest.raises(ProviderRejectedError, match="fiscal rejection"):
        gateway.execute(_request(), provider_id="provider-a")
    assert len(executor.calls) == 1
    assert sleeper.delays == []
    assert circuits.state(_key()) is CircuitState.CLOSED


def test_normalized_rejected_response_returns_without_retry() -> None:
    executor = _Executor([_response(ProviderResponseStatus.REJECTED), _response()])
    gateway, _, sleeper, _ = _runtime(executor)
    result = gateway.execute(_request(), provider_id="provider-a")
    assert result.status is ProviderResponseStatus.REJECTED
    assert len(executor.calls) == 1
    assert sleeper.delays == []


def test_authentication_error_is_not_retried_and_does_not_trip_circuit() -> None:
    executor = _Executor([ProviderAuthenticationError("authentication failed")])
    gateway, circuits, _, _ = _runtime(
        executor,
        circuit=CircuitBreakerPolicy(failure_threshold=1, recovery_timeout_seconds=10),
    )
    with pytest.raises(ProviderAuthenticationError, match="authentication failed"):
        gateway.execute(_request(), provider_id="provider-a")
    assert circuits.state(_key()) is CircuitState.CLOSED


def test_circuit_opens_after_transient_threshold_and_blocks_calls() -> None:
    executor = _Executor(
        [ProviderTransportError("down-1"), ProviderTransportError("down-2")]
    )
    retry = RetryPolicy(max_attempts=1, base_delay_seconds=0, max_delay_seconds=0)
    gateway, circuits, _, _ = _runtime(
        executor,
        retry=retry,
        circuit=CircuitBreakerPolicy(failure_threshold=2, recovery_timeout_seconds=10),
    )
    with pytest.raises(ProviderTransportError, match="down-1"):
        gateway.execute(_request(), provider_id="provider-a")
    with pytest.raises(ProviderTransportError, match="down-2"):
        gateway.execute(_request(), provider_id="provider-a")
    assert circuits.state(_key()) is CircuitState.OPEN
    with pytest.raises(CircuitOpenError, match="open"):
        gateway.execute(_request(), provider_id="provider-a")
    assert len(executor.calls) == 2


def test_open_circuit_moves_half_open_after_timeout_and_closes_on_probe_success() -> None:
    clock = _Clock()
    executor = _Executor([ProviderTransportError("down"), _response()])
    gateway, circuits, _, _ = _runtime(
        executor,
        clock=clock,
        retry=RetryPolicy(max_attempts=1, base_delay_seconds=0, max_delay_seconds=0),
        circuit=CircuitBreakerPolicy(
            failure_threshold=1,
            recovery_timeout_seconds=10,
            success_threshold=1,
        ),
    )
    with pytest.raises(ProviderTransportError):
        gateway.execute(_request(), provider_id="provider-a")
    assert circuits.state(_key()) is CircuitState.OPEN
    clock.advance(10)
    result = gateway.execute(_request(), provider_id="provider-a")
    assert result.status is ProviderResponseStatus.FOUND
    assert circuits.state(_key()) is CircuitState.CLOSED


def test_circuit_is_partitioned_by_provider_environment_and_jurisdiction() -> None:
    clock = _Clock()
    circuits = CircuitBreakerRegistry(
        policy=CircuitBreakerPolicy(failure_threshold=1, recovery_timeout_seconds=10),
        clock=clock,
    )
    provider_a = _key("provider-a")
    provider_b = _key("provider-b")
    production = _key("provider-a", environment="production")
    rio = _key("provider-a", state_code="RJ")
    circuits.record_failure(provider_a)
    assert circuits.state(provider_a) is CircuitState.OPEN
    assert circuits.state(provider_b) is CircuitState.CLOSED
    assert circuits.state(production) is CircuitState.CLOSED
    assert circuits.state(rio) is CircuitState.CLOSED
    circuits.before_call(provider_b)
    circuits.before_call(production)
    circuits.before_call(rio)


def test_resilience_error_messages_do_not_echo_synthetic_secret_material() -> None:
    secret_marker = "SYNTHETIC-SECRET-MUST-NOT-LEAK"
    executor = _Executor([ProviderTransportError("transport failed")])
    gateway, _, _, _ = _runtime(
        executor,
        retry=RetryPolicy(max_attempts=1, base_delay_seconds=0, max_delay_seconds=0),
    )
    with pytest.raises(ProviderTransportError) as raised:
        gateway.execute(_request(), provider_id="provider-a")
    assert secret_marker not in str(raised.value)


def test_provider_id_is_required_for_circuit_partitioning() -> None:
    executor = _Executor([_response()])
    gateway, _, _, _ = _runtime(executor)
    with pytest.raises(FiscalValidationError, match="provider_id"):
        gateway.execute(_request(), provider_id=" ")
    assert executor.calls == []
