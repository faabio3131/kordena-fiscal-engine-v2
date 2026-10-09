"""Real persistence, synthetic dispatch: no external delivery certification."""

import os
from datetime import UTC, datetime, timedelta
from threading import Event

import psycopg
import pytest

from kordena_fiscal.application import BackgroundWorkerRuntime, DurableFiscalOutboxWorker
from kordena_fiscal.contingency import (
    FiscalDispatchResult,
    FiscalDispatchStatus,
    FiscalOutboxService,
    FiscalOutboxStatus,
    FiscalRetryPolicy,
    OutboxStateError,
)
from kordena_fiscal.domain import ExecutionScope, FiscalEnvironment
from kordena_fiscal.events import DeliveryAttemptStatus, FiscalInboxService, FiscalInboxStatus
from kordena_fiscal.persistence import SqliteFiscalDatabase
from kordena_fiscal.persistence.postgres import PostgresFiscalDatabase
from kordena_fiscal.persistence.sqlite_outbox_archive import SqliteFiscalOutboxStore

NOW = datetime(2026, 10, 9, tzinfo=UTC)


def postgres_database():
    dsn = os.environ.get("NFCORE_TEST_POSTGRES_DSN", "").strip()
    if not dsn:
        pytest.skip("NFCORE_TEST_POSTGRES_DSN required for real PostgreSQL certification")
    with psycopg.connect(dsn, autocommit=True) as connection:
        connection.execute("DROP SCHEMA public CASCADE")
        connection.execute("CREATE SCHEMA public")
    db = PostgresFiscalDatabase(dsn, min_pool_size=1, max_pool_size=5)
    db.initialize()
    return db


@pytest.fixture(params=["sqlite", "postgres"])
def database(request, tmp_path):
    if request.param == "postgres":
        db = postgres_database()
    else:
        db = SqliteFiscalDatabase(tmp_path / "recovery.sqlite3")
        db.initialize()
    yield db
    if isinstance(db, PostgresFiscalDatabase):
        db.close()


@pytest.fixture
def pg():
    db = postgres_database()
    yield db
    db.close()


def scope():
    return ExecutionScope(
        host_namespace="nfcore",
        tenant_id="tenant-recovery",
        unit_id="unit-recovery",
        environment=FiscalEnvironment.HOMOLOGATION,
        correlation_id="corr-recovery",
    )


def enqueue(db, key="event", created=NOW):
    with db() as uow:
        result = FiscalOutboxService(uow.outbox).enqueue(
            scope=scope(),
            operation="deliver_webhook",
            deduplication_key=key,
            payload=b'{"event":"synthetic"}',
            created_at=created,
        )
        uow.commit()
        return result


def state(db, entry):
    with db() as uow:
        return uow.outbox.get(entry.entry_id), uow.delivery_audit.list_for_entry(entry.entry_id)


class Clock:
    def __init__(self, now=NOW):
        self.value = now

    def now(self):
        return self.value


class Handler:
    def __init__(self, results=None):
        self.calls = []
        self.results = list(results or [])

    def dispatch(self, entry):
        self.calls.append(entry)
        if self.results:
            return self.results.pop(0)
        return FiscalDispatchResult(FiscalDispatchStatus.SUCCEEDED, reference="synthetic-outcome")


def runtime(db, handler, clock, **kwargs):
    return BackgroundWorkerRuntime(
        worker=DurableFiscalOutboxWorker(uow_factory=db, handler=handler),
        clock=clock,
        **kwargs,
    )


