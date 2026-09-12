"""Ordering-aware SQLite outbox claim adapter for V2-08."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta
from typing import cast

from kordena_fiscal.contingency import FiscalOutboxEntry, FiscalOutboxStatus
from kordena_fiscal.domain import FiscalValidationError

from ._sqlite_common import iso
from .sqlite_outbox_archive import SqliteFiscalOutboxStore


class SqliteOrderedFiscalOutboxStore(SqliteFiscalOutboxStore):
    """Claim due messages while preserving order only for explicitly keyed streams.

    Entries without an ordering key remain fully independent. For a keyed stream,
    a later entry is not claimable until every earlier entry in the same fiscal
    partition and ordering key reaches SUCCEEDED or DEAD_LETTER.
    """

    def claim_due(
        self,
        *,
        now: datetime,
        limit: int,
        lease_duration: timedelta,
    ) -> tuple[FiscalOutboxEntry, ...]:
        now_iso = iso(now)
        if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
            raise FiscalValidationError("limit must be a positive integer")
        if lease_duration <= timedelta(0):
            raise FiscalValidationError("lease_duration must be positive")
        rows = self._connection.execute(
            """
            SELECT current.entry_id, current.host_namespace, current.tenant_id,
                   current.unit_id, current.environment, current.correlation_id,
                   current.operation, current.deduplication_key, current.payload,
                   current.payload_sha256, current.created_at, current.available_at,
                   current.status, current.attempt_count, current.lease_until,
                   current.last_error, current.completion_reference
            FROM fm_fiscal_outbox AS current
            LEFT JOIN fm_fiscal_outbox_ordering AS current_ordering
              ON current_ordering.entry_id = current.entry_id
            WHERE (
                (current.status IN (?, ?) AND current.available_at <= ?)
                OR (
                    current.status = ? AND current.lease_until IS NOT NULL
                    AND current.lease_until <= ?
                )
            )
            AND (
                current_ordering.ordering_key IS NULL
                OR NOT EXISTS (
                    SELECT 1
                    FROM fm_fiscal_outbox AS previous
                    JOIN fm_fiscal_outbox_ordering AS previous_ordering
                      ON previous_ordering.entry_id = previous.entry_id
                    WHERE previous.host_namespace = current.host_namespace
                      AND previous.tenant_id = current.tenant_id
                      AND previous.unit_id = current.unit_id
                      AND previous.environment = current.environment
                      AND previous_ordering.ordering_key = current_ordering.ordering_key
                      AND previous.status NOT IN (?, ?)
                      AND (
                          previous.created_at < current.created_at
                          OR (
                              previous.created_at = current.created_at
                              AND previous.entry_id < current.entry_id
                          )
                      )
                )
            )
            ORDER BY current.available_at, current.created_at, current.entry_id
            LIMIT ?
            """,
            (
                FiscalOutboxStatus.PENDING.value,
                FiscalOutboxStatus.RETRY_WAIT.value,
                now_iso,
                FiscalOutboxStatus.IN_FLIGHT.value,
                now_iso,
                FiscalOutboxStatus.SUCCEEDED.value,
                FiscalOutboxStatus.DEAD_LETTER.value,
                limit,
            ),
        ).fetchall()
        claimed: list[FiscalOutboxEntry] = []
        for raw in rows:
            entry = self._entry(cast(tuple[object, ...], raw))
            updated = replace(
                entry,
                status=FiscalOutboxStatus.IN_FLIGHT,
                attempt_count=entry.attempt_count + 1,
                lease_until=now + lease_duration,
                last_error=None,
            )
            self._replace(updated)
            claimed.append(updated)
        return tuple(claimed)
