"""Durable, replica-safe admission control for anonymous commercial trials.

Requires the separately governed PostgreSQL table described by SCHEMA.
The gate never creates or migrates it at application startup. Missing schema
or database errors deny admission; no implicit in-memory downgrade.
"""

from __future__ import annotations

import hashlib
from contextlib import AbstractContextManager
from datetime import datetime
from typing import Protocol

from kordena_fiscal.persistence.public_trial_rate_schema import PUBLIC_TRIAL_RATE_SCHEMA

SCHEMA = PUBLIC_TRIAL_RATE_SCHEMA[0]


class RowReader(Protocol):
    def fetchone(self) -> tuple[object, ...] | None: ...


class SqlConnection(Protocol):
    def execute(
        self, statement: str, parameters: tuple[object, ...] = ()
    ) -> RowReader: ...


class ConnectionFactory(Protocol):
    def __call__(self) -> AbstractContextManager[SqlConnection]: ...


class PostgresPublicTrialAbuseGate:
    """Count one remote identity atomically across API replicas.

    Every request uses PostgreSQL's upsert under a unique bucket key. A
    rejected increment is not counted. Old windows are removable by a
    governed retention job; no cleanup DDL is performed here.
    """

    def __init__(
        self,
        connection_factory: ConnectionFactory,
        *,
        max_requests: int = 3,
        window_seconds: int = 3600,
        scope_prefix: str = "public-trial",
    ) -> None:
        if max_requests < 1 or window_seconds < 1:
            raise ValueError("public trial limits must be positive")
        if not scope_prefix:
            raise ValueError("scope_prefix must be non-blank")
        self._connection_factory = connection_factory
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._scope_prefix = scope_prefix

    def allow(self, identity: str, now: datetime) -> bool:
        if not identity or now.tzinfo is None or now.utcoffset() is None:
            return False
        scope = hashlib.sha256(
            (self._scope_prefix + ":" + identity).encode("utf-8")
        ).hexdigest()
        window = int(now.timestamp()) // self._window_seconds
        statement = """
            INSERT INTO fm_public_trial_rate_windows (scope_key, window_start, hits)
            VALUES (?, ?, 1)
            ON CONFLICT (scope_key, window_start)
            DO UPDATE SET hits = fm_public_trial_rate_windows.hits + 1
            WHERE fm_public_trial_rate_windows.hits < ?
            RETURNING hits
        """
        try:
            with self._connection_factory() as connection:
                row = connection.execute(
                    statement,
                    (scope, window, self._max_requests),
                ).fetchone()
            return row is not None
        except Exception:
            # No silent downgrade to a process-local limiter.
            return False
