"""Provider-neutral timeout, retry and circuit-breaker runtime for V2-12."""

from __future__ import annotations

import random
import time
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from kordena_fiscal.domain import FiscalDomainError, FiscalValidationError
from kordena_fiscal.gateway import (
    CscUnavailableError,
    ProviderAuthenticationError,
    ProviderCredentialsUnavailableError,
    ProviderGatewayError,
    ProviderOperation,
    ProviderRejectedError,
    ProviderRequest,
    ProviderResponse,
    ProviderResponseStatus,
    ProviderTransportError,
    ProviderUnavailableError,
    UnsupportedJurisdictionError,
    UnsupportedProviderError,
)


class ResilienceError(FiscalDomainError):
    """Base failure for provider resilience coordination."""


class CircuitOpenError(ResilienceError):
    """Provider partition is temporarily blocked by an open circuit."""


class UnknownProviderOutcomeError(ResilienceError):
    """Delivery may have occurred and requires query/reconciliation before retry."""

    requires_reconciliation = True


class RetryMode(StrEnum):
    SAFE_RETRY = "safe_retry"
    CONDITIONAL_RETRY = "conditional_retry"
    NO_AUTOMATIC_RETRY = "no_automatic_retry"


class ProviderErrorClass(StrEnum):
    TRANSIENT = "transient"
    PERMANENT = "permanent"
    AUTHENTICATION = "authentication"
    VALIDATION = "validation"
    FISCAL_REJECTION = "fiscal_rejection"
    UNKNOWN_DELIVERY = "unknown_delivery"


class CircuitState(StrEnum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """Bounded exponential backoff with deterministic injectable jitter."""

    max_attempts: int = 3
    base_delay_seconds: float = 0.25
    max_delay_seconds: float = 5.0
    jitter_ratio: float = 0.2

    def __post_init__(self) -> None:
        if not isinstance(self.max_attempts, int) or isinstance(self.max_attempts, bool):
            raise FiscalValidationError("max_attempts must be an integer")
        if self.max_attempts < 1 or self.max_attempts > 20:
            raise FiscalValidationError("max_attempts must be between 1 and 20")
        for field_name in ("base_delay_seconds", "max_delay_seconds", "jitter_ratio"):
            value = getattr(self, field_name)
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise FiscalValidationError(f"{field_name} must be numeric")
            object.__setattr__(self, field_name, float(value))
        if self.base_delay_seconds < 0:
            raise FiscalValidationError("base_delay_seconds must be >= 0")
        if self.max_delay_seconds < self.base_delay_seconds:
            raise FiscalValidationError("max_delay_seconds must be >= base_delay_seconds")
        if not 0 <= self.jitter_ratio <= 1:
            raise FiscalValidationError("jitter_ratio must be between 0 and 1")

    def delay(self, retry_index: int, jitter_value: float) -> float:
        if retry_index < 1:
            raise FiscalValidationError("retry_index must be >= 1")
        if not 0 <= jitter_value <= 1:
            raise FiscalValidationError("jitter_value must be between 0 and 1")
        base = min(
            self.base_delay_seconds * (2 ** (retry_index - 1)),
            self.max_delay_seconds,
        )
        spread = base * self.jitter_ratio
        shifted = base - spread + (2 * spread * jitter_value)
        return float(min(max(shifted, 0.0), self.max_delay_seconds))


@dataclass(frozen=True, slots=True)
class CircuitBreakerPolicy:
    failure_threshold: int = 3
    recovery_timeout_seconds: float = 30.0
    success_threshold: int = 1

    def __post_init__(self) -> None:
        if (
            not isinstance(self.failure_threshold, int)
            or isinstance(self.failure_threshold, bool)
            or self.failure_threshold < 1
        ):
            raise FiscalValidationError("failure_threshold must be an integer >= 1")
        if (
            not isinstance(self.success_threshold, int)
            or isinstance(self.success_threshold, bool)
            or self.success_threshold < 1
        ):
            raise FiscalValidationError("success_threshold must be an integer >= 1")
        if not isinstance(self.recovery_timeout_seconds, (int, float)) or isinstance(
            self.recovery_timeout_seconds, bool
        ):
            raise FiscalValidationError("recovery_timeout_seconds must be numeric")
        if self.recovery_timeout_seconds <= 0:
            raise FiscalValidationError("recovery_timeout_seconds must be > 0")
        object.__setattr__(
            self,
            "recovery_timeout_seconds",
            float(self.recovery_timeout_seconds),
        )


@dataclass(frozen=True, slots=True)
class CircuitKey:
    provider_id: str
    environment: str
    state_code: str
    municipality_ibge_code: str | None = None

    def __post_init__(self) -> None:
        provider_id = self.provider_id.strip().lower()
        if not provider_id:
            raise FiscalValidationError("provider_id must not be blank")
        object.__setattr__(self, "provider_id", provider_id)
        if not self.environment.strip():
            raise FiscalValidationError("environment must not be blank")
        if not self.state_code.strip():
            raise FiscalValidationError("state_code must not be blank")


class MonotonicClock(Protocol):
    def now(self) -> float: ...


class Sleeper(Protocol):
    def sleep(self, seconds: float) -> None: ...


class JitterSource(Protocol):
    def value(self) -> float: ...


class ProviderExecutor(Protocol):
    def execute(
        self,
        request: ProviderRequest,
        *,
        provider_id: str | None = None,
    ) -> ProviderResponse: ...


class SystemMonotonicClock:
    def now(self) -> float:
        return time.monotonic()


class SystemSleeper:
    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)


class RandomJitterSource:
    def value(self) -> float:
        return random.random()


