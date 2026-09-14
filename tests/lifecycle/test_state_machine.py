from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta

import pytest

from kordena_fiscal.domain import FiscalValidationError
from kordena_fiscal.lifecycle import (
    FiscalDocumentState,
    FiscalStateMachine,
    FiscalStateSnapshot,
    FiscalStateTransition,
    InvalidFiscalTransitionError,
)


def _time(minute: int) -> datetime:
    return datetime(2026, 9, 10, 20, minute, tzinfo=UTC)


def _advance(
    snapshot: FiscalStateSnapshot,
    *states: FiscalDocumentState,
) -> FiscalStateSnapshot:
    machine = FiscalStateMachine()
    current = snapshot
    for index, state in enumerate(states, start=1):
        current = machine.transition(
            current,
            state,
            occurred_at=current.updated_at + timedelta(minutes=1),
            reason=f"synthetic transition {index}",
            correlation_id=f"corr-{index}",
        )
    return current


def test_happy_path_reaches_authorized_with_contiguous_audit_history() -> None:
    initial = FiscalStateSnapshot.initial("doc-1", _time(0))
    final = _advance(
        initial,
        FiscalDocumentState.VALIDATING,
        FiscalDocumentState.READY_TO_SIGN,
        FiscalDocumentState.SIGNING,
        FiscalDocumentState.READY_TO_TRANSMIT,
        FiscalDocumentState.TRANSMITTING,
        FiscalDocumentState.AUTHORIZED,
    )

    assert final.state is FiscalDocumentState.AUTHORIZED
    assert final.version == 6
    assert len(final.history) == 6
    assert [transition.sequence for transition in final.history] == list(range(1, 7))
    assert final.history[-1].to_state is FiscalDocumentState.AUTHORIZED


def test_contingency_path_returns_to_transmission() -> None:
    initial = FiscalStateSnapshot.initial("doc-1", _time(0))
    final = _advance(
        initial,
        FiscalDocumentState.VALIDATING,
        FiscalDocumentState.READY_TO_SIGN,
        FiscalDocumentState.SIGNING,
        FiscalDocumentState.READY_TO_TRANSMIT,
        FiscalDocumentState.CONTINGENCY,
        FiscalDocumentState.CONTINGENCY_PENDING,
        FiscalDocumentState.TRANSMITTING,
        FiscalDocumentState.AUTHORIZED,
    )

    assert final.state is FiscalDocumentState.AUTHORIZED


def test_authorized_document_can_be_cancelled_only_through_request_state() -> None:
    authorized = _advance(
        FiscalStateSnapshot.initial("doc-1", _time(0)),
        FiscalDocumentState.VALIDATING,
        FiscalDocumentState.READY_TO_SIGN,
        FiscalDocumentState.SIGNING,
        FiscalDocumentState.READY_TO_TRANSMIT,
        FiscalDocumentState.TRANSMITTING,
        FiscalDocumentState.AUTHORIZED,
    )

    with pytest.raises(InvalidFiscalTransitionError, match="not allowed"):
        FiscalStateMachine().transition(
            authorized,
            FiscalDocumentState.CANCELLED,
            occurred_at=authorized.updated_at + timedelta(minutes=1),
            reason="synthetic direct cancellation",
            correlation_id="corr-cancel",
        )

    cancelled = _advance(
        authorized,
        FiscalDocumentState.CANCEL_REQUESTED,
        FiscalDocumentState.CANCELLED,
    )
    assert cancelled.state is FiscalDocumentState.CANCELLED


def test_cancel_request_can_return_to_authorized_when_cancellation_not_confirmed() -> None:
    authorized = _advance(
        FiscalStateSnapshot.initial("doc-1", _time(0)),
        FiscalDocumentState.VALIDATING,
        FiscalDocumentState.READY_TO_SIGN,
        FiscalDocumentState.SIGNING,
        FiscalDocumentState.READY_TO_TRANSMIT,
        FiscalDocumentState.TRANSMITTING,
        FiscalDocumentState.AUTHORIZED,
    )
    pending = _advance(authorized, FiscalDocumentState.CANCEL_REQUESTED)
    restored = _advance(pending, FiscalDocumentState.AUTHORIZED)

    assert restored.state is FiscalDocumentState.AUTHORIZED


def test_rejected_cancelled_and_error_are_terminal_for_one_attempt() -> None:
    machine = FiscalStateMachine()
    for state in (
        FiscalDocumentState.REJECTED,
        FiscalDocumentState.CANCELLED,
        FiscalDocumentState.ERROR,
    ):
        assert machine.allowed_targets(state) == frozenset()


def test_invalid_shortcut_fails_closed() -> None:
    initial = FiscalStateSnapshot.initial("doc-1", _time(0))

    with pytest.raises(InvalidFiscalTransitionError, match="draft -> authorized"):
        FiscalStateMachine().transition(
            initial,
            FiscalDocumentState.AUTHORIZED,
            occurred_at=_time(1),
            reason="invalid shortcut",
            correlation_id="corr-invalid",
        )


def test_transition_time_cannot_move_backwards() -> None:
    initial = FiscalStateSnapshot.initial("doc-1", _time(1))

    with pytest.raises(FiscalValidationError, match="cannot move backwards"):
        FiscalStateMachine().transition(
            initial,
            FiscalDocumentState.VALIDATING,
            occurred_at=_time(0),
            reason="bad clock",
            correlation_id="corr-clock",
        )


def test_snapshot_rejects_forged_or_inconsistent_history() -> None:
    transition = FiscalStateTransition(
        sequence=1,
        from_state=FiscalDocumentState.DRAFT,
        to_state=FiscalDocumentState.VALIDATING,
        occurred_at=_time(1),
        reason="synthetic",
        correlation_id="corr-1",
    )

    with pytest.raises(FiscalValidationError, match="version must equal"):
        FiscalStateSnapshot(
            document_id="doc-1",
            state=FiscalDocumentState.VALIDATING,
            version=2,
            updated_at=_time(1),
            history=(transition,),
        )

    forged = FiscalStateTransition(
        sequence=1,
        from_state=FiscalDocumentState.DRAFT,
        to_state=FiscalDocumentState.AUTHORIZED,
        occurred_at=_time(1),
        reason="forged",
        correlation_id="corr-forged",
    )
    with pytest.raises(FiscalValidationError, match="invalid transition"):
        FiscalStateSnapshot(
            document_id="doc-1",
            state=FiscalDocumentState.AUTHORIZED,
            version=1,
            updated_at=_time(1),
            history=(forged,),
        )


def test_state_snapshots_are_immutable() -> None:
    snapshot = FiscalStateSnapshot.initial("doc-1", _time(0))

    with pytest.raises(FrozenInstanceError):
        snapshot.state = FiscalDocumentState.ERROR  # type: ignore[misc]
