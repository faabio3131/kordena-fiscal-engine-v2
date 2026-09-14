from __future__ import annotations

import os
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Lock

import psycopg
import pytest

from kordena_fiscal.application import DurableFiscalOutboxWorker, RoutedOutboxHandler
from kordena_fiscal.contingency import (
    FiscalDispatchResult,
    FiscalDispatchStatus,
    FiscalOutboxEntry,
    FiscalOutboxService,
    FiscalOutboxStatus,
)
from kordena_fiscal.domain import ExecutionScope, FiscalEnvironment
from kordena_fiscal.persistence.postgres import PostgresFiscalDatabase

NOW = datetime(2026, 9, 14, 21, 45, tzinfo=UTC)
DSN_ENV = "NFCORE_TEST_POSTGRES_DSN"


def _dsn() -> str:
    value = os.environ.get(DSN_ENV, "").strip()
    if not value:
        pytest.skip(f"{DSN_ENV} is required for real PostgreSQL certification")
    return value


@pytest.fixture
def database() -> Iterator[PostgresFiscalDatabase]:
    dsn = _dsn()
    with psycopg.connect(dsn, autocommit=True) as connection:
        connection.execute("DROP SCHEMA public CASCADE")
        connection.execute("CREATE SCHEMA public")
    database = PostgresFiscalDatabase(dsn, min_pool_size=1, max_pool_size=12)
    database.initialize()
    try:
        yield database
    finally:
        database.close()


def _scope() -> ExecutionScope:
    return ExecutionScope(
        host_namespace="nfcore",
        tenant_id="tenant-worker-pg",
        unit_id="unit-worker-pg",
        environment=FiscalEnvironment.HOMOLOGATION,
        correlation_id="corr-worker-pg",
    )


def _enqueue(database: PostgresFiscalDatabase, key: str) -> FiscalOutboxEntry:
    with database.unit_of_work() as uow:
        result = FiscalOutboxService(uow.outbox).enqueue(
            scope=_scope(),
            operation="deliver_webhook",
            deduplication_key=key,
            payload=f'{{"job":"{key}"}}'.encode(),
            created_at=NOW,
        )
        uow.commit()
        return result.entry


class _CountingHandler:
    def __init__(self) -> None:
        self._lock = Lock()
        self.calls = 0

    def dispatch(self, entry: FiscalOutboxEntry) -> FiscalDispatchResult:
        with self._lock:
            self.calls += 1
        return FiscalDispatchResult(
            FiscalDispatchStatus.SUCCEEDED,
            reference=f"pg-delivery:{entry.attempt_count}",
        )


def test_two_postgres_workers_never_dispatch_same_live_lease(
    database: PostgresFiscalDatabase,
) -> None:
    entry = _enqueue(database, "concurrent-job")
    handler = _CountingHandler()
    routed = RoutedOutboxHandler({"deliver_webhook": handler})

    def run(_: int) -> tuple[FiscalOutboxEntry, ...]:
        worker = DurableFiscalOutboxWorker(uow_factory=database, handler=routed)
        return worker.run_once(
            now=NOW,
            limit=1,
            lease_duration=timedelta(seconds=30),
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        batches = list(executor.map(run, range(2)))

    outcomes = [outcome for batch in batches for outcome in batch]
    assert len(outcomes) == 1
    assert handler.calls == 1
    assert outcomes[0].entry_id == entry.entry_id
    assert outcomes[0].status is FiscalOutboxStatus.SUCCEEDED


def test_postgres_worker_recovers_expired_lease_after_crash(
    database: PostgresFiscalDatabase,
) -> None:
    entry = _enqueue(database, "crash-recovery-job")
    with database.unit_of_work() as uow:
        crashed = uow.outbox.claim_due(
            now=NOW,
            limit=1,
            lease_duration=timedelta(seconds=5),
        )[0]
        uow.commit()
    assert crashed.attempt_count == 1

    handler = _CountingHandler()
    worker = DurableFiscalOutboxWorker(
        uow_factory=database,
        handler=RoutedOutboxHandler({"deliver_webhook": handler}),
    )

    assert worker.run_once(now=NOW + timedelta(seconds=4), limit=1) == ()
    recovered = worker.run_once(now=NOW + timedelta(seconds=5), limit=1)[0]

    assert handler.calls == 1
    assert recovered.entry_id == entry.entry_id
    assert recovered.attempt_count == 2
    assert recovered.status is FiscalOutboxStatus.SUCCEEDED
