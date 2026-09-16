"""Read-only production Go/No-Go package for governed NFCORE cutover readiness.

This module composes canonical convergence, homologation and controlled-pilot
facts. It does not execute cutover, mutate fiscal authority, create official
evidence or issue a PRODUCTION_APPROVED decision.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from kordena_fiscal.runtime.controlled_pilots import (
    PilotDecision,
    PilotDecisionStatus,
)
from kordena_fiscal.runtime.homologation_readiness import (
    ExternalReadinessCellReport,
    ExternalReadinessFlag,
)

from .readiness import (
    ConvergenceValidationError,
    CutoverReadinessMatrix,
    CutoverReadinessStatus,
)


class ConsumerReadinessStatus(StrEnum):
    READY = "ready"
    PENDING_CAPABILITY = "pending_capability"
    PENDING_FISCAL_CLASSIFICATION = "pending_fiscal_classification"
    BLOCKED_EXTERNAL = "blocked_external"
    NOT_APPLICABLE = "not_applicable"


@dataclass(frozen=True, slots=True)
class ConsumerReadinessEvidence:
    consumer_id: str
    status: ConsumerReadinessStatus
    evidence: str
    mandatory: bool = True

    def __post_init__(self) -> None:
        if not self.consumer_id.strip():
            raise ConvergenceValidationError("consumer_id must not be blank")
        if not isinstance(self.status, ConsumerReadinessStatus):
            raise ConvergenceValidationError("status must be ConsumerReadinessStatus")
        if not self.evidence.strip():
            raise ConvergenceValidationError("consumer evidence must not be blank")


@dataclass(frozen=True, slots=True)
class PilotExecutionEvidence:
    """Sanitized proof that a governed real pilot was actually executed.

    The external evidence id is an opaque reference only. No provider secret,
    certificate or CSC material belongs in this object.
    """

    pilot_id: str
    external_evidence_id: str
    completed_at: datetime

    def __post_init__(self) -> None:
        if not self.pilot_id.strip():
            raise ConvergenceValidationError("pilot_id must not be blank")
        if not self.external_evidence_id.strip():
            raise ConvergenceValidationError("external_evidence_id must not be blank")
        if self.completed_at.tzinfo is None or self.completed_at.utcoffset() is None:
            raise ConvergenceValidationError("pilot completed_at must be timezone-aware")


@dataclass(frozen=True, slots=True)
class CutoverOperationalEvidence:
    """Evidence references for pre-cutover tooling/rehearsal, never production effects."""

    writer_inventory: str | None = None
    writer_freeze_rehearsal: str | None = None
    snapshot_backup_restore: str | None = None
    migration_dry_run: str | None = None
    reconciliation_rehearsal: str | None = None
    rollback_rehearsal: str | None = None
    authority_transfer_rehearsal: str | None = None
    runtime_smoke: str | None = None
    monitoring: str | None = None
    stop_conditions: str | None = None

    @property
    def missing_requirements(self) -> tuple[str, ...]:
        fields = (
            ("writer_inventory", self.writer_inventory),
            ("writer_freeze_rehearsal", self.writer_freeze_rehearsal),
            ("snapshot_backup_restore", self.snapshot_backup_restore),
            ("migration_dry_run", self.migration_dry_run),
            ("reconciliation_rehearsal", self.reconciliation_rehearsal),
            ("rollback_rehearsal", self.rollback_rehearsal),
            ("authority_transfer_rehearsal", self.authority_transfer_rehearsal),
            ("runtime_smoke", self.runtime_smoke),
            ("monitoring", self.monitoring),
            ("stop_conditions", self.stop_conditions),
        )
        return tuple(name for name, value in fields if value is None or not value.strip())


class ProductionGoNoGoStatus(StrEnum):
    NO_GO = "no_go"
    BLOCKED_EXTERNAL = "blocked_external"
    READY_FOR_HUMAN_GO_NO_GO = "ready_for_human_go_no_go"


@dataclass(frozen=True, slots=True)
class ProductionGoNoGoPackage:
    status: ProductionGoNoGoStatus
    internal_blockers: tuple[str, ...]
    external_blockers: tuple[str, ...]
    human_approval_pending: bool
    production_activation_present: bool

    @property
    def ready_for_human_decision(self) -> bool:
        return self.status is ProductionGoNoGoStatus.READY_FOR_HUMAN_GO_NO_GO


def build_production_go_no_go_package(
    *,
    cutover: CutoverReadinessMatrix,
    external_cells: tuple[ExternalReadinessCellReport, ...],
    pilot_decisions: tuple[PilotDecision, ...],
    pilot_execution_evidence: tuple[PilotExecutionEvidence, ...],
    consumers: tuple[ConsumerReadinessEvidence, ...],
    operations: CutoverOperationalEvidence,
) -> ProductionGoNoGoPackage:
    """Classify readiness without creating human approval or production authority."""

    if not isinstance(cutover, CutoverReadinessMatrix):
        raise ConvergenceValidationError("cutover must be CutoverReadinessMatrix")
    if not all(isinstance(item, ExternalReadinessCellReport) for item in external_cells):
        raise ConvergenceValidationError("external_cells contain invalid values")
    if not all(isinstance(item, PilotDecision) for item in pilot_decisions):
        raise ConvergenceValidationError("pilot_decisions contain invalid values")
    if not all(isinstance(item, PilotExecutionEvidence) for item in pilot_execution_evidence):
        raise ConvergenceValidationError("pilot_execution_evidence contain invalid values")
    if not all(isinstance(item, ConsumerReadinessEvidence) for item in consumers):
        raise ConvergenceValidationError("consumers contain invalid values")
    if not isinstance(operations, CutoverOperationalEvidence):
        raise ConvergenceValidationError("operations must be CutoverOperationalEvidence")

    internal: list[str] = []
    external: list[str] = []
    human_approval_pending = False

    for requirement in cutover.requirements:
        if not requirement.mandatory:
            continue
        if requirement.status is CutoverReadinessStatus.BLOCKED_PRODUCT:
            internal.append(f"cutover:{requirement.requirement_id}")
        elif requirement.status is CutoverReadinessStatus.BLOCKED_EXTERNAL:
            external.append(f"cutover:{requirement.requirement_id}")
        elif requirement.status is CutoverReadinessStatus.HUMAN_APPROVAL_REQUIRED:
            human_approval_pending = True

    internal.extend(f"operations:{item}" for item in operations.missing_requirements)

    for consumer in consumers:
        if not consumer.mandatory or consumer.status in {
            ConsumerReadinessStatus.READY,
            ConsumerReadinessStatus.NOT_APPLICABLE,
        }:
            continue
        if consumer.status is ConsumerReadinessStatus.BLOCKED_EXTERNAL:
            external.append(f"consumer:{consumer.consumer_id}:{consumer.status.value}")
        else:
            internal.append(f"consumer:{consumer.consumer_id}:{consumer.status.value}")

    external_flags = {
        ExternalReadinessFlag.MISSING_EXTERNAL_CREDENTIAL,
        ExternalReadinessFlag.MISSING_OFFICIAL_EVIDENCE,
        ExternalReadinessFlag.MISSING_PILOT_AUTHORIZATION,
    }
    production_activation_present = False
    for cell in external_cells:
        cell_id = (
            f"{cell.assessment.scope.tenant_id}/{cell.assessment.scope.unit_id}/"
            f"{cell.assessment.provider_id or 'provider-missing'}/"
            f"{cell.assessment.document_kind.value}/{cell.assessment.operation.value}"
        )
        for flag in sorted(cell.flags.intersection(external_flags), key=lambda item: item.value):
            external.append(f"fiscal_cell:{cell_id}:{flag.value}")
        if ExternalReadinessFlag.MISSING_HUMAN_APPROVAL in cell.flags:
            human_approval_pending = True
        production_activation_present = (
            production_activation_present or cell.production_activation_present
        )

    execution_by_pilot = {item.pilot_id: item for item in pilot_execution_evidence}
    if len(execution_by_pilot) != len(pilot_execution_evidence):
        raise ConvergenceValidationError("pilot execution evidence ids must be unique")

    for decision in pilot_decisions:
        if decision.status is PilotDecisionStatus.NO_GO:
            internal.append(f"pilot:{decision.pilot_id}:no_go")
            continue
        if decision.status is PilotDecisionStatus.BLOCKED_EXTERNAL:
            external.append(f"pilot:{decision.pilot_id}:blocked_external")
            continue
        if not decision.official_evidence_present:
            external.append(f"pilot:{decision.pilot_id}:official_evidence_missing")
            continue
        if decision.pilot_id not in execution_by_pilot:
            external.append(f"pilot:{decision.pilot_id}:execution_evidence_missing")

    internal_blockers = tuple(dict.fromkeys(internal))
    external_blockers = tuple(dict.fromkeys(external))

    if internal_blockers:
        status = ProductionGoNoGoStatus.NO_GO
    elif external_blockers:
        status = ProductionGoNoGoStatus.BLOCKED_EXTERNAL
    else:
        status = ProductionGoNoGoStatus.READY_FOR_HUMAN_GO_NO_GO

    return ProductionGoNoGoPackage(
        status=status,
        internal_blockers=internal_blockers,
        external_blockers=external_blockers,
        human_approval_pending=human_approval_pending,
        production_activation_present=production_activation_present,
    )
