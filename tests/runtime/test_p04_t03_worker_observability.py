"""Internal worker metrics over real persistence; no external exporter/deploy proof."""

import json
import os
from datetime import UTC, datetime, timedelta
from threading import Event

import psycopg
import pytest

from kordena_fiscal.application import BackgroundCycleResult
from kordena_fiscal.contingency import (
    FiscalDispatchResult,
    FiscalDispatchStatus,
    FiscalOutboxService,
    FiscalOutboxStatus,
    InMemoryFiscalOutboxStore,
)
from kordena_fiscal.domain import ExecutionScope, FiscalEnvironment
from kordena_fiscal.persistence import SqliteFiscalDatabase
from kordena_fiscal.persistence.postgres import PostgresFiscalDatabase
from kordena_fiscal.persistence.sqlite_outbox_archive import SqliteFiscalOutboxStore
from kordena_fiscal.runtime.observability import (
    MetricsRegistry,
    StructuredLogger,
    WorkerObservability,
)
from kordena_fiscal.runtime.worker_composition import build_production_worker_runtime

NOW = datetime(2026, 10, 9, tzinfo=UTC)
PRIVATE = "synthetic-private-payload-and-error"


@pytest.fixture(params=["sqlite", "postgres"])
def database(request, tmp_path):
    if request.param == "postgres":
        dsn = os.environ.get("NFCORE_TEST_POSTGRES_DSN", "").strip()
        if not dsn:
            pytest.skip("NFCORE_TEST_POSTGRES_DSN required for real PostgreSQL certification")
        with psycopg.connect(dsn, autocommit=True) as conn:
            conn.execute("DROP SCHEMA public CASCADE")
            conn.execute("CREATE SCHEMA public")
        db = PostgresFiscalDatabase(dsn)
    else:
        db = SqliteFiscalDatabase(tmp_path / "observability.sqlite3")
    db.initialize()
    yield db
    if isinstance(db, PostgresFiscalDatabase):
        db.close()


def scope():
    return ExecutionScope(
        host_namespace="nfcore",
        tenant_id="private-tenant",
        unit_id="private-unit",
        environment=FiscalEnvironment.HOMOLOGATION,
        correlation_id="private-correlation",
    )


def enqueue(store, key, now=NOW):
    return (
        FiscalOutboxService(store)
        .enqueue(
            scope=scope(),
            operation="deliver_webhook",
            deduplication_key=key,
            payload=PRIVATE.encode(),
            created_at=now,
        )
        .entry
    )


def put(db, key, now=NOW):
    with db() as uow:
        entry = enqueue(uow.outbox, key, now)
        uow.commit()
        return entry


class Handler:
    def __init__(self, results=None, stop=None):
        self.calls = []
        self.results = list(results or [])
        self.stop = stop

    def dispatch(self, entry):
        self.calls.append(entry)
        if self.stop is not None:
            self.stop.set()
        if self.results:
            return self.results.pop(0)
        return FiscalDispatchResult(FiscalDispatchStatus.SUCCEEDED, reference="synthetic-result")


def composition(db, handler=None):
    return build_production_worker_runtime(
        uow_factory=db,
        handlers={"deliver_webhook": handler or Handler()},
        environment="test",
    )


def metric(metrics, name, outcome=None):
    return next(
        s.value
        for s in metrics.snapshot()
        if s.name == name and (dict(s.labels).get("outcome") == outcome)
    )


def test_durable_counts_cover_all_states_without_mutation_or_payload(database):
    with database() as uow:
        entries = [enqueue(uow.outbox, str(i)) for i in range(4)]
        claimed = uow.outbox.claim_due(now=NOW, limit=4, lease_duration=timedelta(seconds=30))
        assert len(claimed) == 4
        uow.outbox.mark_succeeded(
            entries[0].entry_id, expected_attempt=1, completion_reference="ok"
        )
        uow.outbox.dead_letter(entries[1].entry_id, expected_attempt=1, error="fatal")
        uow.outbox.reschedule(
            entries[2].entry_id,
            expected_attempt=1,
            available_at=NOW + timedelta(seconds=5),
            error="retry",
        )
        pending = enqueue(uow.outbox, "pending")
        uow.commit()
    with database() as uow:
        before = [uow.outbox.get(e.entry_id) for e in [*entries, pending]]
        counts = uow.outbox.counts_by_status()
        after = [uow.outbox.get(e.entry_id) for e in [*entries, pending]]
        assert counts == dict.fromkeys(FiscalOutboxStatus, 1)
        assert before == after
        assert all(uow.delivery_audit.list_for_entry(e.entry_id) == () for e in entries)
    assert PRIVATE not in repr(counts) and "private-tenant" not in repr(counts)


