import pytest

from kordena_fiscal.convergence.cutover_rehearsal import (
    CutoverInvariantEvidence,
    CutoverRehearsal,
    CutoverRehearsalError,
    CutoverStage,
    ProductionEffectForbiddenError,
    WriterStatus,
)
from kordena_fiscal.convergence.readiness import (
    CutoverReadinessMatrix,
    CutoverReadinessStatus,
    CutoverRequirement,
)


def ready_matrix() -> CutoverReadinessMatrix:
    return CutoverReadinessMatrix(
        requirements=(
            CutoverRequirement(
                requirement_id="functional-equivalence",
                status=CutoverReadinessStatus.READY_INTERNAL,
                evidence="synthetic rehearsal prerequisite",
            ),
            CutoverRequirement(
                requirement_id="migration",
                status=CutoverReadinessStatus.READY_INTERNAL,
                evidence="synthetic migration certified",
            ),
        )
    )


def safe_evidence() -> CutoverInvariantEvidence:
    return CutoverInvariantEvidence(
        sequence_safe=True,
        idempotency_preserved=True,
        inbox_outbox_reconciled=True,
        unknown_outcomes=0,
        archive_integrity=True,
        lifecycle_integrity=True,
        bindings_integrity=True,
        readiness_promoted_by_migration=False,
        provider_state_preserved=True,
        audit_complete=True,
    )


def move_to_migration_applied(rehearsal: CutoverRehearsal) -> None:
    rehearsal.complete_precheck(ready_matrix())
    rehearsal.confirm_writers_frozen(
        (
            WriterStatus("legacy", "legacy-core", True),
            WriterStatus("v2", "fm-fiscal-v2", False),
        ),
        future_authority="fm-fiscal-v2",
    )
    rehearsal.capture_snapshot("synthetic-snapshot", consistent=True)
    rehearsal.validate_migration(conflict_free=True, deterministic=True)
    rehearsal.apply_synthetic_migration()


def test_happy_path_closes_only_after_all_governed_stages() -> None:
    rehearsal = CutoverRehearsal("r-001")
    move_to_migration_applied(rehearsal)
    rehearsal.validate_reconciliation(safe_evidence())
    rehearsal.mark_authority_transfer_ready()
    rehearsal.activate_v2_authority(simulated=True)
    rehearsal.validate_post_transfer(safe_evidence())
    rehearsal.close()

    assert rehearsal.stage is CutoverStage.CLOSED
    assert rehearsal.snapshot_id == "synthetic-snapshot"
    assert "v2_authority_active_simulated" in rehearsal.audit_log


def test_precheck_fails_closed_when_mandatory_blocker_exists() -> None:
    rehearsal = CutoverRehearsal("r-blocked")
    matrix = CutoverReadinessMatrix(
        requirements=(
            CutoverRequirement(
                requirement_id="kordena-on-v2",
                status=CutoverReadinessStatus.BLOCKED_PRODUCT,
                evidence="consumer not ready",
            ),
        )
    )

    with pytest.raises(ValueError, match="prerequisites"):
        rehearsal.complete_precheck(matrix)

    assert rehearsal.stage is CutoverStage.PRECHECK


def test_unfrozen_legacy_writer_blocks_progress() -> None:
    rehearsal = CutoverRehearsal("r-writer")
    rehearsal.complete_precheck(ready_matrix())

    with pytest.raises(CutoverRehearsalError, match="legacy writers remain active"):
        rehearsal.confirm_writers_frozen(
            (WriterStatus("legacy", "legacy-core", False),),
            future_authority="fm-fiscal-v2",
        )


def test_future_authority_writer_may_remain_active_in_rehearsal_inventory() -> None:
    rehearsal = CutoverRehearsal("r-v2-writer")
    rehearsal.complete_precheck(ready_matrix())
    rehearsal.confirm_writers_frozen(
        (WriterStatus("v2", "fm-fiscal-v2", False),),
        future_authority="fm-fiscal-v2",
    )

    assert rehearsal.stage is CutoverStage.WRITERS_FROZEN


def test_inconsistent_snapshot_is_rejected() -> None:
    rehearsal = CutoverRehearsal("r-snapshot")
    rehearsal.complete_precheck(ready_matrix())
    rehearsal.confirm_writers_frozen(
        (WriterStatus("legacy", "legacy-core", True),),
        future_authority="fm-fiscal-v2",
    )

    with pytest.raises(CutoverRehearsalError, match="snapshot is inconsistent"):
        rehearsal.capture_snapshot("bad", consistent=False)


def test_migration_conflict_and_nondeterminism_are_fail_closed() -> None:
    rehearsal = CutoverRehearsal("r-migration")
    rehearsal.complete_precheck(ready_matrix())
    rehearsal.confirm_writers_frozen(
        (WriterStatus("legacy", "legacy-core", True),),
        future_authority="fm-fiscal-v2",
    )
    rehearsal.capture_snapshot("snap", consistent=True)

    with pytest.raises(CutoverRehearsalError, match="conflict"):
        rehearsal.validate_migration(conflict_free=False, deterministic=True)
    with pytest.raises(CutoverRehearsalError, match="not deterministic"):
        rehearsal.validate_migration(conflict_free=True, deterministic=False)


