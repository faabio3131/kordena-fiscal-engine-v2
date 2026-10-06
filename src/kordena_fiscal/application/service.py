"""Universal application service over pure domain rules and durable repositories."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from kordena_fiscal.archive import FiscalArchiveEntry
from kordena_fiscal.contingency import FiscalOutboxEnqueueResult, FiscalOutboxEntry
from kordena_fiscal.domain import (
    ExecutionScope,
    FiscalAccountBinding,
    FiscalEnvironment,
    FiscalValidationError,
    HostScope,
    SourceReference,
)
from kordena_fiscal.events import (
    FiscalInboxEntry,
    FiscalInboxReceiveResult,
    FiscalInboxService,
)
from kordena_fiscal.lifecycle import (
    FiscalDocumentState,
    FiscalStateMachine,
    FiscalStateSnapshot,
    IdempotencyKey,
    IdempotencyReservation,
    IssuanceAttemptStatus,
)
from kordena_fiscal.numbering import (
    FiscalNumberReservation,
    FiscalSequenceKey,
    FiscalSequencePolicy,
)
from kordena_fiscal.operations import FiscalOperationSnapshot
from kordena_fiscal.persistence.ports import (
    FiscalUnitOfWorkFactory,
    PersistenceConflictError,
    PersistenceStateError,
)
from kordena_fiscal.reconciliation import (
    FiscalReconciliationCandidate,
    FiscalReconciliationEngine,
    FiscalReconciliationResult,
)


class IssuanceResumeDisposition(StrEnum):
    """Fail-closed instruction returned after a durable idempotency reservation."""

    FRESH = "fresh"
    AUTHORIZED_REPLAY = "authorized_replay"
    REJECTED_REPLAY = "rejected_replay"
    RECOVERY_REQUIRED = "recovery_required"


@dataclass(frozen=True, slots=True)
class DurableIssuanceReservation:
    reservation: IdempotencyReservation
    lifecycle: FiscalStateSnapshot
    disposition: IssuanceResumeDisposition

    def __post_init__(self) -> None:
        if not isinstance(self.reservation, IdempotencyReservation):
            raise FiscalValidationError("reservation must be IdempotencyReservation")
        if not isinstance(self.lifecycle, FiscalStateSnapshot):
            raise FiscalValidationError("lifecycle must be FiscalStateSnapshot")
        if not isinstance(self.disposition, IssuanceResumeDisposition):
            raise FiscalValidationError("disposition must be IssuanceResumeDisposition")
        if self.lifecycle.document_id != self.reservation.attempt.document_id:
            raise FiscalValidationError("lifecycle and idempotency attempt must share document_id")


class FiscalApplicationService:
    """Host-neutral application boundary with explicit transactional state changes.

    External provider I/O intentionally stays outside these local transactions.
    A retry of a RESERVED attempt is classified as RECOVERY_REQUIRED instead of
    being silently re-issued, which is the V2-07 crash-safety rule.
    """

    def __init__(
        self,
        uow_factory: FiscalUnitOfWorkFactory,
        *,
        state_machine: FiscalStateMachine | None = None,
        reconciliation: FiscalReconciliationEngine | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._state_machine = state_machine or FiscalStateMachine()
        self._reconciliation = reconciliation or FiscalReconciliationEngine()

    def register_binding(self, binding: FiscalAccountBinding) -> FiscalAccountBinding:
        with self._uow_factory() as uow:
            persisted = uow.bindings.add(binding)
            uow.commit()
            return persisted

    def resolve_scope(
        self,
        host_scope: HostScope,
        *,
        environment: FiscalEnvironment,
        correlation_id: str,
    ) -> ExecutionScope:
        with self._uow_factory() as uow:
            try:
                binding = uow.bindings.resolve(host_scope)
            except PersistenceStateError as exc:
                raise FiscalValidationError(
                    "exact durable fiscal binding is required for host scope"
                ) from exc
            return binding.to_execution_scope(
                environment=environment,
                correlation_id=correlation_id,
            )

    def receive_inbox_event(
        self,
        *,
        scope: ExecutionScope,
        producer: str,
        event_id: str,
        event_type: str,
        payload: bytes,
        occurred_at: datetime,
        received_at: datetime,
        causation_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> FiscalInboxReceiveResult:
        """Atomically persist one inbound event before any application processing."""

        with self._uow_factory() as uow:
            result = FiscalInboxService(uow.inbox).receive(
                scope=scope,
                producer=producer,
                event_id=event_id,
                event_type=event_type,
                payload=payload,
                occurred_at=occurred_at,
                received_at=received_at,
                causation_id=causation_id,
                idempotency_key=idempotency_key,
            )
            uow.commit()
            return result

    def begin_inbox_processing(
        self,
        entry_id: str,
        *,
        expected_version: int,
    ) -> FiscalInboxEntry:
        with self._uow_factory() as uow:
            entry = uow.inbox.begin_processing(
                entry_id,
                expected_version=expected_version,
            )
            uow.commit()
            return entry

    def complete_inbox_event(
        self,
        entry_id: str,
        *,
        expected_version: int,
        processed_at: datetime,
        outcome_reference: str | None = None,
    ) -> FiscalInboxEntry:
        with self._uow_factory() as uow:
            entry = uow.inbox.mark_processed(
                entry_id,
                expected_version=expected_version,
                processed_at=processed_at,
                outcome_reference=outcome_reference,
            )
            uow.commit()
            return entry

    def reject_inbox_event(
        self,
        entry_id: str,
        *,
        expected_version: int,
        processed_at: datetime,
        error: str,
    ) -> FiscalInboxEntry:
        with self._uow_factory() as uow:
            entry = uow.inbox.mark_rejected(
                entry_id,
                expected_version=expected_version,
                processed_at=processed_at,
                error=error,
            )
            uow.commit()
            return entry

    def get_inbox_event(self, entry_id: str) -> FiscalInboxEntry | None:
        with self._uow_factory() as uow:
            return uow.inbox.get(entry_id)

    def reserve_issuance(
        self,
        *,
        key: IdempotencyKey,
        request_fingerprint: str,
        document_id: str,
        created_at: datetime,
        scope: ExecutionScope,
    ) -> DurableIssuanceReservation:
        """Atomically persist issuance authority before any provider side effect."""

        if not isinstance(scope, ExecutionScope):
            raise FiscalValidationError("scope must be ExecutionScope")
        with self._uow_factory() as uow:
            reservation = uow.idempotency.reserve(key, request_fingerprint, document_id)
            attempt = reservation.attempt
            lifecycle = uow.lifecycle.get(attempt.document_id)
            if lifecycle is None:
                if reservation.replay:
                    raise PersistenceStateError(
                        "idempotency replay has no durable lifecycle authority"
                    )
                lifecycle = FiscalStateSnapshot.initial(attempt.document_id, created_at)
                uow.lifecycle.add(lifecycle, scope=scope)
            else:
                uow.lifecycle.assert_scope(attempt.document_id, scope)
                if not reservation.replay:
                    raise PersistenceConflictError("document_id already belongs to an issuance")
            disposition = self._disposition(reservation)
            uow.commit()
            return DurableIssuanceReservation(
                reservation=reservation,
                lifecycle=lifecycle,
                disposition=disposition,
            )

    @staticmethod
    def _disposition(reservation: IdempotencyReservation) -> IssuanceResumeDisposition:
        if not reservation.replay:
            return IssuanceResumeDisposition.FRESH
        status = reservation.attempt.status
        if status is IssuanceAttemptStatus.AUTHORIZED:
            return IssuanceResumeDisposition.AUTHORIZED_REPLAY
        if status is IssuanceAttemptStatus.REJECTED:
            return IssuanceResumeDisposition.REJECTED_REPLAY
        return IssuanceResumeDisposition.RECOVERY_REQUIRED

    def transition_lifecycle(
        self,
        document_id: str,
        target: FiscalDocumentState,
        *,
        occurred_at: datetime,
        reason: str,
        correlation_id: str,
    ) -> FiscalStateSnapshot:
        """Apply domain transition first, then persist with optimistic concurrency."""

        with self._uow_factory() as uow:
            current = uow.lifecycle.get(document_id)
            if current is None:
                raise PersistenceStateError("fiscal lifecycle does not exist")
            updated = self._state_machine.transition(
                current,
                target,
                occurred_at=occurred_at,
                reason=reason,
                correlation_id=correlation_id,
            )
            uow.lifecycle.save(updated, expected_version=current.version)
            uow.commit()
            return updated

    def finalize_authorized(
        self,
        *,
        key: IdempotencyKey,
        generation: int,
        document_id: str,
        result_reference: str,
        occurred_at: datetime,
        reason: str,
        correlation_id: str,
    ) -> FiscalStateSnapshot:
        """Atomically couple terminal lifecycle authority and idempotency result."""

        with self._uow_factory() as uow:
            current = uow.lifecycle.get(document_id)
            if current is None:
                raise PersistenceStateError("fiscal lifecycle does not exist")
            updated = self._state_machine.transition(
                current,
                FiscalDocumentState.AUTHORIZED,
                occurred_at=occurred_at,
                reason=reason,
                correlation_id=correlation_id,
            )
            uow.idempotency.mark_authorized(key, generation, result_reference)
            uow.lifecycle.save(updated, expected_version=current.version)
            uow.commit()
            return updated

    def finalize_rejected(
        self,
        *,
        key: IdempotencyKey,
        generation: int,
        document_id: str,
        rejection_reason: str,
        occurred_at: datetime,
        correlation_id: str,
    ) -> FiscalStateSnapshot:
        """Atomically couple terminal rejection and idempotency result."""

        with self._uow_factory() as uow:
            current = uow.lifecycle.get(document_id)
            if current is None:
                raise PersistenceStateError("fiscal lifecycle does not exist")
            updated = self._state_machine.transition(
                current,
                FiscalDocumentState.REJECTED,
                occurred_at=occurred_at,
                reason=rejection_reason,
                correlation_id=correlation_id,
            )
            uow.idempotency.mark_rejected(key, generation, rejection_reason)
            uow.lifecycle.save(updated, expected_version=current.version)
            uow.commit()
            return updated

    def reserve_number(
        self,
        key: FiscalSequenceKey,
        policy: FiscalSequencePolicy | None = None,
    ) -> FiscalNumberReservation:
        with self._uow_factory() as uow:
            reservation = uow.sequences.reserve_next(key, policy or FiscalSequencePolicy())
            uow.commit()
            return reservation

    def enqueue_outbox(self, entry: FiscalOutboxEntry) -> FiscalOutboxEnqueueResult:
        with self._uow_factory() as uow:
            result = uow.outbox.enqueue(entry)
            uow.commit()
            return result

    def archive(self, entry: FiscalArchiveEntry) -> FiscalArchiveEntry:
        with self._uow_factory() as uow:
            result = uow.archive.append(entry)
            uow.commit()
            return result

    def reconcile_operation(
        self,
        operation: FiscalOperationSnapshot,
        candidates: tuple[FiscalReconciliationCandidate, ...],
    ) -> FiscalReconciliationResult:
        result = self._reconciliation.reconcile_operation(operation, candidates)
        with self._uow_factory() as uow:
            uow.reconciliations.save(result)
            uow.commit()
        return result

    def get_reconciliation(
        self,
        scope: ExecutionScope,
        source: SourceReference,
    ) -> FiscalReconciliationResult | None:
        with self._uow_factory() as uow:
            return uow.reconciliations.get(scope, source)
