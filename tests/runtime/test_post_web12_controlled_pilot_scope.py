from __future__ import annotations

from datetime import UTC, datetime

from kordena_fiscal.domain import (
    BrazilianJurisdiction,
    ExecutionScope,
    FiscalDocumentKind,
    FiscalEnvironment,
)
from kordena_fiscal.gateway.provider import ProviderOperation
from kordena_fiscal.homologation import TechnicalGateState
from kordena_fiscal.runtime.controlled_pilots import (
    ControlledPilotGovernanceService,
    ControlledPilotScope,
)
from kordena_fiscal.runtime.homologation_readiness import (
    HomologationEnvironmentReadinessAssessment,
)

NOW = datetime(2026, 9, 16, 3, 0, tzinfo=UTC)
SP = BrazilianJurisdiction("SP")
PROVIDER = "provider-post-web12-b"


def _scope() -> ExecutionScope:
    return ExecutionScope(
        host_namespace="nfcore-post-web12",
        tenant_id="tenant-b",
        unit_id="unit-b",
        environment=FiscalEnvironment.HOMOLOGATION,
        correlation_id="corr-post-web12-b",
    )


def _pilot() -> ControlledPilotScope:
    return ControlledPilotScope(
        pilot_id="pilot-post-web12-b",
        scope=_scope(),
        document_kind=FiscalDocumentKind.NFE,
        jurisdiction=SP,
        provider_id=PROVIDER,
        allowed_operations=frozenset(
            {ProviderOperation.AUTHORIZE, ProviderOperation.QUERY}
        ),
    )


def _assessment(
    operation: ProviderOperation,
    *,
    official: bool,
    missing: tuple[str, ...] = (),
) -> HomologationEnvironmentReadinessAssessment:
    return HomologationEnvironmentReadinessAssessment(
        scope=_scope(),
        document_kind=FiscalDocumentKind.NFE,
        jurisdiction=SP,
        operation=operation,
        provider_id=PROVIDER,
        missing_configuration=missing,
        technical_state=TechnicalGateState.TECHNICALLY_CERTIFIED,
        external_official=official,
        external_evidence_id=(
            f"official-{operation.value}" if official else None
        ),
        external_recorded_at=NOW if official else None,
    )


class StaticReadiness:
    def __init__(
        self,
        assessments: dict[
            ProviderOperation,
            HomologationEnvironmentReadinessAssessment,
        ],
    ) -> None:
        self.assessments = assessments

    def assess(self, **kwargs):  # type: ignore[no-untyped-def]
        return self.assessments[kwargs["operation"]]


def _service(
    assessments: dict[ProviderOperation, HomologationEnvironmentReadinessAssessment],
) -> ControlledPilotGovernanceService:
    return ControlledPilotGovernanceService(  # type: ignore[arg-type]
        None,
        readiness=StaticReadiness(assessments),
    )


def test_external_pilot_requires_official_evidence_for_every_allowlisted_operation() -> None:
    service = _service(
        {
            ProviderOperation.AUTHORIZE: _assessment(
                ProviderOperation.AUTHORIZE,
                official=True,
            ),
            ProviderOperation.QUERY: _assessment(
                ProviderOperation.QUERY,
                official=False,
            ),
        }
    )

    readiness = service.assess_external_scope(pilot=_pilot())

    assert readiness.internal_ready is True
    assert readiness.official_evidence_complete is False
    assert readiness.external_reasons == (
        "external_official_evidence_missing:query",
    )


def test_external_pilot_fails_internal_gate_before_external_classification() -> None:
    service = _service(
        {
            ProviderOperation.AUTHORIZE: _assessment(
                ProviderOperation.AUTHORIZE,
                official=True,
            ),
            ProviderOperation.QUERY: _assessment(
                ProviderOperation.QUERY,
                official=False,
                missing=("provider_credentials_reference",),
            ),
        }
    )

    readiness = service.assess_external_scope(pilot=_pilot())

    assert readiness.internal_ready is False
    assert readiness.official_evidence_complete is False
    assert readiness.internal_reasons == (
        "pilot_operation_not_internally_ready:query:provider_credentials_reference",
    )


def test_external_pilot_scope_is_complete_only_when_every_exact_cell_is_official() -> None:
    service = _service(
        {
            ProviderOperation.AUTHORIZE: _assessment(
                ProviderOperation.AUTHORIZE,
                official=True,
            ),
            ProviderOperation.QUERY: _assessment(
                ProviderOperation.QUERY,
                official=True,
            ),
        }
    )

    readiness = service.assess_external_scope(pilot=_pilot())

    assert readiness.internal_reasons == ()
    assert readiness.external_reasons == ()
    assert readiness.internal_ready is True
    assert readiness.official_evidence_complete is True