def test_rehearsal_cannot_apply_production_migration() -> None:
    rehearsal = CutoverRehearsal("r-prod-migration")
    rehearsal.complete_precheck(ready_matrix())
    rehearsal.confirm_writers_frozen(
        (WriterStatus("legacy", "legacy-core", True),),
        future_authority="fm-fiscal-v2",
    )
    rehearsal.capture_snapshot("snap", consistent=True)
    rehearsal.validate_migration(conflict_free=True, deterministic=True)

    with pytest.raises(ProductionEffectForbiddenError, match="production migration"):
        rehearsal.apply_synthetic_migration(production_effect=True)


def test_reconciliation_rejects_each_material_invariant_failure() -> None:
    base = safe_evidence()
    cases = (
        {"sequence_safe": False},
        {"idempotency_preserved": False},
        {"inbox_outbox_reconciled": False},
        {"unknown_outcomes": 1},
        {"archive_integrity": False},
        {"lifecycle_integrity": False},
        {"bindings_integrity": False},
        {"readiness_promoted_by_migration": True},
        {"provider_state_preserved": False},
        {"audit_complete": False},
    )
    values = base.__dict__ if hasattr(base, "__dict__") else {
        "sequence_safe": base.sequence_safe,
        "idempotency_preserved": base.idempotency_preserved,
        "inbox_outbox_reconciled": base.inbox_outbox_reconciled,
        "unknown_outcomes": base.unknown_outcomes,
        "archive_integrity": base.archive_integrity,
        "lifecycle_integrity": base.lifecycle_integrity,
        "bindings_integrity": base.bindings_integrity,
        "readiness_promoted_by_migration": base.readiness_promoted_by_migration,
        "provider_state_preserved": base.provider_state_preserved,
        "audit_complete": base.audit_complete,
    }
    for override in cases:
        rehearsal = CutoverRehearsal(f"r-invariant-{next(iter(override))}")
        move_to_migration_applied(rehearsal)
        evidence = CutoverInvariantEvidence(**(values | override))
        with pytest.raises(CutoverRehearsalError, match="invariants"):
            rehearsal.validate_reconciliation(evidence)


def test_real_authority_activation_is_forbidden() -> None:
    rehearsal = CutoverRehearsal("r-authority")
    move_to_migration_applied(rehearsal)
    rehearsal.validate_reconciliation(safe_evidence())
    rehearsal.mark_authority_transfer_ready()

    with pytest.raises(ProductionEffectForbiddenError, match="human authorization"):
        rehearsal.activate_v2_authority(simulated=False)


def test_checkpoint_restore_allows_restart_without_stage_regression() -> None:
    rehearsal = CutoverRehearsal("r-restart")
    move_to_migration_applied(rehearsal)
    checkpoint = rehearsal.checkpoint()

    restored = CutoverRehearsal.restore(checkpoint)
    restored.validate_reconciliation(safe_evidence())

    assert restored.stage is CutoverStage.RECONCILIATION_VALIDATED
    assert restored.snapshot_id == "synthetic-snapshot"
    assert restored.audit_log[-1] == "reconciliation_validated"
    assert "rehearsal_restored" in restored.audit_log


def test_rollback_before_authority_transfer_preserves_fail_closed_flow() -> None:
    rehearsal = CutoverRehearsal("r-rollback-before")
    move_to_migration_applied(rehearsal)
    rehearsal.require_rollback("reconciliation warning")
    rehearsal.start_rollback()
    rehearsal.finish_rollback(safe_evidence())

    assert rehearsal.stage is CutoverStage.ROLLED_BACK


def test_rollback_after_simulated_authority_transfer_is_supported() -> None:
    rehearsal = CutoverRehearsal("r-rollback-after")
    move_to_migration_applied(rehearsal)
    rehearsal.validate_reconciliation(safe_evidence())
    rehearsal.mark_authority_transfer_ready()
    rehearsal.activate_v2_authority(simulated=True)
    rehearsal.require_rollback("post-transfer validation failed")
    rehearsal.start_rollback()
    rehearsal.finish_rollback(safe_evidence())

    assert rehearsal.stage is CutoverStage.ROLLED_BACK


def test_abort_requires_reason_and_completed_rehearsal_cannot_abort() -> None:
    rehearsal = CutoverRehearsal("r-abort")
    with pytest.raises(CutoverRehearsalError, match="reason"):
        rehearsal.abort(" ")
    rehearsal.abort("operator requested stop")
    assert rehearsal.stage is CutoverStage.ABORT


def test_stage_ordering_prevents_partial_or_replayed_transition() -> None:
    rehearsal = CutoverRehearsal("r-order")
    with pytest.raises(CutoverRehearsalError, match="freeze_requested"):
        rehearsal.confirm_writers_frozen(
            (WriterStatus("legacy", "legacy", True),),
            future_authority="v2",
        )


def test_unknown_outcome_count_must_be_non_negative() -> None:
    with pytest.raises(CutoverRehearsalError, match="non-negative"):
        CutoverInvariantEvidence(
            sequence_safe=True,
            idempotency_preserved=True,
            inbox_outbox_reconciled=True,
            unknown_outcomes=-1,
            archive_integrity=True,
            lifecycle_integrity=True,
            bindings_integrity=True,
            readiness_promoted_by_migration=False,
            provider_state_preserved=True,
            audit_complete=True,
        )
