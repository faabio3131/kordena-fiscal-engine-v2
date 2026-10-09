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
from threading import Event

from kordena_fiscal.contingency import FiscalOutboxHandler
from kordena_fiscal.persistence.postgres import PostgresFiscalDatabase

from .config import RuntimeConfigurationError, RuntimeSettings
from .worker_composition import (
    WorkerWebhookDependencies,
    build_canonical_worker_handlers,
    build_production_worker_runtime,
)

_STOP = Event()
WorkerHandlerFactory = Callable[
    [PostgresFiscalDatabase, RuntimeSettings],
    Mapping[str, FiscalOutboxHandler],
]


def _stop(_signum: int, _frame: object) -> None:
    _STOP.set()


def _oneshot_requested() -> bool:
    return os.environ.get("NFCORE_WORKER_ONESHOT", "").strip().lower() == "true"


def run(
    *,
    handler_factory: WorkerHandlerFactory | None = None,
    webhook: WorkerWebhookDependencies | None = None,
) -> int:
    settings = RuntimeSettings.from_environ()
    if settings.persistence_backend != "postgres":
        raise RuntimeConfigurationError("durable worker runtime requires PostgreSQL persistence")
    assert settings.database_url is not None

    database = PostgresFiscalDatabase(settings.database_url)
    try:
        database.initialize()
        with database.connection() as connection:
            connection.execute("SELECT 1").fetchone()

        # This is a dependency/readiness probe only. It must never dispatch fiscal or
        # commercial work and therefore does not require external handler composition.
        if _oneshot_requested():
            return 0

        if handler_factory is not None and webhook is not None:
            raise RuntimeConfigurationError(
                "worker must use one handler composition source"
            )
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

        _STOP.clear()
        signal.signal(signal.SIGTERM, _stop)
        signal.signal(signal.SIGINT, _stop)
        composition.runtime.run_forever(_STOP)
        return 0
    finally:
        database.close()


if __name__ == "__main__":
    raise SystemExit(run())
