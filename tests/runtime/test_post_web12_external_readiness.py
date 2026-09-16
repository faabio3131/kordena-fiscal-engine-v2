from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from kordena_fiscal.domain import (
    BrazilianJurisdiction,
    ExecutionScope,
    FiscalDocumentKind,
    FiscalEnvironment,
    FiscalValidationError,
)
from kordena_fiscal.gateway.production_activation import (
    HumanProductionApproval,
    ProductionActivationKey,
    ProductionActivationRecord,
    ProductionActivationState,
)
from kordena_fiscal.gateway.provider import ProviderOperation
from kordena_fiscal.homologation import TechnicalGateState
from kordena_fiscal.runtime.homologation_readiness import (
    ExternalReadinessFlag,
    HomologationEnvironmentReadinessAssessment,
    reconcile_external_readiness,
)

NOW = datetime(2026, 9, 16, 2, 0, tzinfo=UTC)
SP = BrazilianJurisdiction("SP")


def _assessment(
    *,
    external_official: bool = False,
    external_evidence_id: str | None = None,
    recorded_at: datetime | None = None,
    missing_configuration: tuple[str, ...] = (),
) -> HomologationEnvironmentReadinessAssessment:
    return HomologationEnvironmentReadinessAssessment(
        scope=ExecutionScope(
            host_namespace="nfcore-post-web12",
            tenant_id="tenant-a",
            unit_id="unit-a",
            environment=FiscalEnvironment.HOMOLOGATION,
            correlation_id="corr-post-web12-a",
        ),
        document_kind=FiscalDocumentKind.NFE,
        jurisdiction=SP,
        operation=ProviderOperation.QUERY,
        provider_id="provider-a",
        missing_configuration=missing_configuration,
        technical_state=TechnicalGateState.TECHNICALLY_CERTIFIED,
        external_official=external_official,
        external_evidence_id=external_evidence_id,
        external_recorded_at=recorded_at,
    )


def _key(*, provider_id: str = "provider-a") -> ProductionActivationKey:
    return ProductionActivationKey(
        tenant_id="tenant-a",
        unit_id="unit-a",
        provider_id=provider_id,
        document_kind=FiscalDocumentKind.NFE,
        jurisdiction=SP,
        operation=ProviderOperation.QUERY,
    )


def _approval(*, provider_id: str = "provider-a") -> HumanProductionApproval:
    return HumanProductionApproval(
        key=_key(provider_id=provider_id),
        approved_by="human-director",
        approval_reference="change-control-post-web12-a",
        approved_at=NOW,
        correlation_id="corr-human-approval",
    )


def _activation() -> ProductionActivationRecord:
    return ProductionActivationRecord(
        key=_key(),
        state=ProductionActivationState.ACTIVE,
        approval_reference="change-control-post-web12-a",
        external_evidence_id="official-evidence-a",
        changed_by="fiscal-authority-admin",
        changed_at=NOW + timedelta(minutes=1),
        correlation_id="corr-production-activation",
    )


def test_official_homologation_requires_timestamp_not_only_flag_and_external_id() -> None:
    assessment = _assessment(
        external_official=True,
        external_evidence_id="official-evidence-a",
        recorded_at=None,
    )

    assert assessment.internally_ready is True
    assert assessment.officially_homologated is False


def test_external_readiness_reports_internal_readiness_without_inventing_external_facts() -> None:
    report = reconcile_external_readiness(_assessment())

    assert ExternalReadinessFlag.READY_INTERNAL in report.flags
    assert ExternalReadinessFlag.MISSING_OFFICIAL_EVIDENCE in report.flags
    assert ExternalReadinessFlag.MISSING_PILOT_AUTHORIZATION in report.flags
    assert ExternalReadinessFlag.MISSING_HUMAN_APPROVAL in report.flags
    assert ExternalReadinessFlag.BLOCKED_EXTERNAL in report.flags
    assert report.production_activation_present is False


def test_external_readiness_identifies_missing_external_secret_references() -> None:
    report = reconcile_external_readiness(
        _assessment(missing_configuration=("provider_credentials_reference",))
    )

    assert ExternalReadinessFlag.READY_INTERNAL not in report.flags
    assert ExternalReadinessFlag.MISSING_EXTERNAL_CREDENTIAL in report.flags
    assert report.blocked_external is True


def test_external_readiness_rejects_cross_provider_human_approval() -> None:
    with pytest.raises(FiscalValidationError, match="exact assessed cell"):
        reconcile_external_readiness(
            _assessment(
                external_official=True,
                external_evidence_id="official-evidence-a",
                recorded_at=NOW,
            ),
            pilot_authorized=True,
            human_approval=_approval(provider_id="provider-b"),
        )


def test_external_readiness_accepts_only_matching_canonical_approval_and_activation() -> None:
    report = reconcile_external_readiness(
        _assessment(
            external_official=True,
            external_evidence_id="official-evidence-a",
            recorded_at=NOW,
        ),
        pilot_authorized=True,
        human_approval=_approval(),
        activation_record=_activation(),
    )

    assert report.flags == frozenset({ExternalReadinessFlag.READY_INTERNAL})
    assert report.human_approval_present is True
    assert report.production_activation_present is True
    assert report.blocked_external is False