def test_aggregate_backlog_is_not_limited_to_portal_pagination(database):
    with database() as uow:
        for i in range(125):
            enqueue(uow.outbox, str(i), datetime(2099, 1, 1, tzinfo=UTC))
        uow.commit()
    comp = composition(database)
    assert not comp.health().ready
    assert comp.runtime.run_cycle().claimed == 0
    assert metric(comp.metrics, "nfcore_worker_backlog_jobs") == 125
    assert metric(comp.metrics, "nfcore_worker_queue_jobs", "pending") == 125
    assert comp.health().ready
    text = json.dumps(comp.metrics.as_dicts())
    for private in [PRIVATE, "private-tenant", "private-unit", "private-correlation"]:
        assert private not in text
    assert all(set(dict(s.labels)) <= {"outcome"} for s in comp.metrics.snapshot())


def test_outcome_counters_and_current_backlog_agree_with_persistence(database):
    for i in range(3):
        put(database, str(i))
    put(database, "future", datetime(2099, 1, 1, tzinfo=UTC))
    handler = Handler(
        [
            FiscalDispatchResult(FiscalDispatchStatus.SUCCEEDED, reference="ok"),
            FiscalDispatchResult(FiscalDispatchStatus.RETRYABLE_FAILURE, error="temporary"),
            FiscalDispatchResult(FiscalDispatchStatus.FATAL_FAILURE, error="fatal"),
        ]
    )
    comp = composition(database, handler)
    result = comp.runtime.run_cycle()
    assert (result.claimed, result.succeeded, result.retry_wait, result.dead_letter) == (3, 1, 1, 1)
    assert metric(comp.metrics, "nfcore_worker_job_failures_total") == 2
    assert metric(comp.metrics, "nfcore_worker_jobs_total", "claimed") == 3
    assert metric(comp.metrics, "nfcore_worker_jobs_total", "succeeded") == 1
    assert metric(comp.metrics, "nfcore_worker_queue_jobs", "retry_wait") == 1
    assert metric(comp.metrics, "nfcore_worker_queue_jobs", "dead_letter") == 1
    assert metric(comp.metrics, "nfcore_worker_backlog_jobs") == 2
    assert comp.health().ready
    # Poll readiness does not assert that failed jobs or external providers are healthy.
    comp.runtime.run_cycle()
    assert metric(comp.metrics, "nfcore_worker_jobs_total", "claimed") == 3


def test_snapshot_failure_preserves_completed_job_but_invalidates_queue_health(
    database, monkeypatch, capsys
):
    entry = put(database, "one")
    handler = Handler()
    comp = composition(database, handler)
    assert comp.runtime.run_cycle().succeeded == 1
    original = SqliteFiscalOutboxStore.counts_by_status

    def unavailable(_store):
        raise RuntimeError(PRIVATE)

    monkeypatch.setattr(SqliteFiscalOutboxStore, "counts_by_status", unavailable)
    assert comp.runtime.run_cycle().claimed == 0
    assert not comp.health().ready and not comp.health().queue_snapshot_valid
    assert metric(comp.metrics, "nfcore_worker_telemetry_failures_total", "queue") == 1
    assert metric(comp.metrics, "nfcore_worker_ready") == 0
    assert metric(comp.metrics, "nfcore_worker_jobs_total", "succeeded") == 1
    assert PRIVATE not in capsys.readouterr().out
    with database() as uow:
        assert uow.outbox.get(entry.entry_id).status is FiscalOutboxStatus.SUCCEEDED
        assert len(uow.delivery_audit.list_for_entry(entry.entry_id)) == 1
    monkeypatch.setattr(SqliteFiscalOutboxStore, "counts_by_status", original)
    comp.runtime.run_cycle()
    assert comp.health().ready and len(handler.calls) == 1


