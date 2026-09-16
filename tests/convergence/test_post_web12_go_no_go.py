from __future__ import annotations

from datetime import UTC, datetime

from kordena_fiscal.convergence.go_no_go import (
    ConsumerReadinessEvidence,
    ConsumerReadinessStatus,
    CutoverOperationalEvidence,
    PilotExecutionEvidence,
    ProductionGoNoGoStatus,
    build_production_go_no_go_package,
)
from kordena_fiscal.convergence.readiness import (
    CutoverReadinessMatrix,
    CutoverReadinessStatus,
    CutoverRequirement,
)
from kordena_fiscal.domain import (
    BrazilianJurisdiction,
    ExecutionScope,
    FiscalDocumentKind,
    FiscalEnvironment,
)
from kordena_fiscal.gateway.provider import ProviderOperation
from kordena_fiscal.homologation import TechnicalGateState
from kordena_fiscal.runtime.controlled_pilots import (
    PilotDecision,
    PilotDecisionStatus,
)
from kordena_fiscal.runtime.homologation_readiness import (
    ExternalReadinessCellReport,
    ExternalReadinessFlag,
    HomologationEnvironmentReadinessAssessment,
)

NOW = datetime(2026, 9, 16, 4, 0, tzinfo=UTC)


def _operations(*, complete: bool = True) -> CutoverOperationalEvidence:
    value = "certified-rehearsal" if complete else None
    return CutoverOperationalEvidence(
        writer_inventory=value,
        writer_freeze_rehearsal=value,
        snapshot_backup_restore=value,
        migration_dry_run=value,
        reconciliation_rehearsal=value,
        rollback_rehearsal=value,
        authority_transfer_rehearsal=value,
        runtime_smoke=value,
        monitoring=value,
        stop_conditions=value,
    )


def _cutover(status: CutoverReadinessStatus) -> CutoverReadinessMatrix:
    return CutoverReadinessMatrix(
        (
            CutoverRequirement(
                requirement_id="production-go-no-go",
                status=status,
                evidence="post-web12-c-evidence",
            ),
        )
    )


def _cell(*, blocked_external: bool) -> ExternalReadinessCellReport:
    assessment = HomologationEnvironmentReadinessAssessment(
        scope=ExecutionScope(
            host_namespace="nfcore-post-web12",
            tenant_id="tenant-c",
            unit_id="unit-c",
            environment=FiscalEnvironment.HOMOLOGATION,
            correlation_id="corr-post-web12-c",
        ),
        document_kind=FiscalDocumentKind.NFE,
        jurisdiction=BrazilianJurisdiction("SP"),
        operation=ProviderOperation.QUERY,
        provider_id="provider-c",
        missing_configuration=(),
        technical_state=TechnicalGateState.TECHNICALLY_CERTIFIED,
        external_official=not blocked_external,
        external_evidence_id=None if blocked_external else "official-cell-c",
        external_recorded_at=None if blocked_external else NOW,
    )
    flags = (
        frozenset(
            {
                ExternalReadinessFlag.READY_INTERNAL,
                ExternalReadinessFlag.MISSING_OFFICIAL_EVIDENCE,
                ExternalReadinessFlag.MISSING_PILOT_AUTHORIZATION,
                ExternalReadinessFlag.MISSING_HUMAN_APPROVAL,
                ExternalReadinessFlag.BLOCKED_EXTERNAL,
            }
        )
        if blocked_external
        else frozenset(
            {
                ExternalReadinessFlag.READY_INTERNAL,
                ExternalReadinessFlag.MISSING_HUMAN_APPROVAL,
            }
        )
    )
    return ExternalReadinessCellReport(
        assessment=assessment,
        flags=flags,
        pilot_authorized=not blocked_external,
        human_approval_present=False,
        production_activation_present=False,
    )


def _pilot(*, status: PilotDecisionStatus, official: bool) -> PilotDecision:
    return PilotDecision(
        pilot_id="pilot-c",
        operation=ProviderOperation.QUERY,
        status=status,
        reasons=("certified",),
        provider_id="provider-c",
        internal_ready=status is not PilotDecisionStatus.NO_GO,
        official_evidence_present=official,
    )


def _consumer(status: ConsumerReadinessStatus) -> ConsumerReadinessEvidence:
    return ConsumerReadinessEvidence(
        consumer_id="consumer-c",
        status=status,
        evidence="consumer-audit-c",
    )


