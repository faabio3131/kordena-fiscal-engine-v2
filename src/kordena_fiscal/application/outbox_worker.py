"""Durable V2-08 outbox worker over short-lived persistence transactions."""

from __future__ import annotations

from datetime import datetime, timedelta

from kordena_fiscal.contingency import (
    FiscalDispatchResult,
    FiscalDispatchStatus,
    FiscalOutboxEntry,
    FiscalOutboxHandler,
    FiscalRetryPolicy,
    OutboxStateError,
)
from kordena_fiscal.domain import FiscalValidationError
from kordena_fiscal.persistence.ports import FiscalUnitOfWorkFactory


class DurableFiscalOutboxWorker:
    """Dispatch durable outbox entries without holding a DB transaction over I/O.

    Claim/lease plus audit start are committed before provider/transport I/O.
    Every terminal/retry transition and its audit outcome are committed together
    in a fresh transaction using ``attempt_count`` as the stale-worker fence.
    """

    def __init__(
        self,
        *,
        uow_factory: FiscalUnitOfWorkFactory,
        handler: FiscalOutboxHandler,
        retry_policy: FiscalRetryPolicy | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._handler = handler
        self._policy = retry_policy or FiscalRetryPolicy()

    def run_once(
        self,
        *,
        now: datetime,
        limit: int = 10,
        lease_duration: timedelta = timedelta(seconds=60),
    ) -> tuple[FiscalOutboxEntry, ...]:
        self._validate_clock(now)
        claimed = self._claim(now=now, limit=limit, lease_duration=lease_duration)
        outcomes: list[FiscalOutboxEntry] = []
        for entry in claimed:
            if entry.attempt_count > self._policy.max_attempts:
                outcomes.append(
                    self._dead_letter(
                        entry,
                        "maximum retry attempts exceeded before dispatch",
                        now=now,
                    )
                )
                continue

            try:
                result = self._handler.dispatch(entry)
            except Exception as exc:
                result = FiscalDispatchResult(
                    FiscalDispatchStatus.RETRYABLE_FAILURE,
                    error=self._exception_error(exc),
                )

            if not isinstance(result, FiscalDispatchResult):
                raise OutboxStateError("outbox handler must return FiscalDispatchResult")
            outcomes.append(self._finalize(entry=entry, result=result, now=now))
        return tuple(outcomes)

    def _claim(
        self,
        *,
        now: datetime,
        limit: int,
        lease_duration: timedelta,
    ) -> tuple[FiscalOutboxEntry, ...]:
        with self._uow_factory() as uow:
            claimed = uow.outbox.claim_due(
                now=now,
                limit=limit,
                lease_duration=lease_duration,
            )
            for entry in claimed:
                uow.delivery_audit.expire_prior_attempts(
                    entry.entry_id,
                    before_attempt=entry.attempt_count,
                    expired_at=now,
                )
                uow.delivery_audit.start(entry, started_at=now)
            uow.commit()
            return claimed

    def _finalize(
        self,
        *,
        entry: FiscalOutboxEntry,
        result: FiscalDispatchResult,
        now: datetime,
    ) -> FiscalOutboxEntry:
        if result.status is FiscalDispatchStatus.SUCCEEDED:
            if result.reference is None:
                raise OutboxStateError("successful dispatch result requires reference")
            with self._uow_factory() as uow:
                updated = uow.outbox.mark_succeeded(
                    entry.entry_id,
                    expected_attempt=entry.attempt_count,
                    completion_reference=result.reference,
                )
                uow.delivery_audit.mark_succeeded(
                    entry.entry_id,
                    attempt_count=entry.attempt_count,
                    finished_at=now,
                    outcome_reference=result.reference,
                )
                uow.commit()
                return updated

        if result.error is None:
            raise OutboxStateError("failed dispatch result requires error")
        if (
            result.status is FiscalDispatchStatus.FATAL_FAILURE
            or entry.attempt_count >= self._policy.max_attempts
        ):
            return self._dead_letter(entry, result.error, now=now)

        available_at = now + self._policy.delay_for_attempt(entry.attempt_count)
        with self._uow_factory() as uow:
            updated = uow.outbox.reschedule(
                entry.entry_id,
                expected_attempt=entry.attempt_count,
                available_at=available_at,
                error=result.error,
            )
            uow.delivery_audit.mark_retry_scheduled(
                entry.entry_id,
                attempt_count=entry.attempt_count,
                finished_at=now,
                next_available_at=available_at,
                error=result.error,
            )
            uow.commit()
            return updated

    def _dead_letter(
        self,
        entry: FiscalOutboxEntry,
        error: str,
        *,
        now: datetime,
    ) -> FiscalOutboxEntry:
        with self._uow_factory() as uow:
            updated = uow.outbox.dead_letter(
                entry.entry_id,
                expected_attempt=entry.attempt_count,
                error=error,
            )
            uow.delivery_audit.mark_dead_letter(
                entry.entry_id,
                attempt_count=entry.attempt_count,
                finished_at=now,
                error=error,
            )
            uow.commit()
            return updated

    @staticmethod
    def _validate_clock(now: datetime) -> None:
        if not isinstance(now, datetime):
            raise FiscalValidationError("now must be datetime")
        if now.tzinfo is None or now.utcoffset() is None:
            raise FiscalValidationError("now must be timezone-aware")

    @staticmethod
    def _exception_error(exc: Exception) -> str:
        detail = str(exc).strip() or "no detail"
        message = f"handler exception {type(exc).__name__}: {detail}"
        return message[:1024]