def test_retry_backoff_cap_restart_and_terminal_replay(database):
    entry = enqueue(database).entry
    handler = Handler(
        [
            FiscalDispatchResult(FiscalDispatchStatus.RETRYABLE_FAILURE, error="temporary")
            for _ in range(4)
        ]
    )
    policy = FiscalRetryPolicy(
        max_attempts=4,
        initial_delay_seconds=2,
        multiplier=3,
        max_delay_seconds=5,
    )
    instant = NOW
    for attempt, delay in enumerate([2, 5, 5, None], start=1):
        # A fresh worker/runtime has no process-local retry state.
        worker = DurableFiscalOutboxWorker(
            uow_factory=database, handler=handler, retry_policy=policy
        )
        loop = BackgroundWorkerRuntime(worker=worker, clock=Clock(instant))
        result = loop.run_cycle()
        current, audit = state(database, entry)
        assert result.claimed == 1
        assert current.attempt_count == attempt
        assert len(audit) == attempt
        if delay is None:
            assert result.dead_letter == 1
            assert current.status is FiscalOutboxStatus.DEAD_LETTER
            assert audit[-1].status is DeliveryAttemptStatus.DEAD_LETTER
        else:
            assert result.retry_wait == 1
            assert current.available_at == instant + timedelta(seconds=delay)
            assert audit[-1].next_available_at == current.available_at
            assert audit[-1].status is DeliveryAttemptStatus.RETRY_SCHEDULED
            assert (
                runtime(database, handler, Clock(current.available_at - timedelta(microseconds=1)))
                .run_cycle()
                .claimed
                == 0
            )
            instant = current.available_at
    replay = enqueue(database)
    assert replay.replay and replay.entry == current
    assert runtime(database, handler, Clock(NOW + timedelta(days=1))).run_cycle().claimed == 0
    assert len(handler.calls) == 4


def test_success_is_terminal_across_database_reopen(database):
    entry = enqueue(database).entry
    handler = Handler()
    assert runtime(database, handler, Clock()).run_cycle().succeeded == 1
    if isinstance(database, SqliteFiscalDatabase):
        reopened = SqliteFiscalDatabase(database.path)
    else:
        reopened = PostgresFiscalDatabase(os.environ["NFCORE_TEST_POSTGRES_DSN"])
    try:
        reopened.initialize()
        replay = enqueue(reopened)
        assert replay.replay and replay.entry.status is FiscalOutboxStatus.SUCCEEDED
        assert runtime(reopened, handler, Clock(NOW + timedelta(days=1))).run_cycle().claimed == 0
        _, audit = state(reopened, entry)
        assert len(audit) == 1 and audit[0].status is DeliveryAttemptStatus.SUCCEEDED
        assert len(handler.calls) == 1
    finally:
        if isinstance(reopened, PostgresFiscalDatabase):
            reopened.close()


class ProcessLost(BaseException):
    """Injected abrupt process loss, deliberately outside normal handler retries."""


class InboxReceiver:
    """Synthetic recipient; the inbox completion IS its durable test effect."""

    def __init__(self, db, crash=False):
        self.db = db
        self.crash = crash
        self.replays = []
        self.inbox_id = None

    def dispatch(self, entry):
        with self.db() as uow:
            received = FiscalInboxService(uow.inbox).receive(
                scope=entry.scope,
                producer="synthetic-recipient",
                event_id=entry.entry_id,
                event_type="synthetic.received",
                payload=entry.payload,
                occurred_at=entry.created_at,
                received_at=NOW,
            )
            self.replays.append(received.replay)
            self.inbox_id = received.entry.entry_id
            if not received.replay:
                processing = uow.inbox.begin_processing(self.inbox_id, expected_version=0)
                completed = uow.inbox.mark_processed(
                    self.inbox_id,
                    expected_version=processing.version,
                    processed_at=NOW,
                    outcome_reference="synthetic-effect:" + entry.entry_id,
                )
            else:
                completed = received.entry
            assert completed.status is FiscalInboxStatus.PROCESSED
            uow.commit()
        if self.crash:
            raise ProcessLost()
        return FiscalDispatchResult(
            FiscalDispatchStatus.SUCCEEDED, reference=completed.outcome_reference
        )


