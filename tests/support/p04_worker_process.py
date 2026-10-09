"""CI-only process fixture; never copied into runtime images or production routing.

Real entrypoint/loop/PostgreSQL, synthetic dispatch with no external transport.
"""

import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import psycopg

from kordena_fiscal.contingency import (
    FiscalDispatchResult,
    FiscalDispatchStatus,
    FiscalOutboxService,
    FiscalOutboxStatus,
)
from kordena_fiscal.domain import ExecutionScope, FiscalEnvironment
from kordena_fiscal.persistence.postgres import PostgresFiscalDatabase
from kordena_fiscal.runtime.worker_health import HEALTH_PATH
from kordena_fiscal.runtime.worker_main import run

OPERATION = "p04_process_proof"
SCOPE = ExecutionScope(
    host_namespace="nfcore",
    tenant_id="synthetic-p04-process",
    unit_id="synthetic-unit",
    environment=FiscalEnvironment.HOMOLOGATION,
    correlation_id="synthetic-correlation",
)


def main():
    mode = sys.argv[1]
    health = Path(sys.argv[2]) if len(sys.argv) > 2 else HEALTH_PATH
    state = Path(sys.argv[3]) if len(sys.argv) > 3 else Path("/proof/state")
    if mode in {"reset", "seed", "verify_drained", "verify_finished"}:
        dsn = os.environ["DATABASE_URL"]
        if mode == "reset":
            with psycopg.connect(dsn, autocommit=True) as connection:
                connection.execute("DROP SCHEMA public CASCADE")
                connection.execute("CREATE SCHEMA public")
            return 0
        db = PostgresFiscalDatabase(dsn)
        try:
            db.initialize()
            with db() as uow:
                if mode == "seed":
                    for i in range(13):
                        FiscalOutboxService(uow.outbox).enqueue(
                            scope=SCOPE,
                            operation=OPERATION,
                            deduplication_key=f"p04-process-{i}",
                            payload=b'{"proof":"synthetic"}',
                            created_at=datetime.now(UTC),
                        )
                    uow.commit()
                else:
                    counts = uow.outbox.counts_by_status()
                    expected_done = 10 if mode == "verify_drained" else 13
                    assert counts[FiscalOutboxStatus.SUCCEEDED] == expected_done, counts
                    assert counts[FiscalOutboxStatus.PENDING] == 13 - expected_done, counts
                    for entry in uow.outbox.list_for_scope(SCOPE):
                        if entry.status is FiscalOutboxStatus.SUCCEEDED:
                            assert entry.attempt_count == 1
                            assert len(uow.delivery_audit.list_for_entry(entry.entry_id)) == 1
        finally:
            db.close()
        return 0

    class SyntheticHandler:
        def dispatch(self, entry):
            if mode == "drain":
                (state / "dispatch_started").touch()
                deadline = time.monotonic() + 40
                while not (state / "release").exists():
                    if time.monotonic() >= deadline:
                        raise AssertionError("proof release deadline exceeded")
                    time.sleep(0.05)
            return FiscalDispatchResult(FiscalDispatchStatus.SUCCEEDED, reference="synthetic-proof")

    if mode == "unconfigured":
        return run(health_path=health)
    if mode == "oneshot":
        os.environ["NFCORE_WORKER_ONESHOT"] = "true"
    elif mode not in {"idle", "drain", "restart"}:
        raise ValueError("unsupported proof mode")
    return run(handler_factory=lambda *_: {OPERATION: SyntheticHandler()}, health_path=health)


if __name__ == "__main__":
    raise SystemExit(main())