def test_poll_failure_clears_readiness_and_recovers_without_duplicate_counter(database, capsys):
    failing = False

    def factory():
        if failing:
            raise RuntimeError(PRIVATE)
        return database()

    comp = composition(factory)
    comp.runtime.run_cycle()
    assert comp.health().ready
    failing = True
    with pytest.raises(RuntimeError):
        comp.runtime.run_cycle()
    assert not comp.health().ready
    assert metric(comp.metrics, "nfcore_worker_cycle_failures_total", "failed") == 1
    assert PRIVATE not in capsys.readouterr().out
    failing = False
    comp.runtime.run_cycle()
    assert comp.health().ready
    assert metric(comp.metrics, "nfcore_worker_cycle_failures_total", "failed") == 1


def test_graceful_loop_shutdown_updates_health_without_claiming_again(database):
    entries = [put(database, str(i)) for i in range(3)]
    stop = Event()
    comp = composition(database, Handler(stop=stop))
    comp.runtime._batch_size = 2
    comp.runtime.run_forever(stop)
    assert comp.health().stopped and not comp.health().ready
    assert metric(comp.metrics, "nfcore_worker_ready") == 0
    assert metric(comp.metrics, "nfcore_worker_stopped") == 1
    assert metric(comp.metrics, "nfcore_worker_backlog_jobs") == 1
    with database() as uow:
        statuses = [uow.outbox.get(e.entry_id).status for e in entries]
        assert statuses.count(FiscalOutboxStatus.SUCCEEDED) == 2
        assert statuses.count(FiscalOutboxStatus.PENDING) == 1


def test_logger_failure_does_not_turn_success_into_retry_or_stop_loop(database, monkeypatch):
    put(database, "one")

    def broken(*_args, **_kwargs):
        raise RuntimeError(PRIVATE)

    monkeypatch.setattr(StructuredLogger, "emit", broken)
    comp = composition(database)
    assert comp.runtime.run_cycle().succeeded == 1
    assert comp.health().ready
    assert comp.runtime.run_cycle().claimed == 0
    assert metric(comp.metrics, "nfcore_worker_telemetry_failures_total", "log") == 2
    assert metric(comp.metrics, "nfcore_worker_jobs_total", "succeeded") == 1


def test_arbitrary_observer_failure_does_not_break_completion_or_failure_wait(
    database, monkeypatch
):
    put(database, "one")
    comp = composition(database)

    def broken(*_args, **_kwargs):
        raise RuntimeError(PRIVATE)

    monkeypatch.setattr(comp.observer, "cycle_completed", broken)
    assert comp.runtime.run_cycle().succeeded == 1
    assert comp.runtime.run_cycle().claimed == 0
    monkeypatch.setattr(comp.observer, "cycle_failed", broken)
    monkeypatch.setattr(comp.runtime._worker, "run_once", broken)
    waits = []
    stop = Event()

    def wait(event, seconds):
        waits.append(seconds)
        event.set()
        return True

    comp.runtime._wait = wait
    comp.runtime.run_forever(stop)
    assert waits == [2.0] and stop.is_set() and comp.health().stopped


def test_readiness_is_fresh_on_collection_idle_failure_restart_and_stop():
    now = [0.0]
    metrics = MetricsRegistry()
    obs = WorkerObservability(
        metrics=metrics,
        logger=StructuredLogger(service="worker", environment="test", sink=lambda _: None),
        clock=lambda: now[0],
        heartbeat_timeout_seconds=10,
        queue_counts=lambda: dict.fromkeys(FiscalOutboxStatus, 0),
    )
    assert metric(metrics, "nfcore_worker_ready") == 0
    assert metric(metrics, "nfcore_worker_heartbeat_observed") == 0
    result = BackgroundCycleResult(0, 0, 0, 0, 0)
    obs.cycle_completed(result)
    assert metric(metrics, "nfcore_worker_ready") == 1
    now[0] = 9.9
    assert obs.health().ready
    now[0] = 10
    assert metric(metrics, "nfcore_worker_ready") == 0
    assert metric(metrics, "nfcore_worker_heartbeat_age_seconds") == 10
    obs.cycle_completed(result)
    assert obs.health().ready
    obs.cycle_failed(error_type="RuntimeError", elapsed_seconds=0)
    assert not obs.health().ready
    obs.cycle_completed(result)
    assert obs.health().ready
    obs.worker_stopped()
    assert metric(metrics, "nfcore_worker_ready") == 0
    obs.worker_started()
    assert not obs.health().ready and obs.health().last_success_age_seconds is None
    obs.cycle_completed(result)
    assert obs.health().ready


