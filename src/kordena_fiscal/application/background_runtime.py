"""Production-oriented background worker runtime over the durable fiscal outbox.

Critical job state lives in the persistence outbox; this runtime owns only process
lifecycle, handler routing and bounded polling. A process crash loses no authoritative
job state because claims are leases and completion/retry/dead-letter transitions are
persisted by ``DurableFiscalOutboxWorker``.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import Event
from time import monotonic
from typing import Protocol

from kordena_fiscal.contingency import (
    FiscalDispatchResult,
    FiscalDispatchStatus,
    FiscalOutboxEntry,
    FiscalOutboxHandler,
)
from kordena_fiscal.domain import FiscalValidationError

from .outbox_worker import DurableFiscalOutboxWorker


class WorkerClock(Protocol):
    def now(self) -> datetime: ...


class SystemWorkerClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


class WorkerObserver(Protocol):
    def cycle_completed(self, result: BackgroundCycleResult) -> None: ...

    def cycle_failed(self, *, error_type: str, elapsed_seconds: float) -> None: ...


@dataclass(frozen=True, slots=True)
class BackgroundCycleResult:
    claimed: int
    succeeded: int
    retry_wait: int
    dead_letter: int
    elapsed_seconds: float

    def __post_init__(self) -> None:
        for name in ("claimed", "succeeded", "retry_wait", "dead_letter"):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise FiscalValidationError(f"{name} must be a non-negative integer")
        if self.succeeded + self.retry_wait + self.dead_letter != self.claimed:
            raise FiscalValidationError("cycle outcome counters must equal claimed count")
        if self.elapsed_seconds < 0:
            raise FiscalValidationError("elapsed_seconds must be non-negative")


class NullWorkerObserver:
    def cycle_completed(self, result: BackgroundCycleResult) -> None:
        del result

    def cycle_failed(self, *, error_type: str, elapsed_seconds: float) -> None:
        del error_type, elapsed_seconds


class RoutedOutboxHandler:
    """Route durable operations without coupling the fiscal core to a queue product.

    Missing operations are classified as permanent/poison failures instead of being
    retried forever. Individual handlers remain responsible for provider-specific
    transient/fatal classification.
    """

    def __init__(self, handlers: Mapping[str, FiscalOutboxHandler]) -> None:
        normalized: dict[str, FiscalOutboxHandler] = {}
        for operation, handler in handlers.items():
            key = operation.strip().lower()
            if not key:
                raise FiscalValidationError("background operation must not be blank")
            if key in normalized:
                raise FiscalValidationError(f"duplicate background operation: {key}")
            normalized[key] = handler
        if not normalized:
            raise FiscalValidationError("at least one background handler is required")
        self._handlers = normalized

    @property
    def operations(self) -> frozenset[str]:
        return frozenset(self._handlers)

    def dispatch(self, entry: FiscalOutboxEntry) -> FiscalDispatchResult:
        handler = self._handlers.get(entry.operation)
        if handler is None:
            return FiscalDispatchResult(
                FiscalDispatchStatus.FATAL_FAILURE,
                error=f"unsupported background operation: {entry.operation}",
            )
        return handler.dispatch(entry)


class BackgroundWorkerRuntime:
    """Bounded poll loop with graceful shutdown and database-failure isolation."""

    def __init__(
        self,
        *,
        worker: DurableFiscalOutboxWorker,
        clock: WorkerClock | None = None,
        observer: WorkerObserver | None = None,
        batch_size: int = 10,
        lease_duration: timedelta = timedelta(seconds=60),
        idle_wait_seconds: float = 1.0,
        failure_wait_seconds: float = 2.0,
        wait: Callable[[Event, float], bool] | None = None,
    ) -> None:
        if not isinstance(worker, DurableFiscalOutboxWorker):
            raise FiscalValidationError("worker must be DurableFiscalOutboxWorker")
        if not isinstance(batch_size, int) or isinstance(batch_size, bool) or batch_size < 1:
            raise FiscalValidationError("batch_size must be a positive integer")
        if lease_duration <= timedelta(0):
            raise FiscalValidationError("lease_duration must be positive")
        if idle_wait_seconds < 0 or failure_wait_seconds < 0:
            raise FiscalValidationError("worker wait durations must be non-negative")
        self._worker = worker
        self._clock = clock or SystemWorkerClock()
        self._observer = observer or NullWorkerObserver()
        self._batch_size = batch_size
        self._lease_duration = lease_duration
        self._idle_wait = idle_wait_seconds
        self._failure_wait = failure_wait_seconds
        self._wait = wait or (lambda stop, seconds: stop.wait(seconds))

    def _notify(self, method: str, *args: object, **kwargs: object) -> None:
        # Telemetry cannot retry a completed job or terminate the durable poll loop.
        try:
            callback = getattr(self._observer, method, None)
            if callback is not None:
                callback(*args, **kwargs)
        except Exception:
            return

    def run_cycle(self) -> BackgroundCycleResult:
        started = monotonic()
        try:
            outcomes = self._worker.run_once(
                now=self._clock.now(),
                limit=self._batch_size,
                lease_duration=self._lease_duration,
            )
            status_values = [entry.status.value for entry in outcomes]
            result = BackgroundCycleResult(
                claimed=len(outcomes),
                succeeded=status_values.count("succeeded"),
                retry_wait=status_values.count("retry_wait"),
                dead_letter=status_values.count("dead_letter"),
                elapsed_seconds=max(0.0, monotonic() - started),
            )
        except Exception as exc:
            self._notify(
                "cycle_failed",
                error_type=type(exc).__name__,
                elapsed_seconds=max(0.0, monotonic() - started),
            )
            raise
        self._notify("cycle_completed", result)
        return result

    def run_forever(self, stop: Event) -> None:
        """Run until requested to stop; failures never erase durable job state."""

        if not isinstance(stop, Event):
            raise FiscalValidationError("stop must be threading.Event")
        self._notify("worker_started")
        try:
            while not stop.is_set():
                try:
                    result = self.run_cycle()
                except Exception:
                    if self._wait(stop, self._failure_wait):
                        break
                    continue
                if result.claimed == 0 and self._wait(stop, self._idle_wait):
                    break
        finally:
            self._notify("worker_stopped")
