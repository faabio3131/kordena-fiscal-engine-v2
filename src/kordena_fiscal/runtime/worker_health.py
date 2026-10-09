"""Private container readiness over the canonical worker's process-local health.

No DB queries, secrets, tenant projections or HTTP listener. A fresh publisher alone
cannot make a stale/failed poll ready: readiness comes from WorkerObservability.
"""

from __future__ import annotations

import json
import math
import os
import stat
import tempfile
from collections.abc import Callable
from pathlib import Path
from threading import Event, Thread
from time import monotonic

from .observability import WorkerHealth

HEALTH_PATH = Path("/tmp/nfcore-worker-health.json")
PUBLISH_INTERVAL_SECONDS = 1.0
SAMPLE_MAX_AGE_SECONDS = 5.0


class WorkerHealthPublisher:
    """Publish bounded, atomic samples independently of a blocked dispatch/poll.

    The signal handler only sets ``stop``. The publisher observes it and invalidates
    readiness while the runtime drains its already-claimed batch. Publication errors
    never retry durable work; missing/stale samples fail the separate health probe.
    """

    def __init__(self, stop: Event, *, path: Path = HEALTH_PATH) -> None:
        self._stop = stop
        self._path = path
        self._closed = Event()
        self._source: Callable[[], WorkerHealth] | None = None
        self._thread = Thread(target=self._loop, name="nfcore-worker-health", daemon=True)

    def attach(self, source: Callable[[], WorkerHealth]) -> None:
        self._source = source

    def publish(self) -> None:
        source = self._source
        ready = False
        if source is not None:
            try:
                ready = source().ready
            except Exception:
                ready = False
        stopped = self._stop.is_set() or self._closed.is_set()
        record = {
            "version": 1,
            "pid": os.getpid(),
            "sampled_at": monotonic(),
            "ready": ready and not stopped,
            "stopped": stopped,
        }
        fd, temporary = tempfile.mkstemp(prefix=".nfcore-health-", dir=self._path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(record, stream, separators=(",", ":"), allow_nan=False)
            os.replace(temporary, self._path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def _loop(self) -> None:
        while not self._closed.wait(PUBLISH_INTERVAL_SECONDS):
            try:
                self.publish()
            except Exception:
                # Last sample expires; do not expose path/exception details or stop jobs.
                continue

    def start(self) -> None:
        # Invalidate any previous run's file before configuration/database bootstrap.
        # An unwritable health path rejects startup before any work is claimed.
        self.publish()
        self._thread.start()

    def close(self) -> None:
        self._closed.set()
        if self._thread.ident is not None:
            self._thread.join(timeout=2.0)
        try:
            self.publish()
        except Exception:
            pass


def check_worker_health(*, path: Path = HEALTH_PATH) -> bool:
    """Require a live owner process, fresh private sample and canonical readiness."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "rb") as stream:
            info = os.fstat(stream.fileno())
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_uid != os.getuid()
                or info.st_mode & 0o077
                or info.st_size > 1024
            ):
                return False
            record = json.loads(stream.read(1025))
        if not isinstance(record, dict) or set(record) != {
            "version",
            "pid",
            "sampled_at",
            "ready",
            "stopped",
        }:
            return False
        if type(record["version"]) is not int or record["version"] != 1:
            return False
        pid = record["pid"]
        timestamp = record["sampled_at"]
        if type(pid) is not int or pid <= 0:
            return False
        if type(timestamp) not in (int, float) or not math.isfinite(timestamp):
            return False
        if type(record["ready"]) is not bool or type(record["stopped"]) is not bool:
            return False
        age = monotonic() - timestamp
        if not 0 <= age < SAMPLE_MAX_AGE_SECONDS:
            return False
        os.kill(pid, 0)
        return record["ready"] is True and record["stopped"] is False
    except (OSError, ValueError, TypeError, OverflowError):
        return False


if __name__ == "__main__":
    raise SystemExit(0 if check_worker_health() else 1)
