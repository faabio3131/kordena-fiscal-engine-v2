from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest

from kordena_fiscal.contingency import (
    FiscalDispatchResult,
    FiscalDispatchStatus,
    FiscalOutboxDispatcher,
    FiscalOutboxEntry,
    FiscalOutboxService,
    FiscalOutboxStatus,
    FiscalRetryPolicy,
    InMemoryFiscalOutboxStore,
    OutboxConflictError,
)
from kordena_fiscal.domain import ExecutionScope, FiscalEnvironment, FiscalValidationError


def _now() -> datetime:
    return datetime(2026, 9, 11, 4, 0, tzinfo=UTC)


def _scope(*, unit: str = "unit-a") -> ExecutionScope:
    return ExecutionScope(
        tenant_id="tenant-a",
        unit_id=unit,
        environment=FiscalEnvironment.HOMOLOGATION,
        correlation_id="corr-fisc-15",
    )


def _service() -> tuple[FiscalOutboxService, InMemoryFiscalOutboxStore]:
    store = InMemoryFiscalOutboxStore()
    return FiscalOutboxService(store), store


class _SequenceHandler:
    def __init__(self, results: list[FiscalDispatchResult]) -> None:
        self._results = list(results)
        self.calls: list[FiscalOutboxEntry] = []

    def dispatch(self, entry: FiscalOutboxEntry) -> FiscalDispatchResult:
        self.calls.append(entry)
        if not self._results:
            raise AssertionError("unexpected dispatch call")
        return self._results.pop(0)


def _enqueue(
    service: FiscalOutboxService,
    *,
    scope: ExecutionScope | None = None,
    key: str = "sale-100:authorize",
    payload: bytes = b"synthetic-signed-xml",
):
    return service.enqueue(
        scope=scope or _scope(),
        operation="nfce_authorize",
        deduplication_key=key,
        payload=payload,
        created_at=_now(),
    )


def test_exact_enqueue_replay_does_not_create_duplicate() -> None:
    service, store = _service()

    first = _enqueue(service)
    replay = _enqueue(service)

    assert first.replay is False
    assert replay.replay is True
    assert replay.entry == first.entry
    assert store.get(first.entry.entry_id) == first.entry


def test_same_deduplication_identity_with_changed_payload_fails_closed() -> None:
    service, _ = _service()
    _enqueue(service, payload=b"payload-a")

    with pytest.raises(OutboxConflictError, match="different content"):
        _enqueue(service, payload=b"payload-b")


def test_concurrent_enqueue_has_one_fresh_reservation_and_one_identity() -> None:
    service, _ = _service()

    with ThreadPoolExecutor(max_workers=16) as pool:
        results = list(pool.map(lambda _: _enqueue(service), range(64)))

    assert sum(not result.replay for result in results) == 1
    assert len({result.entry.entry_id for result in results}) == 1
    assert len({result.entry.payload_sha256 for result in results}) == 1


def test_claim_due_leases_entry_to_only_one_concurrent_worker() -> None:
    service, store = _service()
    entry = _enqueue(service).entry

    def claim_once(_: int):
        return store.claim_due(
            now=_now(),
            limit=1,
            lease_duration=timedelta(seconds=30),
        )

    with ThreadPoolExecutor(max_workers=16) as pool:
        batches = list(pool.map(claim_once, range(32)))

    claimed = [item for batch in batches for item in batch]
    assert len(claimed) == 1
    assert claimed[0].entry_id == entry.entry_id
    assert claimed[0].status is FiscalOutboxStatus.IN_FLIGHT
    assert claimed[0].attempt_count == 1


def test_expired_lease_is_reclaimable_and_increments_attempt_count() -> None:
    service, store = _service()
    _enqueue(service)
    first = store.claim_due(
        now=_now(),
        limit=1,
        lease_duration=timedelta(seconds=10),
    )[0]

    assert store.claim_due(
        now=_now() + timedelta(seconds=9),
        limit=1,
        lease_duration=timedelta(seconds=10),
    ) == ()

    second = store.claim_due(
        now=_now() + timedelta(seconds=10),
        limit=1,
        lease_duration=timedelta(seconds=10),
    )[0]
    assert second.entry_id == first.entry_id
    assert second.attempt_count == 2


def test_success_is_terminal_and_never_claimed_again() -> None:
    service, store = _service()
    entry = _enqueue(service).entry
    handler = _SequenceHandler(
        [FiscalDispatchResult(FiscalDispatchStatus.SUCCEEDED, reference="protocol-1")]
    )
    dispatcher = FiscalOutboxDispatcher(store=store, handler=handler)

    outcome = dispatcher.run_once(now=_now())[0]

    assert outcome.status is FiscalOutboxStatus.SUCCEEDED
    assert outcome.completion_reference == "protocol-1"
    assert outcome.attempt_count == 1
    assert dispatcher.run_once(now=_now() + timedelta(days=1)) == ()
    assert store.get(entry.entry_id) == outcome


