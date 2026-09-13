from __future__ import annotations

import pytest

from kordena_fiscal.convergence import (
    DEFAULT_MIGRATION_INVENTORY,
    MigrationBatch,
    MigrationConflictError,
    MigrationDisposition,
    MigrationInterruptedError,
    MigrationRecord,
    MigrationRehearsalLedger,
    MigrationValidationError,
    SequenceMigrationCheckpoint,
)


def _records() -> tuple[MigrationRecord, ...]:
    return (
        MigrationRecord(
            record_id="document:001",
            category="document-lifecycle",
            checksum="sha256-doc-001",
            provenance="legacy@b336def",
        ),
        MigrationRecord(
            record_id="idempotency:001",
            category="idempotency",
            checksum="sha256-idem-001",
            provenance="legacy@b336def",
        ),
        MigrationRecord(
            record_id="sequence:sp:55:001",
            category="numbering-sequence",
            checksum="sha256-seq-001",
            provenance="legacy@b336def",
        ),
    )


def _batch(batch_id: str = "batch-001") -> MigrationBatch:
    return MigrationBatch(batch_id=batch_id, records=_records())


def test_inventory_covers_every_state_category_required_by_v2_17_2() -> None:
    categories = {item.category for item in DEFAULT_MIGRATION_INVENTORY}
    assert categories == {
        "fiscal-documents",
        "document-lifecycle",
        "numbering-sequence",
        "idempotency",
        "provider-operation-references",
        "archive-metadata",
        "xml-document-references",
        "fiscal-account-bindings",
        "fiscal-profiles",
        "environment-state",
        "capability-readiness-evidence",
        "outbox",
        "inbox",
        "webhook-delivery-state",
        "reconciliation-state",
        "contingencies",
        "cancel-inutilization-references",
        "correlation-causation",
        "audit-trail",
        "regulatory-provenance",
    }
    assert {item.disposition for item in DEFAULT_MIGRATION_INVENTORY} <= set(
        MigrationDisposition
    )


def test_dry_run_is_deterministic_and_does_not_mutate_state() -> None:
    ledger = MigrationRehearsalLedger()
    batch = _batch()

    first = ledger.dry_run(batch)
    second = ledger.dry_run(batch)

    assert first == second
    assert first.safe_to_apply is True
    assert first.new_records == 3
    assert first.already_applied == 0
    assert ledger.record_count == 0


def test_apply_is_idempotent_and_reconciliation_confirms_complete_state() -> None:
    ledger = MigrationRehearsalLedger()
    batch = _batch()

    assert ledger.apply(batch) == 3
    assert ledger.apply(batch) == 0
    assert ledger.record_count == 3
    assert ledger.reconciled(batch) is True


def test_interrupted_batch_is_restartable_without_duplicate_records() -> None:
    ledger = MigrationRehearsalLedger()
    batch = _batch()

    with pytest.raises(MigrationInterruptedError, match="synthetic migration interruption"):
        ledger.apply(batch, interrupt_after=2)

    assert ledger.record_count == 2
    assert ledger.apply(batch) == 1
    assert ledger.record_count == 3
    assert ledger.reconciled(batch) is True


def test_conflicting_existing_state_fails_closed_before_mutation() -> None:
    corrupted = MigrationRecord(
        record_id="document:001",
        category="document-lifecycle",
        checksum="different-checksum",
        provenance="legacy@b336def",
    )
    ledger = MigrationRehearsalLedger((corrupted,))
    batch = _batch()

    dry_run = ledger.dry_run(batch)
    assert dry_run.safe_to_apply is False
    assert dry_run.conflicts == ("document:001",)
    with pytest.raises(MigrationConflictError, match="conflicts with existing state"):
        ledger.apply(batch)
    assert ledger.record_count == 1


def test_reusing_batch_id_with_different_content_fails_closed() -> None:
    ledger = MigrationRehearsalLedger()
    original = _batch()
    ledger.apply(original)
    changed = MigrationBatch(
        batch_id=original.batch_id,
        records=(
            MigrationRecord(
                record_id="new:001",
                category="document-lifecycle",
                checksum="different",
                provenance="synthetic",
            ),
        ),
    )

    with pytest.raises(MigrationConflictError, match="batch id was reused"):
        ledger.apply(changed)


def test_rollback_removes_only_records_introduced_by_batch_and_allows_rerun() -> None:
    preexisting = _records()[0]
    ledger = MigrationRehearsalLedger((preexisting,))
    batch = _batch()

    assert ledger.apply(batch) == 2
    assert ledger.record_count == 3
    assert ledger.rollback(batch.batch_id) == 2
    assert ledger.record_count == 1
    assert ledger.get(preexisting.record_id) == preexisting

    assert ledger.apply(batch) == 2
    assert ledger.record_count == 3
    assert ledger.reconciled(batch) is True


def test_unknown_rollback_fails_closed() -> None:
    ledger = MigrationRehearsalLedger()
    with pytest.raises(MigrationValidationError, match="unknown migration batch"):
        ledger.rollback("missing-batch")


def test_sequence_checkpoint_forbids_regression_below_highest_known_floor() -> None:
    checkpoint = SequenceMigrationCheckpoint(
        scope_key="fm.kordena|tenant-a|unit-a|homologation|nfe|55",
        legacy_last_issued=120,
        v2_last_issued=123,
    )

    assert checkpoint.required_last_issued_floor == 123
    checkpoint.validate_target(123)
    checkpoint.validate_target(130)
    with pytest.raises(MigrationValidationError, match="sequence would regress"):
        checkpoint.validate_target(122)
