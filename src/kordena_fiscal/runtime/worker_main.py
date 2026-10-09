"""Container entrypoint for the FM NFCORE worker process.

The worker validates durable production dependencies before doing work. Continuous
execution requires an explicit handler registry; an empty/unconfigured registry fails
closed instead of idling forever or consuming unknown jobs. The CI ``ONESHOT`` probe
continues to validate database/migration readiness without dispatching any operation.
"""

from __future__ import annotations

import os
import signal
from collections.abc import Callable, Mapping
from pathlib import Path
from threading import Event

from kordena_fiscal.contingency import FiscalOutboxHandler
from kordena_fiscal.persistence.postgres import PostgresFiscalDatabase

from .config import RuntimeConfigurationError, RuntimeSettings
from .worker_composition import (
    WorkerWebhookDependencies,
    build_canonical_worker_handlers,
    build_production_worker_runtime,
)
from .worker_health import HEALTH_PATH, WorkerHealthPublisher

WorkerHandlerFactory = Callable[
    [PostgresFiscalDatabase, RuntimeSettings],
    Mapping[str, FiscalOutboxHandler],
]


def _oneshot_requested() -> bool:
    return os.environ.get("NFCORE_WORKER_ONESHOT", "").strip().lower() == "true"


def run(
    *,
    handler_factory: WorkerHandlerFactory | None = None,
    webhook: WorkerWebhookDependencies | None = None,
    health_path: Path = HEALTH_PATH,
) -> int:
    stop = Event()
    publisher = WorkerHealthPublisher(stop, path=health_path)
    previous = {}

    def request_stop(_signum: int, _frame: object) -> None:
        stop.set()

    try:
        # Install before bootstrap and never clear an already received signal.
        for signum in (signal.SIGTERM, signal.SIGINT):
            previous[signum] = signal.signal(signum, request_stop)
        publisher.start()
        settings = RuntimeSettings.from_environ()
        if settings.persistence_backend != "postgres":
            raise RuntimeConfigurationError(
                "durable worker runtime requires PostgreSQL persistence"
            )
        assert settings.database_url is not None

        database = PostgresFiscalDatabase(settings.database_url)
        try:
            database.initialize()
            with database.connection() as connection:
                connection.execute("SELECT 1").fetchone()

            # ONESHOT probes dependencies only and never publishes continuous readiness.
            # A signal received during bootstrap must not be lost or followed by a claim.
            if _oneshot_requested() or stop.is_set():
                return 0

            if handler_factory is not None and webhook is not None:
                raise RuntimeConfigurationError("worker must use one handler composition source")
            handlers = (
                handler_factory(database, settings)
                if handler_factory is not None
                else build_canonical_worker_handlers(uow_factory=database, webhook=webhook)
            )
            composition = build_production_worker_runtime(
                uow_factory=database,
                handlers=handlers,
                environment=settings.environment.value,
            )
            publisher.attach(composition.health)
            composition.runtime.run_forever(stop)
            return 0
        finally:
            database.close()
    finally:
        # Restore caller signal dispositions even after configuration/DB failure.
        try:
            publisher.close()
        finally:
            for signum, handler in previous.items():
                signal.signal(signum, handler)


if __name__ == "__main__":
    raise SystemExit(run())