def test_crash_after_inbox_commit_reclaims_lease_without_duplicate_effect(database):
    entry = enqueue(database).entry
    first = InboxReceiver(database, crash=True)
    with pytest.raises(ProcessLost):
        runtime(database, first, Clock(), lease_duration=timedelta(seconds=5)).run_cycle()
    current, audit = state(database, entry)
    assert current.status is FiscalOutboxStatus.IN_FLIGHT and current.attempt_count == 1
    assert audit[0].status is DeliveryAttemptStatus.CLAIMED
    resumed = InboxReceiver(database)
    assert runtime(database, resumed, Clock(NOW + timedelta(seconds=4))).run_cycle().claimed == 0
    assert resumed.replays == []
    assert runtime(database, resumed, Clock(NOW + timedelta(seconds=5))).run_cycle().succeeded == 1
    final, audit = state(database, entry)
    assert final.attempt_count == 2
    assert [a.status for a in audit] == [
        DeliveryAttemptStatus.LEASE_EXPIRED,
        DeliveryAttemptStatus.SUCCEEDED,
    ]
    assert first.replays == [False] and resumed.replays == [True]
    with database() as uow:
        inbox = uow.inbox.get(first.inbox_id)
        assert inbox.version == 2 and inbox.status is FiscalInboxStatus.PROCESSED
        assert inbox.outcome_reference == final.completion_reference
    assert enqueue(database).replay
    assert runtime(database, resumed, Clock(NOW + timedelta(days=1))).run_cycle().claimed == 0


def test_shutdown_drains_claimed_batch_without_polling_next_batch(database):
    entries = [
        enqueue(database, key=str(i), created=NOW + timedelta(microseconds=i)).entry
        for i in range(3)
    ]
    stop = Event()

    class StopDuringDispatch(Handler):
        def dispatch(self, entry):
            stop.set()
            return super().dispatch(entry)

    handler = StopDuringDispatch()
    loop = runtime(database, handler, Clock(NOW + timedelta(seconds=1)), batch_size=2)
    loop.run_forever(stop)
    assert len(handler.calls) == 2
    assert [state(database, e)[0].status for e in entries] == [
        FiscalOutboxStatus.SUCCEEDED,
        FiscalOutboxStatus.SUCCEEDED,
        FiscalOutboxStatus.PENDING,
    ]
    assert state(database, entries[2])[1] == ()
    assert runtime(database, handler, Clock(NOW + timedelta(seconds=1))).run_cycle().succeeded == 1
    assert len(handler.calls) == 3


def test_pre_requested_shutdown_never_claims(database):
    entry = enqueue(database).entry
    stop = Event()
    stop.set()
    handler = Handler()
    runtime(database, handler, Clock()).run_forever(stop)
    current, audit = state(database, entry)
    assert current.status is FiscalOutboxStatus.PENDING and current.attempt_count == 0
    assert audit == () and handler.calls == []


def test_outbox_and_inbox_creation_roll_back_together(database):
    with database() as uow:
        inbox = (
            FiscalInboxService(uow.inbox)
            .receive(
                scope=scope(),
                producer="synthetic",
                event_id="rollback",
                event_type="synthetic.created",
                payload=b"{}",
                occurred_at=NOW,
                received_at=NOW,
            )
            .entry
        )
        entry = (
            FiscalOutboxService(uow.outbox)
            .enqueue(
                scope=scope(),
                operation="deliver_webhook",
                deduplication_key="rollback",
                payload=b"{}",
                created_at=NOW,
            )
            .entry
        )
    with database() as uow:
        assert uow.inbox.get(inbox.entry_id) is None
        assert uow.outbox.get(entry.entry_id) is None
    assert runtime(database, Handler(), Clock()).run_cycle().claimed == 0


def test_postgres_expired_claim_cannot_overwrite_just_committed_success(pg, monkeypatch):
    entry = enqueue(pg).entry
    handler = Handler()
    owner = DurableFiscalOutboxWorker(uow_factory=pg, handler=handler)
    claimed = owner._claim(now=NOW, limit=1, lease_duration=timedelta(seconds=5))[0]
    original = SqliteFiscalOutboxStore._replace
    raced = False

    def finish_before_claim_write(store, updated, **kwargs):
        nonlocal raced
        if not raced:
            raced = True
            owner._finalize(
                entry=claimed, result=handler.dispatch(claimed), now=NOW + timedelta(seconds=1)
            )
        return original(store, updated, **kwargs)

    monkeypatch.setattr(SqliteFiscalOutboxStore, "_replace", finish_before_claim_write)
    assert runtime(pg, handler, Clock(NOW + timedelta(seconds=5))).run_cycle().claimed == 0
    final, audit = state(pg, entry)
    assert raced and len(handler.calls) == 1
    assert final.status is FiscalOutboxStatus.SUCCEEDED and final.attempt_count == 1
    assert len(audit) == 1 and audit[0].status is DeliveryAttemptStatus.SUCCEEDED