@dataclass(slots=True)
class _CircuitRecord:
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    opened_at: float | None = None
    half_open_successes: int = 0


class CircuitBreakerRegistry:
    """In-memory circuits partitioned by provider/environment/jurisdiction."""

    def __init__(
        self,
        *,
        policy: CircuitBreakerPolicy,
        clock: MonotonicClock | None = None,
    ) -> None:
        self._policy = policy
        self._clock = clock or SystemMonotonicClock()
        self._records: dict[CircuitKey, _CircuitRecord] = {}

    def state(self, key: CircuitKey) -> CircuitState:
        return self._record(key).state

    def before_call(self, key: CircuitKey) -> None:
        record = self._record(key)
        if record.state is not CircuitState.OPEN:
            return
        if record.opened_at is None:
            raise CircuitOpenError("provider circuit is open")
        if self._clock.now() - record.opened_at < self._policy.recovery_timeout_seconds:
            raise CircuitOpenError("provider circuit is open")
        record.state = CircuitState.HALF_OPEN
        record.half_open_successes = 0

    def record_success(self, key: CircuitKey) -> None:
        record = self._record(key)
        if record.state is CircuitState.HALF_OPEN:
            record.half_open_successes += 1
            if record.half_open_successes < self._policy.success_threshold:
                return
        record.state = CircuitState.CLOSED
        record.failure_count = 0
        record.opened_at = None
        record.half_open_successes = 0

    def record_failure(self, key: CircuitKey) -> None:
        record = self._record(key)
        if record.state is CircuitState.HALF_OPEN:
            self._open(record)
            return
        record.failure_count += 1
        if record.failure_count >= self._policy.failure_threshold:
            self._open(record)

    def _record(self, key: CircuitKey) -> _CircuitRecord:
        return self._records.setdefault(key, _CircuitRecord())

    def _open(self, record: _CircuitRecord) -> None:
        record.state = CircuitState.OPEN
        record.opened_at = self._clock.now()
        record.half_open_successes = 0


def retry_mode(operation: ProviderOperation) -> RetryMode:
    if operation in {ProviderOperation.QUERY, ProviderOperation.STATUS}:
        return RetryMode.SAFE_RETRY
    if operation in {
        ProviderOperation.AUTHORIZE,
        ProviderOperation.CANCEL,
        ProviderOperation.INUTILIZE,
    }:
        return RetryMode.CONDITIONAL_RETRY
    return RetryMode.NO_AUTOMATIC_RETRY


def classify_provider_error(error: Exception) -> ProviderErrorClass:
    if isinstance(error, ProviderTransportError):
        if error.delivery_unknown:
            return ProviderErrorClass.UNKNOWN_DELIVERY
        return ProviderErrorClass.TRANSIENT
    if isinstance(error, ProviderUnavailableError):
        return ProviderErrorClass.TRANSIENT
    if isinstance(
        error,
        (ProviderAuthenticationError, ProviderCredentialsUnavailableError, CscUnavailableError),
    ):
        return ProviderErrorClass.AUTHENTICATION
    if isinstance(
        error,
        (UnsupportedProviderError, UnsupportedJurisdictionError, FiscalValidationError),
    ):
        return ProviderErrorClass.VALIDATION
    if isinstance(error, ProviderRejectedError):
        return ProviderErrorClass.FISCAL_REJECTION
    if isinstance(error, ProviderGatewayError):
        return ProviderErrorClass.PERMANENT
    return ProviderErrorClass.PERMANENT


class ResilientProviderGateway:
    """Apply bounded retries and circuit isolation without repeating unknown authorization."""

    def __init__(
        self,
        *,
        executor: ProviderExecutor,
        retry_policy: RetryPolicy,
        circuits: CircuitBreakerRegistry,
        sleeper: Sleeper | None = None,
        jitter: JitterSource | None = None,
    ) -> None:
        self._executor = executor
        self._retry_policy = retry_policy
        self._circuits = circuits
        self._sleeper = sleeper or SystemSleeper()
        self._jitter = jitter or RandomJitterSource()

    def execute(self, request: ProviderRequest, *, provider_id: str) -> ProviderResponse:
        if not isinstance(request, ProviderRequest):
            raise FiscalValidationError("request must be ProviderRequest")
        normalized_provider = provider_id.strip().lower()
        if not normalized_provider:
            raise FiscalValidationError("provider_id must not be blank")
        key = CircuitKey(
            provider_id=normalized_provider,
            environment=request.scope.environment.value,
            state_code=request.jurisdiction.state_code,
            municipality_ibge_code=request.jurisdiction.municipality_ibge_code,
        )
        mode = retry_mode(request.operation)

        for attempt in range(1, self._retry_policy.max_attempts + 1):
            self._circuits.before_call(key)
            try:
                response = self._executor.execute(
                    request,
                    provider_id=normalized_provider,
                )
            except Exception as error:
                classification = classify_provider_error(error)
                if classification is ProviderErrorClass.UNKNOWN_DELIVERY:
                    self._circuits.record_failure(key)
                    if mode is not RetryMode.SAFE_RETRY:
                        raise UnknownProviderOutcomeError(
                            "provider delivery outcome is unknown; query/reconciliation required"
                        ) from None
                elif classification is ProviderErrorClass.TRANSIENT:
                    self._circuits.record_failure(key)
                else:
                    raise

                if attempt >= self._retry_policy.max_attempts:
                    raise
                delay = self._retry_policy.delay(attempt, self._jitter.value())
                self._sleeper.sleep(delay)
                continue

            self._circuits.record_success(key)
            if response.status is ProviderResponseStatus.REJECTED:
                return response
            return response

        raise ResilienceError("provider retry loop terminated unexpectedly")
