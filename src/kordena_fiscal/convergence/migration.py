"""Synthetic, deterministic migration rehearsal for pre-cutover certification.

The module migrates only identifiers, categories and checksums. It is not a
production database migrator and never carries real fiscal document payloads or
secrets.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256

from .readiness import ConvergenceValidationError


class MigrationValidationError(ConvergenceValidationError):
    """Raised when a migration contract or state is unsafe."""


class MigrationConflictError(MigrationValidationError):
    """Raised when an identifier resolves to conflicting state."""


class MigrationInterruptedError(MigrationValidationError):
    """Synthetic interruption used to certify restartability."""


class MigrationDisposition(StrEnum):
    MIGRATE = "migrate"
    REBUILD = "rebuild"
    REINDEX = "reindex"
    REFERENCE = "reference"
    ARCHIVE_ONLY = "archive_only"
    RECONCILE = "reconcile"
    DO_NOT_MIGRATE = "do_not_migrate"


@dataclass(frozen=True, slots=True)
class MigrationInventoryItem:
    category: str
    disposition: MigrationDisposition
    rationale: str

    def __post_init__(self) -> None:
        if not self.category.strip():
            raise MigrationValidationError("migration category must not be blank")
        if not isinstance(self.disposition, MigrationDisposition):
            raise MigrationValidationError("disposition must be MigrationDisposition")
        if not self.rationale.strip():
            raise MigrationValidationError("migration rationale must not be blank")


def _inventory(
    category: str,
    disposition: MigrationDisposition,
    rationale: str,
) -> MigrationInventoryItem:
    return MigrationInventoryItem(category, disposition, rationale)


DEFAULT_MIGRATION_INVENTORY: tuple[MigrationInventoryItem, ...] = (
    _inventory(
        "fiscal-documents",
        MigrationDisposition.REFERENCE,
        "Preserve canonical references and lifecycle identity; "
        "do not duplicate signed payloads.",
    ),
    _inventory(
        "document-lifecycle",
        MigrationDisposition.MIGRATE,
        "Lifecycle authority must continue without state loss.",
    ),
    _inventory(
        "numbering-sequence",
        MigrationDisposition.MIGRATE,
        "Sequence floors must never regress or be reissued.",
    ),
    _inventory(
        "idempotency",
        MigrationDisposition.MIGRATE,
        "Historical keys prevent duplicate fiscal side effects after cutover.",
    ),
    _inventory(
        "provider-operation-references",
        MigrationDisposition.MIGRATE,
        "Provider correlation remains necessary for query and reconciliation.",
    ),
    _inventory(
        "archive-metadata",
        MigrationDisposition.MIGRATE,
        "Metadata and integrity references remain queryable.",
    ),
    _inventory(
        "xml-document-references",
        MigrationDisposition.ARCHIVE_ONLY,
        "Archive remains immutable; migration carries references rather than "
        "raw payload duplication.",
    ),
    _inventory(
        "fiscal-account-bindings",
        MigrationDisposition.MIGRATE,
        "Host/tenant/unit fiscal ownership must remain explicit.",
    ),
    _inventory(
        "fiscal-profiles",
        MigrationDisposition.MIGRATE,
        "Effective-dated fiscal profiles remain governed state.",
    ),
    _inventory(
        "environment-state",
        MigrationDisposition.MIGRATE,
        "Homologation and production scopes cannot be inferred or collapsed.",
    ),
    _inventory(
        "capability-readiness-evidence",
        MigrationDisposition.RECONCILE,
        "Evidence must be revalidated; migration never promotes readiness.",
    ),
    _inventory(
        "outbox",
        MigrationDisposition.RECONCILE,
        "Pending delivery state must be drained or reconciled at the authority boundary.",
    ),
    _inventory(
        "inbox",
        MigrationDisposition.RECONCILE,
        "Inbound deduplication state must prevent replay side effects.",
    ),
    _inventory(
        "webhook-delivery-state",
        MigrationDisposition.RECONCILE,
        "Pending deliveries require explicit reconciliation.",
    ),
    _inventory(
        "reconciliation-state",
        MigrationDisposition.MIGRATE,
        "Unknown outcomes and pending reconciliation cannot be discarded.",
    ),
    _inventory(
        "contingencies",
        MigrationDisposition.RECONCILE,
        "Open contingency state must be resolved before authority transfer.",
    ),
    _inventory(
        "cancel-inutilization-references",
        MigrationDisposition.MIGRATE,
        "Downstream lifecycle operations require original references.",
    ),
    _inventory(
        "correlation-causation",
        MigrationDisposition.MIGRATE,
        "Trace continuity must survive convergence.",
    ),
    _inventory(
        "audit-trail",
        MigrationDisposition.ARCHIVE_ONLY,
        "Historical audit is immutable and remains evidence.",
    ),
    _inventory(
        "regulatory-provenance",
        MigrationDisposition.MIGRATE,
        "Rule provenance remains required for deterministic historical explanation.",
    ),
)


@dataclass(frozen=True, slots=True)
class MigrationRecord:
    record_id: str
    category: str
    checksum: str
    provenance: str

    def __post_init__(self) -> None:
        for field_name in ("record_id", "category", "checksum", "provenance"):
            if not getattr(self, field_name).strip():
                raise MigrationValidationError(f"{field_name} must not be blank")

    @property
    def state_signature(self) -> tuple[str, str, str]:
        return (self.category, self.checksum, self.provenance)


@dataclass(frozen=True, slots=True)
class MigrationBatch:
    batch_id: str
    records: tuple[MigrationRecord, ...]

    def __post_init__(self) -> None:
        if not self.batch_id.strip():
            raise MigrationValidationError("batch_id must not be blank")
        if not self.records:
            raise MigrationValidationError("migration batch must not be empty")
        ids = tuple(record.record_id for record in self.records)
        if len(ids) != len(set(ids)):
            raise MigrationValidationError("record ids must be unique inside a batch")

    @property
    def fingerprint(self) -> str:
        material = "\n".join(
            f"{record.record_id}|{record.category}|{record.checksum}|{record.provenance}"
            for record in sorted(self.records, key=lambda item: item.record_id)
        )
        return sha256(material.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class MigrationDryRun:
    batch_id: str
    fingerprint: str
    new_records: int
    already_applied: int
    conflicts: tuple[str, ...]

    @property
    def safe_to_apply(self) -> bool:
        return not self.conflicts


@dataclass(frozen=True, slots=True)
class SequenceMigrationCheckpoint:
    scope_key: str
    legacy_last_issued: int
    v2_last_issued: int

    def __post_init__(self) -> None:
        if not self.scope_key.strip():
            raise MigrationValidationError("scope_key must not be blank")
        if self.legacy_last_issued < 0 or self.v2_last_issued < 0:
            raise MigrationValidationError("sequence checkpoints must be non-negative")

    @property
    def required_last_issued_floor(self) -> int:
        return max(self.legacy_last_issued, self.v2_last_issued)

    def validate_target(self, target_last_issued: int) -> None:
        if target_last_issued < self.required_last_issued_floor:
            raise MigrationValidationError("target sequence would regress below certified floor")


class MigrationRehearsalLedger:
    """In-memory synthetic ledger used only to prove migration invariants."""

    def __init__(self, initial_records: tuple[MigrationRecord, ...] = ()) -> None:
        ids = tuple(record.record_id for record in initial_records)
        if len(ids) != len(set(ids)):
            raise MigrationValidationError("initial migration state contains duplicate ids")
        self._records = {record.record_id: record for record in initial_records}
        self._batch_fingerprints: dict[str, str] = {}
        self._batch_new_ids: dict[str, set[str]] = {}

    @property
    def record_count(self) -> int:
        return len(self._records)

    def get(self, record_id: str) -> MigrationRecord | None:
        return self._records.get(record_id)

    def dry_run(self, batch: MigrationBatch) -> MigrationDryRun:
        new_records = 0
        already_applied = 0
        conflicts: list[str] = []
        for record in batch.records:
            existing = self._records.get(record.record_id)
            if existing is None:
                new_records += 1
            elif existing.state_signature == record.state_signature:
                already_applied += 1
            else:
                conflicts.append(record.record_id)
        return MigrationDryRun(
            batch_id=batch.batch_id,
            fingerprint=batch.fingerprint,
            new_records=new_records,
            already_applied=already_applied,
            conflicts=tuple(sorted(conflicts)),
        )

    def apply(self, batch: MigrationBatch, *, interrupt_after: int | None = None) -> int:
        if interrupt_after is not None and interrupt_after <= 0:
            raise MigrationValidationError("interrupt_after must be greater than zero")

        known_fingerprint = self._batch_fingerprints.get(batch.batch_id)
        if known_fingerprint is not None and known_fingerprint != batch.fingerprint:
            raise MigrationConflictError("batch id was reused with different migration content")

        dry_run = self.dry_run(batch)
        if dry_run.conflicts:
            raise MigrationConflictError(
                "migration conflicts with existing state: " + ", ".join(dry_run.conflicts)
            )

        self._batch_fingerprints.setdefault(batch.batch_id, batch.fingerprint)
        introduced = self._batch_new_ids.setdefault(batch.batch_id, set())
        processed = 0
        applied = 0
        for record in batch.records:
            processed += 1
            if record.record_id not in self._records:
                self._records[record.record_id] = record
                introduced.add(record.record_id)
                applied += 1
            if interrupt_after is not None and processed == interrupt_after:
                raise MigrationInterruptedError("synthetic migration interruption")
        return applied

    def reconciled(self, batch: MigrationBatch) -> bool:
        dry_run = self.dry_run(batch)
        return dry_run.safe_to_apply and dry_run.new_records == 0

    def rollback(self, batch_id: str) -> int:
        if batch_id not in self._batch_fingerprints:
            raise MigrationValidationError("cannot rollback an unknown migration batch")
        introduced = self._batch_new_ids.get(batch_id, set())
        removed = 0
        for record_id in tuple(introduced):
            if self._records.pop(record_id, None) is not None:
                removed += 1
        self._batch_new_ids.pop(batch_id, None)
        self._batch_fingerprints.pop(batch_id, None)
        return removed