def test_postgres_transition_cannot_overwrite_reclaimed_attempt(pg, monkeypatch):
    entry = enqueue(pg).entry
    handler = Handler()
    owner = DurableFiscalOutboxWorker(uow_factory=pg, handler=handler)
    claimed = owner._claim(now=NOW, limit=1, lease_duration=timedelta(seconds=5))[0]
    original = SqliteFiscalOutboxStore._replace
    raced = False

    def reclaim_before_final_write(store, updated, **kwargs):
        nonlocal raced
        if not raced:
            raced = True
            assert (
                runtime(pg, handler, Clock(NOW + timedelta(seconds=5))).run_cycle().succeeded == 1
            )
        return original(store, updated, **kwargs)

    monkeypatch.setattr(SqliteFiscalOutboxStore, "_replace", reclaim_before_final_write)
    with pytest.raises(OutboxStateError, match="changed during transition"):
        with pg() as uow:
            uow.outbox.mark_succeeded(
                entry.entry_id, expected_attempt=claimed.attempt_count, completion_reference="stale"
            )
            uow.commit()
    final, audit = state(pg, entry)
    assert raced and final.attempt_count == 2 and final.completion_reference == "synthetic-outcome"
    assert [a.status for a in audit] == [
        DeliveryAttemptStatus.LEASE_EXPIRED,
        DeliveryAttemptStatus.SUCCEEDED,
    ]


def test_poll_loop_recovers_transaction_failure_then_processes_bounded_batches(database):
    entries = [enqueue(database, key=str(i)).entry for i in range(5)]
    handler = Handler()
    stop = Event()
    waits = []
    failed = []
    batches = []

    class Observer:
        def cycle_completed(self, result):
            batches.append(result.claimed)

        def cycle_failed(self, *, error_type, elapsed_seconds):
            assert elapsed_seconds >= 0
            failed.append(error_type)

    class OnceUnavailable:
        def __init__(self):
            self.first = True

        def __call__(self):
            if self.first:
                self.first = False
                raise RuntimeError("synthetic persistence outage")
            return database()

    def wait(event, seconds):
        waits.append(seconds)
        if len(waits) == 1:
            assert all(state(database, e)[0].attempt_count == 0 for e in entries)
            assert all(state(database, e)[1] == () for e in entries)
            return False
        event.set()
        return True

    loop = BackgroundWorkerRuntime(
        worker=DurableFiscalOutboxWorker(uow_factory=OnceUnavailable(), handler=handler),
        clock=Clock(),
        observer=Observer(),
        batch_size=2,
        failure_wait_seconds=0.75,
        idle_wait_seconds=0.25,
        wait=wait,
    )
    loop.run_forever(stop)
    assert failed == ["RuntimeError"]
    assert batches == [2, 2, 1, 0]
    assert waits == [0.75, 0.25] and stop.is_set()
    assert len(handler.calls) == 5
    assert all(state(database, e)[0].status is FiscalOutboxStatus.SUCCEEDED for e in entries)


def test_fatal_dispatch_dead_letters_without_retry_or_replay(database):
    entry = enqueue(database).entry
    handler = Handler([FiscalDispatchResult(FiscalDispatchStatus.FATAL_FAILURE, error="poison")])
    assert runtime(database, handler, Clock()).run_cycle().dead_letter == 1
    final, audit = state(database, entry)
    assert final.status is FiscalOutboxStatus.DEAD_LETTER and final.attempt_count == 1
    assert final.lease_until is None and final.last_error == "poison"
    assert len(audit) == 1 and audit[0].status is DeliveryAttemptStatus.DEAD_LETTER
    assert enqueue(database).replay
    assert runtime(database, handler, Clock(NOW + timedelta(days=1))).run_cycle().claimed == 0
    assert len(handler.calls) == 1
