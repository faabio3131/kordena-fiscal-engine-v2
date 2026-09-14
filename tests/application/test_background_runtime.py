from __future__ import annotations

from datetime import UTC, datetime, timedelta
from threading import Event

from kordena_fiscal.application import (
    BackgroundCycleResult,
    BackgroundWorkerRuntime,
    DurableFiscalOutboxWorker,
    RoutedOutboxHandler,
)
from kordena_fiscal.contingency import (
    FiscalDispatchResult,
    FiscalDispatchStatus,
    FiscalOutboxEntry,
    FiscalOutboxService,
    FiscalOutboxStatus,
)
from kordena_fiscal.domain import ExecutionScope, FiscalEnvironment
from kordena_fiscal.persistence import SqliteFiscalDatabase

NOW = datetime(2026, 9, 14, 21, 30, tzinfo=UTC)


def _scope() -> ExecutionScope:
    return ExecutionScope(
        host_namespace="nfcore",
        tenant_id="tenant-worker",
        unit_id="unit-worker",
        environment=FiscalEnvironment.HOMOLOGATION,
        correlation_id="corr-worker",
    )


def _enqueue(database: SqliteFiscalDatabase, *, operation: str, key: str) -> FiscalOutboxEntry:
    with database.unit_of_work() as uow:
        result = FiscalOutboxService(uow.outbox).enqueue(
            scope=_scope(),
            operation=operation,
            deduplication_key=key,
            payload=f'{{"job":"{key}"}}'.encode(),
            created_at=NOW,
        )
        uow.commit()
        return result.entry


class _Clock:
    def now(self) -> datetime:
        return NOW


class _SuccessHandler:
    def __init__(self, prefix: str) -> None:
        self.prefix = prefix
        self.calls: list[str] = []

    def dispatch(self, entry: FiscalOutboxEntry) -> FiscalDispatchResult:
        self.calls.append(entry.entry_id)
        return FiscalDispatchResult(
            FiscalDispatchStatus.SUCCEEDED,
            reference=f"{self.prefix}:{entry.entry_id[:12]}",
        )


class _Observer:
    def __init__(self) -> None:
        self.completed: list[BackgroundCycleResult] = []
        self.failed: list[str] = []

    def cycle_completed(self, result: BackgroundCycleResult) -> None:
        self.completed.append(result)

    def cycle_failed(self, *, error_type: str, elapsed_seconds: float) -> None:
        assert elapsed_seconds >= 0
        self.failed.append(error_type)


class _ExplodingWorker(DurableFiscalOutboxWorker):
    def run_once(self, *, now: datetime, limit: int = 10, lease_duration: timedelta = timedelta(seconds=60)) -> tuple[FiscalOutboxEntry, ...]:
        del now, limit, lease_duration
        raise RuntimeError("database unavailable")


def test_runtime_routes_webhook_and_reconciliation_jobs_in_one_bounded_cycle(tmp_path) -> None:
    database = SqliteFiscalDatabase(tmp_path / "worker.sqlite3")
    assert database.initialize() == (1, 2, 3, 4, 5, 6)
    webhook = _SuccessHandler("webhook")
    reconciliation = _SuccessHandler("reconciliation")
    routed = RoutedOutboxHandler(
        {
            "deliver_webhook": webhook,
            "reconciliation": reconciliation,
        }
    )
    _enqueue(database, operation="deliver_webhook", key="event-1")
    _enqueue(database, operation="reconciliation", key="reconcile-1")
    observer = _Observer()
    runtime = BackgroundWorkerRuntime(
        worker=DurableFiscalOutboxWorker(uow_factory=database, handler=routed),
        clock=_Clock(),
        observer=observer,
        batch_size=10,
    )

    result = runtime.run_cycle()

    assert result.claimed == 2
    assert result.succeeded == 2
    assert result.retry_wait == 0
    assert result.dead_letter == 0
    assert len(webhook.calls) == 1
    assert len(reconciliation.calls) == 1
    assert observer.completed == [result]


def test_unknown_operation_is_fail_closed_to_dead_letter(tmp_path) -> None:
    database = SqliteFiscalDatabase(tmp_path / "worker.sqlite3")
    database.initialize()
    entry = _enqueue(database, operation="unknown_job", key="poison-1")
    routed = RoutedOutboxHandler({"deliver_webhook": _SuccessHandler("webhook")})
    runtime = BackgroundWorkerRuntime(
        worker=DurableFiscalOutboxWorker(uow_factory=database, handler=routed),
        clock=_Clock(),
    )

    result = runtime.run_cycle()

    assert result == BackgroundCycleResult(
        claimed=1,
        succeeded=0,
        retry_wait=0,
        dead_letter=1,
        elapsed_seconds=result.elapsed_seconds,
    )
    with database.unit_of_work() as uow:
        persisted = uow.outbox.get(entry.entry_id)
        assert persisted is not None
        assert persisted.status is FiscalOutboxStatus.DEAD_LETTER
        assert persisted.last_error == "unsupported background operation: unknown_job"


def test_run_forever_stops_gracefully_when_stop_is_requested_during_idle_wait(tmp_path) -> None:
    database = SqliteFiscalDatabase(tmp_path / "worker.sqlite3")
    database.initialize()
    routed = RoutedOutboxHandler({"deliver_webhook": _SuccessHandler("webhook")})
    stop = Event()
    waits: list[float] = []

    def wait(event: Event, seconds: float) -> bool:
        waits.append(seconds)
        event.set()
        return True

    runtime = BackgroundWorkerRuntime(
        worker=DurableFiscalOutboxWorker(uow_factory=database, handler=routed),
        clock=_Clock(),
        idle_wait_seconds=0.25,
        wait=wait,
    )

    runtime.run_forever(stop)

    assert stop.is_set()
    assert waits == [0.25]


def test_run_forever_isolates_cycle_failure_and_honors_failure_backoff(tmp_path) -> None:
    database = SqliteFiscalDatabase(tmp_path / "worker.sqlite3")
    database.initialize()
    observer = _Observer()
    stop = Event()
    waits: list[float] = []

    def wait(event: Event, seconds: float) -> bool:
        waits.append(seconds)
        event.set()
        return True

    exploding = _ExplodingWorker(
        uow_factory=database,
        handler=RoutedOutboxHandler({"deliver_webhook": _SuccessHandler("webhook")}),
    )
    runtime = BackgroundWorkerRuntime(
        worker=exploding,
        clock=_Clock(),
        observer=observer,
        failure_wait_seconds=0.5,
        wait=wait,
    )

    runtime.run_forever(stop)

    assert observer.failed == ["RuntimeError"]
    assert waits == [0.5]
    assert stop.is_set()
