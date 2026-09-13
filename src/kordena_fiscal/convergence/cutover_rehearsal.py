"""Synthetic cutover rehearsal for governed authority transfer.

This module never executes production effects. It models the ordering, evidence,
and rollback invariants required before a human-authorized real cutover.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .readiness import CutoverReadinessMatrix


class CutoverRehearsalError(ValueError):
    """Raised when a rehearsal transition violates a cutover invariant."""


class ProductionEffectForbiddenError(CutoverRehearsalError):
    """Raised if rehearsal code is asked to perform a production effect."""


class CutoverStage(StrEnum):
    PRECHECK = "precheck"
    FREEZE_REQUESTED = "freeze_requested"
    WRITERS_FROZEN = "writers_frozen"
    SNAPSHOT_CAPTURED = "snapshot_captured"
    MIGRATION_VALIDATED = "migration_validated"
    MIGRATION_APPLIED = "migration_applied"
    RECONCILIATION_VALIDATED = "reconciliation_validated"
    AUTHORITY_TRANSFER_READY = "authority_transfer_ready"
    V2_AUTHORITY_ACTIVE = "v2_authority_active"
    POST_TRANSFER_VALIDATION = "post_transfer_validation"
    CLOSED = "closed"
    ABORT = "abort"
    ROLLBACK_REQUIRED = "rollback_required"
    ROLLBACK_IN_PROGRESS = "rollback_in_progress"
    ROLLED_BACK = "rolled_back"


@dataclass(frozen=True, slots=True)
class WriterStatus:
    writer_id: str
    authority: str
    frozen: bool

    def __post_init__(self) -> None:
        if not self.writer_id.strip():
            raise CutoverRehearsalError("writer_id must not be blank")
        if not self.authority.strip():
            raise CutoverRehearsalError("authority must not be blank")


@dataclass(frozen=True, slots=True)
class CutoverInvariantEvidence:
    sequence_safe: bool
    idempotency_preserved: bool
    inbox_outbox_reconciled: bool
    unknown_outcomes: int
    archive_integrity: bool
    lifecycle_integrity: bool
    bindings_integrity: bool
    readiness_promoted_by_migration: bool
    provider_state_preserved: bool
    audit_complete: bool

    def __post_init__(self) -> None:
        if self.unknown_outcomes < 0:
            raise CutoverRehearsalError("unknown_outcomes must be non-negative")

    @property
    def blockers(self) -> tuple[str, ...]:
        blockers: list[str] = []
        checks = (
            (self.sequence_safe, "sequence"),
            (self.idempotency_preserved, "idempotency"),
            (self.inbox_outbox_reconciled, "inbox_outbox"),
            (self.archive_integrity, "archive"),
            (self.lifecycle_integrity, "lifecycle"),
            (self.bindings_integrity, "bindings"),
            (self.provider_state_preserved, "provider_state"),
            (self.audit_complete, "audit"),
        )
        blockers.extend(name for ok, name in checks if not ok)
        if self.unknown_outcomes:
            blockers.append("unknown_outcomes")
        if self.readiness_promoted_by_migration:
            blockers.append("readiness_promotion")
        return tuple(blockers)

    def require_safe(self) -> None:
        if self.blockers:
            raise CutoverRehearsalError(
                "cutover invariants are not satisfied: " + ", ".join(self.blockers)
            )


@dataclass(frozen=True, slots=True)
class CutoverRehearsalCheckpoint:
    rehearsal_id: str
    stage: CutoverStage
    snapshot_id: str | None
    audit_log: tuple[str, ...]


class CutoverRehearsal:
    """Fail-closed synthetic state machine for an eventual authority transfer."""

    def __init__(self, rehearsal_id: str) -> None:
        if not rehearsal_id.strip():
            raise CutoverRehearsalError("rehearsal_id must not be blank")
        self.rehearsal_id = rehearsal_id.strip()
        self.stage = CutoverStage.PRECHECK
        self.snapshot_id: str | None = None
        self._audit_log: list[str] = ["rehearsal_created"]

    @property
    def audit_log(self) -> tuple[str, ...]:
        return tuple(self._audit_log)

    def _require_stage(self, expected: CutoverStage) -> None:
        if self.stage is not expected:
            raise CutoverRehearsalError(
                f"transition requires {expected.value}; current stage is {self.stage.value}"
            )

    def _advance(self, stage: CutoverStage, event: str) -> None:
        self.stage = stage
        self._audit_log.append(event)

    def complete_precheck(self, readiness: CutoverReadinessMatrix) -> None:
        self._require_stage(CutoverStage.PRECHECK)
        readiness.require_cutover_ready()
        self._advance(CutoverStage.FREEZE_REQUESTED, "precheck_passed")

    def confirm_writers_frozen(
        self,
        writers: tuple[WriterStatus, ...],
        *,
        future_authority: str,
    ) -> None:
        self._require_stage(CutoverStage.FREEZE_REQUESTED)
        if not writers:
            raise CutoverRehearsalError("writer inventory must not be empty")
        authority = future_authority.strip()
        if not authority:
            raise CutoverRehearsalError("future_authority must not be blank")
        unexpected = tuple(
            writer.writer_id
            for writer in writers
            if writer.authority != authority and not writer.frozen
        )
        if unexpected:
            raise CutoverRehearsalError(
                "legacy writers remain active: " + ", ".join(sorted(unexpected))
            )
        self._advance(CutoverStage.WRITERS_FROZEN, "writers_frozen")

    def capture_snapshot(self, snapshot_id: str, *, consistent: bool) -> None:
        self._require_stage(CutoverStage.WRITERS_FROZEN)
        if not snapshot_id.strip():
            raise CutoverRehearsalError("snapshot_id must not be blank")
        if not consistent:
            raise CutoverRehearsalError("snapshot is inconsistent")
        self.snapshot_id = snapshot_id.strip()
        self._advance(CutoverStage.SNAPSHOT_CAPTURED, "snapshot_captured")

    def validate_migration(self, *, conflict_free: bool, deterministic: bool) -> None:
        self._require_stage(CutoverStage.SNAPSHOT_CAPTURED)
        if not conflict_free:
            raise CutoverRehearsalError("migration validation detected a conflict")
        if not deterministic:
            raise CutoverRehearsalError("migration validation is not deterministic")
        self._advance(CutoverStage.MIGRATION_VALIDATED, "migration_validated")

    def apply_synthetic_migration(self, *, production_effect: bool = False) -> None:
        self._require_stage(CutoverStage.MIGRATION_VALIDATED)
        if production_effect:
            raise ProductionEffectForbiddenError(
                "cutover rehearsal cannot perform a production migration"
            )
        self._advance(CutoverStage.MIGRATION_APPLIED, "synthetic_migration_applied")

    def validate_reconciliation(self, evidence: CutoverInvariantEvidence) -> None:
        self._require_stage(CutoverStage.MIGRATION_APPLIED)
        evidence.require_safe()
        self._advance(
            CutoverStage.RECONCILIATION_VALIDATED,
            "reconciliation_validated",
        )

    def mark_authority_transfer_ready(self) -> None:
        self._require_stage(CutoverStage.RECONCILIATION_VALIDATED)
        self._advance(
            CutoverStage.AUTHORITY_TRANSFER_READY,
            "authority_transfer_ready",
        )

    def activate_v2_authority(self, *, simulated: bool) -> None:
        self._require_stage(CutoverStage.AUTHORITY_TRANSFER_READY)
        if not simulated:
            raise ProductionEffectForbiddenError(
                "real authority activation requires a separate human authorization"
            )
        self._advance(CutoverStage.V2_AUTHORITY_ACTIVE, "v2_authority_active_simulated")

    def validate_post_transfer(self, evidence: CutoverInvariantEvidence) -> None:
        self._require_stage(CutoverStage.V2_AUTHORITY_ACTIVE)
        evidence.require_safe()
        self._advance(
            CutoverStage.POST_TRANSFER_VALIDATION,
            "post_transfer_validation_passed",
        )

    def close(self) -> None:
        self._require_stage(CutoverStage.POST_TRANSFER_VALIDATION)
        self._advance(CutoverStage.CLOSED, "rehearsal_closed")

    def abort(self, reason: str) -> None:
        if self.stage in {CutoverStage.CLOSED, CutoverStage.ROLLED_BACK}:
            raise CutoverRehearsalError("completed rehearsal cannot be aborted")
        if not reason.strip():
            raise CutoverRehearsalError("abort reason must not be blank")
        self._advance(CutoverStage.ABORT, f"aborted:{reason.strip()}")

    def require_rollback(self, reason: str) -> None:
        if self.stage in {
            CutoverStage.PRECHECK,
            CutoverStage.CLOSED,
            CutoverStage.ABORT,
            CutoverStage.ROLLED_BACK,
        }:
            raise CutoverRehearsalError("rollback is not valid from the current stage")
        if not reason.strip():
            raise CutoverRehearsalError("rollback reason must not be blank")
        self._advance(
            CutoverStage.ROLLBACK_REQUIRED,
            f"rollback_required:{reason.strip()}",
        )

    def start_rollback(self) -> None:
        self._require_stage(CutoverStage.ROLLBACK_REQUIRED)
        self._advance(CutoverStage.ROLLBACK_IN_PROGRESS, "rollback_started")

    def finish_rollback(self, evidence: CutoverInvariantEvidence) -> None:
        self._require_stage(CutoverStage.ROLLBACK_IN_PROGRESS)
        evidence.require_safe()
        self._advance(CutoverStage.ROLLED_BACK, "rollback_finished")

    def checkpoint(self) -> CutoverRehearsalCheckpoint:
        return CutoverRehearsalCheckpoint(
            rehearsal_id=self.rehearsal_id,
            stage=self.stage,
            snapshot_id=self.snapshot_id,
            audit_log=self.audit_log,
        )

    @classmethod
    def restore(cls, checkpoint: CutoverRehearsalCheckpoint) -> CutoverRehearsal:
        rehearsal = cls(checkpoint.rehearsal_id)
        rehearsal.stage = checkpoint.stage
        rehearsal.snapshot_id = checkpoint.snapshot_id
        rehearsal._audit_log = list(checkpoint.audit_log)
        rehearsal._audit_log.append("rehearsal_restored")
        return rehearsal
