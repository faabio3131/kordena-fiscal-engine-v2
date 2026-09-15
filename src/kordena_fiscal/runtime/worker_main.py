"""Container entrypoint for the FM NFCORE worker process.

The process validates production dependencies and remains idle until concrete fiscal
operation handlers are configured by a later externally-authorized integration. It does
not consume or dead-letter unknown jobs merely to appear healthy.
"""

from __future__ import annotations

import os
import signal
from threading import Event

from kordena_fiscal.persistence.postgres import PostgresFiscalDatabase

from .config import RuntimeSettings

_STOP = Event()


def _stop(_signum: int, _frame: object) -> None:
    _STOP.set()


def run() -> int:
    settings = RuntimeSettings.from_environ()
    database: PostgresFiscalDatabase | None = None
    if settings.persistence_backend == "postgres":
        assert settings.database_url is not None
        database = PostgresFiscalDatabase(settings.database_url)
        database.initialize()
        with database.connection() as connection:
            connection.execute("SELECT 1").fetchone()

    if os.environ.get("NFCORE_WORKER_ONESHOT", "").strip().lower() == "true":
        if database is not None:
            database.close()
        return 0

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    try:
        while not _STOP.wait(1.0):
            pass
    finally:
        if database is not None:
            database.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