def test_internal_cutover_failure_is_no_go_even_when_external_evidence_exists() -> None:
    package = build_production_go_no_go_package(
        cutover=_cutover(CutoverReadinessStatus.BLOCKED_PRODUCT),
        external_cells=(_cell(blocked_external=False),),
        pilot_decisions=(_pilot(status=PilotDecisionStatus.GO_INTERNAL, official=True),),
        pilot_execution_evidence=(
            PilotExecutionEvidence("pilot-c", "pilot-external-c", NOW),
        ),
        consumers=(_consumer(ConsumerReadinessStatus.READY),),
        operations=_operations(),
    )

    assert package.status is ProductionGoNoGoStatus.NO_GO
    assert package.internal_blockers == ("cutover:production-go-no-go",)


def test_missing_official_evidence_and_pilot_are_blocked_external() -> None:
    package = build_production_go_no_go_package(
        cutover=_cutover(CutoverReadinessStatus.HUMAN_APPROVAL_REQUIRED),
        external_cells=(_cell(blocked_external=True),),
        pilot_decisions=(
            _pilot(status=PilotDecisionStatus.BLOCKED_EXTERNAL, official=False),
        ),
        pilot_execution_evidence=(),
        consumers=(_consumer(ConsumerReadinessStatus.READY),),
        operations=_operations(),
    )

    assert package.status is ProductionGoNoGoStatus.BLOCKED_EXTERNAL
    assert package.human_approval_pending is True
    assert any("missing_official_evidence" in item for item in package.external_blockers)
    assert "pilot:pilot-c:blocked_external" in package.external_blockers


def test_mandatory_consumer_pending_classification_is_no_go() -> None:
    package = build_production_go_no_go_package(
        cutover=_cutover(CutoverReadinessStatus.HUMAN_APPROVAL_REQUIRED),
        external_cells=(_cell(blocked_external=False),),
        pilot_decisions=(_pilot(status=PilotDecisionStatus.GO_INTERNAL, official=True),),
        pilot_execution_evidence=(
            PilotExecutionEvidence("pilot-c", "pilot-external-c", NOW),
        ),
        consumers=(
            _consumer(ConsumerReadinessStatus.PENDING_FISCAL_CLASSIFICATION),
        ),
        operations=_operations(),
    )

    assert package.status is ProductionGoNoGoStatus.NO_GO
    assert package.internal_blockers == (
        "consumer:consumer-c:pending_fiscal_classification",
    )


def test_missing_cutover_rehearsal_evidence_is_no_go() -> None:
    package = build_production_go_no_go_package(
        cutover=_cutover(CutoverReadinessStatus.HUMAN_APPROVAL_REQUIRED),
        external_cells=(_cell(blocked_external=False),),
        pilot_decisions=(_pilot(status=PilotDecisionStatus.GO_INTERNAL, official=True),),
        pilot_execution_evidence=(
            PilotExecutionEvidence("pilot-c", "pilot-external-c", NOW),
        ),
        consumers=(_consumer(ConsumerReadinessStatus.READY),),
        operations=_operations(complete=False),
    )

    assert package.status is ProductionGoNoGoStatus.NO_GO
    assert "operations:writer_inventory" in package.internal_blockers
    assert "operations:rollback_rehearsal" in package.internal_blockers


def test_fully_evidenced_package_stops_at_ready_for_human_go_no_go() -> None:
    package = build_production_go_no_go_package(
        cutover=_cutover(CutoverReadinessStatus.HUMAN_APPROVAL_REQUIRED),
        external_cells=(_cell(blocked_external=False),),
        pilot_decisions=(_pilot(status=PilotDecisionStatus.GO_INTERNAL, official=True),),
        pilot_execution_evidence=(
            PilotExecutionEvidence("pilot-c", "pilot-external-c", NOW),
        ),
        consumers=(_consumer(ConsumerReadinessStatus.READY),),
        operations=_operations(),
    )

    assert package.status is ProductionGoNoGoStatus.READY_FOR_HUMAN_GO_NO_GO
    assert package.ready_for_human_decision is True
    assert package.human_approval_pending is True
    assert package.production_activation_present is False
    assert "PRODUCTION_APPROVED" not in {item.value for item in ProductionGoNoGoStatus}