@pytest.mark.parametrize("timeout", [0, -1, float("nan"), float("inf")])
def test_invalid_heartbeat_timeout_rejected(timeout):
    with pytest.raises(ValueError, match="heartbeat timeout"):
        WorkerObservability(
            metrics=MetricsRegistry(),
            logger=StructuredLogger(service="test", environment="test"),
            heartbeat_timeout_seconds=timeout,
        )


@pytest.mark.parametrize("value", [-1, float("nan"), float("inf")])
def test_invalid_gauge_rejected(value):
    with pytest.raises(ValueError, match="gauge"):
        MetricsRegistry().set_gauge("invalid", value)


def test_gauge_replaces_values_and_rejects_private_labels():
    metrics = MetricsRegistry()
    metrics.set_gauge("backlog", 4)
    metrics.set_gauge("backlog", 1)
    assert metric(metrics, "backlog") == 1
    with pytest.raises(ValueError, match="high-cardinality"):
        metrics.set_gauge("unsafe", 1, tenant_id="private-tenant")


def test_reference_memory_counts_follow_existing_transitions():
    store = InMemoryFiscalOutboxStore()
    assert store.counts_by_status() == dict.fromkeys(FiscalOutboxStatus, 0)
    entry = enqueue(store, "one")
    assert store.counts_by_status()[FiscalOutboxStatus.PENDING] == 1
    store.claim_due(now=NOW, limit=1, lease_duration=timedelta(seconds=5))
    store.mark_succeeded(entry.entry_id, expected_attempt=1, completion_reference="ok")
    assert store.counts_by_status()[FiscalOutboxStatus.SUCCEEDED] == 1


def test_restart_reconstructs_durable_counts_without_replaying_success(database):
    put(database, "done")
    first = composition(database)
    assert first.runtime.run_cycle().succeeded == 1
    put(database, "future", datetime(2099, 1, 1, tzinfo=UTC))
    handler = Handler()
    restarted = composition(database, handler)
    assert not restarted.health().ready
    assert restarted.runtime.run_cycle().claimed == 0
    assert handler.calls == []
    assert metric(restarted.metrics, "nfcore_worker_jobs_total", "succeeded") == 0
    assert metric(restarted.metrics, "nfcore_worker_queue_jobs", "succeeded") == 1
    assert metric(restarted.metrics, "nfcore_worker_backlog_jobs") == 1
    assert restarted.health().ready


def test_collecting_health_metrics_never_requeries_database():
    calls = []

    def counts():
        calls.append(1)
        return dict.fromkeys(FiscalOutboxStatus, 0)

    metrics = MetricsRegistry()
    obs = WorkerObservability(
        metrics=metrics,
        logger=StructuredLogger(service="test", environment="test", sink=lambda _: None),
        queue_counts=counts,
    )
    obs.cycle_completed(BackgroundCycleResult(0, 0, 0, 0, 0))
    for _ in range(4):
        metrics.as_dicts()
        obs.health()
    assert calls == [1]


@pytest.mark.parametrize(
    "counts", [{}, dict.fromkeys(FiscalOutboxStatus, -1), dict.fromkeys(FiscalOutboxStatus, True)]
)
def test_malformed_snapshot_cannot_promote_readiness(counts):
    metrics = MetricsRegistry()
    obs = WorkerObservability(
        metrics=metrics,
        logger=StructuredLogger(service="test", environment="test", sink=lambda _: None),
        queue_counts=lambda: counts,
    )
    obs.cycle_completed(BackgroundCycleResult(0, 0, 0, 0, 0))
    assert metric(metrics, "nfcore_worker_ready") == 0
    assert metric(metrics, "nfcore_worker_queue_snapshot_valid") == 0
    assert metric(metrics, "nfcore_worker_telemetry_failures_total", "queue") == 1
