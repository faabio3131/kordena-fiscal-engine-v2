from __future__ import annotations

import os
from datetime import UTC, datetime

import pytest

from kordena_fiscal.contingency import (
    FiscalDispatchResult,
    FiscalDispatchStatus,
    FiscalOutboxEntry,
    FiscalOutboxService,
    FiscalOutboxStatus,
)
from kordena_fiscal.domain import ExecutionScope, FiscalEnvironment, FiscalValidationError
from kordena_fiscal.persistence import SqliteFiscalDatabase
from kordena_fiscal.runtime.config import RuntimeConfigurationError
from kordena_fiscal.runtime.worker_composition import build_production_worker_runtime
from kordena_fiscal.runtime.worker_main import run

NOW = datetime(2026, 9, 16, 16, 0, tzinfo=UTC)


def _scope() -> ExecutionScope:
    return ExecutionScope(
        host_namespace="nfcore",
        tenant_id="tenant-cl02",
        unit_id="unit-cl02",
        environment=FiscalEnvironment.HOMOLOGATION,
        correlation_id="corr-cl02",
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


class _SuccessHandler:
    def dispatch(self, entry: FiscalOutboxEntry) -> FiscalDispatchResult:
        return FiscalDispatchResult(
            FiscalDispatchStatus.SUCCEEDED,
            reference=f"cl02:{entry.entry_id[:12]}",
        )


class _SecretExplodingHandler:
    def dispatch(self, entry: FiscalOutboxEntry) -> FiscalDispatchResult:
        del entry
        raise RuntimeError("password=never-persist-this-value")


def test_production_worker_composition_executes_durable_job_and_emits_metrics(tmp_path) -> None:
    database = SqliteFiscalDatabase(tmp_path / "cl02-worker.sqlite3")
    database.initialize()
    entry = _enqueue(database, operation="deliver_webhook", key="job-1")
    composition = build_production_worker_runtime(
        uow_factory=database,
        handlers={"deliver_webhook": _SuccessHandler()},
        environment="test",
    )

    result = composition.runtime.run_cycle()

    assert composition.operations == frozenset({"deliver_webhook"})
    assert result.claimed == 1
    assert result.succeeded == 1
    with database.unit_of_work() as uow:
        persisted = uow.outbox.get(entry.entry_id)
    assert persisted is not None
    assert persisted.status is FiscalOutboxStatus.SUCCEEDED
    samples = composition.metrics.as_dicts()
    assert {
        (sample["name"], sample["labels"].get("outcome"), sample["value"])
        for sample in samples
        if sample["name"] == "nfcore_worker_jobs_total"
    } >= {
        ("nfcore_worker_jobs_total", "claimed", 1.0),
        ("nfcore_worker_jobs_total", "succeeded", 1.0),
    }


def test_production_worker_composition_rejects_empty_handler_registry(tmp_path) -> None:
    database = SqliteFiscalDatabase(tmp_path / "cl02-empty.sqlite3")
    database.initialize()

    with pytest.raises(FiscalValidationError, match="at least one background handler"):
        build_production_worker_runtime(
            uow_factory=database,
            handlers={},
            environment="test",
        )


def test_unexpected_handler_exception_never_persists_secret_detail(tmp_path) -> None:
    database = SqliteFiscalDatabase(tmp_path / "cl02-secret.sqlite3")
    database.initialize()
    entry = _enqueue(database, operation="deliver_webhook", key="job-secret")
    composition = build_production_worker_runtime(
        uow_factory=database,
        handlers={"deliver_webhook": _SecretExplodingHandler()},
        environment="test",
    )

    result = composition.runtime.run_cycle()

    assert result.retry_wait == 1
    with database.unit_of_work() as uow:
        persisted = uow.outbox.get(entry.entry_id)
        audit = uow.delivery_audit.list_for_entry(entry.entry_id)
    assert persisted is not None
    assert persisted.last_error == "handler exception RuntimeError"
    assert "never-persist-this-value" not in repr(persisted)
    assert len(audit) == 1
    assert audit[0].last_error == "handler exception RuntimeError"


def _configure_staging_worker(monkeypatch: pytest.MonkeyPatch) -> None:
    dsn = os.environ.get("NFCORE_TEST_POSTGRES_DSN", "").strip()
    if not dsn:
        pytest.skip("NFCORE_TEST_POSTGRES_DSN is required for worker entrypoint certification")
    monkeypatch.setenv("NFCORE_ENVIRONMENT", "staging")
    monkeypatch.setenv("NFCORE_PERSISTENCE_BACKEND", "postgres")
    monkeypatch.setenv("DATABASE_URL", dsn)
    monkeypatch.setenv("NFCORE_SECRET_BACKEND", "external")
    monkeypatch.setenv("NFCORE_REQUIRE_HTTPS", "true")


def test_worker_oneshot_is_readiness_only_and_does_not_require_handlers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_staging_worker(monkeypatch)
    monkeypatch.setenv("NFCORE_WORKER_ONESHOT", "true")

    def forbidden_factory(*_args: object) -> dict[str, _SuccessHandler]:
        raise AssertionError("oneshot readiness must not compose or dispatch handlers")

    assert run(handler_factory=forbidden_factory) == 0


def test_continuous_worker_fails_closed_without_explicit_handler_factory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_staging_worker(monkeypatch)
    monkeypatch.delenv("NFCORE_WORKER_ONESHOT", raising=False)

    with pytest.raises(
        RuntimeConfigurationError,
        match="requires an explicitly configured handler factory",
    ):
        run()