def test_retryable_failure_waits_for_deterministic_backoff_then_succeeds() -> None:
    service, store = _service()
    _enqueue(service)
    handler = _SequenceHandler(
        [
            FiscalDispatchResult(
                FiscalDispatchStatus.RETRYABLE_FAILURE,
                error="synthetic transport timeout",
            ),
            FiscalDispatchResult(
                FiscalDispatchStatus.SUCCEEDED,
                reference="protocol-after-retry",
            ),
        ]
    )
    policy = FiscalRetryPolicy(
        max_attempts=3,
        initial_delay_seconds=5,
        multiplier=2,
        max_delay_seconds=30,
    )
    dispatcher = FiscalOutboxDispatcher(
        store=store,
        handler=handler,
        retry_policy=policy,
    )

    first = dispatcher.run_once(now=_now())[0]
    assert first.status is FiscalOutboxStatus.RETRY_WAIT
    assert first.available_at == _now() + timedelta(seconds=5)
    assert first.last_error == "synthetic transport timeout"
    assert dispatcher.run_once(now=_now() + timedelta(seconds=4)) == ()

    second = dispatcher.run_once(now=_now() + timedelta(seconds=5))[0]
    assert second.status is FiscalOutboxStatus.SUCCEEDED
    assert second.attempt_count == 2
    assert second.completion_reference == "protocol-after-retry"
    assert len(handler.calls) == 2


def test_retryable_failure_at_max_attempts_goes_to_dead_letter() -> None:
    service, store = _service()
    _enqueue(service)
    handler = _SequenceHandler(
        [
            FiscalDispatchResult(
                FiscalDispatchStatus.RETRYABLE_FAILURE,
                error="temporary failure 1",
            ),
            FiscalDispatchResult(
                FiscalDispatchStatus.RETRYABLE_FAILURE,
                error="temporary failure 2",
            ),
        ]
    )
    dispatcher = FiscalOutboxDispatcher(
        store=store,
        handler=handler,
        retry_policy=FiscalRetryPolicy(
            max_attempts=2,
            initial_delay_seconds=1,
            multiplier=2,
            max_delay_seconds=10,
        ),
    )

    first = dispatcher.run_once(now=_now())[0]
    assert first.status is FiscalOutboxStatus.RETRY_WAIT

    second = dispatcher.run_once(now=_now() + timedelta(seconds=1))[0]
    assert second.status is FiscalOutboxStatus.DEAD_LETTER
    assert second.attempt_count == 2
    assert second.last_error == "temporary failure 2"
    assert dispatcher.run_once(now=_now() + timedelta(days=1)) == ()


def test_fatal_failure_goes_directly_to_dead_letter() -> None:
    service, store = _service()
    _enqueue(service)
    handler = _SequenceHandler(
        [
            FiscalDispatchResult(
                FiscalDispatchStatus.FATAL_FAILURE,
                error="synthetic non-retryable rejection",
            )
        ]
    )
    dispatcher = FiscalOutboxDispatcher(store=store, handler=handler)

    outcome = dispatcher.run_once(now=_now())[0]

    assert outcome.status is FiscalOutboxStatus.DEAD_LETTER
    assert outcome.last_error == "synthetic non-retryable rejection"
    assert outcome.attempt_count == 1


def test_scope_isolation_produces_distinct_entry_ids() -> None:
    service, _ = _service()

    first = _enqueue(service, scope=_scope(unit="unit-a"))
    second = _enqueue(service, scope=_scope(unit="unit-b"))

    assert first.entry.entry_id != second.entry.entry_id
    assert first.entry.scope.unit_id == "unit-a"
    assert second.entry.scope.unit_id == "unit-b"


def test_naive_datetime_and_bad_payload_digest_are_rejected() -> None:
    service, _ = _service()
    with pytest.raises(FiscalValidationError, match="timezone-aware"):
        service.enqueue(
            scope=_scope(),
            operation="nfce_authorize",
            deduplication_key="sale-100",
            payload=b"payload",
            created_at=datetime(2026, 9, 11, 4, 0),
        )

    with pytest.raises(FiscalValidationError, match="does not match payload"):
        FiscalOutboxEntry(
            entry_id="a" * 64,
            scope=_scope(),
            operation="nfce_authorize",
            deduplication_key="sale-101",
            payload=b"payload",
            payload_sha256="b" * 64,
            created_at=_now(),
            available_at=_now(),
        )


def test_retry_policy_caps_exponential_delay() -> None:
    policy = FiscalRetryPolicy(
        max_attempts=10,
        initial_delay_seconds=5,
        multiplier=3,
        max_delay_seconds=40,
    )

    assert policy.delay_for_attempt(1) == timedelta(seconds=5)
    assert policy.delay_for_attempt(2) == timedelta(seconds=15)
    assert policy.delay_for_attempt(3) == timedelta(seconds=40)
    assert policy.delay_for_attempt(8) == timedelta(seconds=40)
