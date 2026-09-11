from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from kordena_fiscal.compliance import (
    FiscalCapabilityLevel,
    JurisdictionCapabilityError,
    JurisdictionCapabilityMatrix,
    JurisdictionCapabilityRule,
    LegalObligationStatus,
    ReformTaxClassificationSnapshot,
    ReformTaxComponent,
    ReformTaxComponentSnapshot,
    ReformTaxSnapshot,
    RegulatoryArtifactKind,
    RegulatoryArtifactPin,
    RegulatoryBaseline,
    RegulatoryBaselineError,
    RtcEmissionPolicyResolver,
    RtcEmissionPolicyRule,
    RtcPolicyResolutionError,
    TechnicalValidationMode,
)
from kordena_fiscal.domain import (
    BrazilianJurisdiction,
    FiscalDocumentKind,
    FiscalEnvironment,
    FiscalValidationError,
    Money,
    TaxRegimeCode,
)

_ALL_UFS = (
    "AC",
    "AL",
    "AP",
    "AM",
    "BA",
    "CE",
    "DF",
    "ES",
    "GO",
    "MA",
    "MT",
    "MS",
    "MG",
    "PA",
    "PB",
    "PR",
    "PE",
    "PI",
    "RJ",
    "RN",
    "RS",
    "RO",
    "RR",
    "SC",
    "SP",
    "SE",
    "TO",
)


def _instant() -> datetime:
    return datetime(2026, 9, 11, 12, 0, tzinfo=UTC)


def _classification() -> ReformTaxClassificationSnapshot:
    return ReformTaxClassificationSnapshot(
        cst_code="000",
        classification_code="000001",
        classification_table_version="IT-2025.002-v1.60",
    )


def _artifact(
    artifact_id: str,
    version: str,
    published_on: date,
    kind: RegulatoryArtifactKind,
) -> RegulatoryArtifactPin:
    return RegulatoryArtifactPin(
        artifact_id=artifact_id,
        kind=kind,
        version=version,
        published_on=published_on,
        source_reference=f"official:{artifact_id}:{version}",
    )


def test_regulatory_baseline_pins_current_artifact_versions_without_network_dependency() -> None:
    baseline = RegulatoryBaseline(
        baseline_id="rtc-baseline-2026-09-11",
        version=1,
        captured_at=_instant(),
        artifacts=(
            _artifact(
                "NT-2025.002",
                "1.51",
                date(2026, 8, 4),
                RegulatoryArtifactKind.TECHNICAL_NOTE,
            ),
            _artifact(
                "IT-2025.002",
                "1.60",
                date(2026, 6, 23),
                RegulatoryArtifactKind.TECHNICAL_REPORT,
            ),
            _artifact(
                "NT-2026.004",
                "1.01",
                date(2026, 6, 8),
                RegulatoryArtifactKind.TECHNICAL_NOTE,
            ),
            _artifact(
                "NT-2026.007",
                "1.00",
                date(2026, 8, 4),
                RegulatoryArtifactKind.TECHNICAL_NOTE,
            ),
            _artifact(
                "ATO-RFB-CGIBS-4-2026",
                "4/2026",
                date(2026, 7, 31),
                RegulatoryArtifactKind.JOINT_ACT,
            ),
            _artifact(
                "ATO-TECNICO-RFB-CGIBS-1-2026",
                "1/2026",
                date(2026, 7, 31),
                RegulatoryArtifactKind.TECHNICAL_JOINT_ACT,
            ),
        ),
    )

    assert baseline.artifact("NT-2025.002").version == "1.51"
    assert baseline.artifact("IT-2025.002").version == "1.60"


def test_regulatory_baseline_rejects_duplicate_artifact_version() -> None:
    artifact = _artifact(
        "NT-2025.002",
        "1.51",
        date(2026, 8, 4),
        RegulatoryArtifactKind.TECHNICAL_NOTE,
    )
    with pytest.raises(RegulatoryBaselineError, match="duplicate artifact"):
        RegulatoryBaseline(
            baseline_id="duplicated",
            version=1,
            captured_at=_instant(),
            artifacts=(artifact, artifact),
        )


def test_reform_tax_snapshot_keeps_ibs_cbs_is_components_explicit_and_unique() -> None:
    classification = _classification()
    snapshot = ReformTaxSnapshot(
        rule_set_id="rtc-rule-set",
        rule_set_version=7,
        source_normative="official-versioned-rule-set",
        resolved_at=_instant(),
        baseline_id="rtc-baseline-2026-09-11",
        baseline_version=1,
        components=(
            ReformTaxComponentSnapshot(
                component=ReformTaxComponent.CBS,
                tax_base=Money(Decimal("100.00")),
                nominal_rate_percent=Decimal("0.90"),
                effective_rate_percent=Decimal("0.90"),
                tax_amount=Money(Decimal("0.90")),
                classification=classification,
            ),
            ReformTaxComponentSnapshot(
                component=ReformTaxComponent.IBS_STATE,
                tax_base=Money(Decimal("100.00")),
                nominal_rate_percent=Decimal("0.05"),
                effective_rate_percent=Decimal("0.05"),
                tax_amount=Money(Decimal("0.05")),
                classification=classification,
            ),
            ReformTaxComponentSnapshot(
                component=ReformTaxComponent.IBS_MUNICIPAL,
                tax_base=Money(Decimal("100.00")),
                nominal_rate_percent=Decimal("0.05"),
                effective_rate_percent=Decimal("0.05"),
                tax_amount=Money(Decimal("0.05")),
                classification=classification,
            ),
            ReformTaxComponentSnapshot(
                component=ReformTaxComponent.SELECTIVE_TAX,
                tax_base=Money(Decimal("0.00")),
                nominal_rate_percent=Decimal("0.00"),
                effective_rate_percent=Decimal("0.00"),
                tax_amount=Money(Decimal("0.00")),
                classification=classification,
            ),
        ),
    )

    assert {item.component for item in snapshot.components} == set(ReformTaxComponent)

    duplicate = snapshot.components[0]
    with pytest.raises(FiscalValidationError, match="components must be unique"):
        ReformTaxSnapshot(
            rule_set_id="rtc-rule-set",
            rule_set_version=7,
            source_normative="official-versioned-rule-set",
            resolved_at=_instant(),
            baseline_id="rtc-baseline-2026-09-11",
            baseline_version=1,
            components=(duplicate, duplicate),
        )


def test_tax_component_rejects_invalid_percent_without_inventing_formula() -> None:
    with pytest.raises(FiscalValidationError, match="between 0 and 100"):
        ReformTaxComponentSnapshot(
            component=ReformTaxComponent.CBS,
            tax_base=Money(Decimal("100.00")),
            nominal_rate_percent=Decimal("101"),
            effective_rate_percent=Decimal("1"),
            tax_amount=Money(Decimal("1")),
            classification=_classification(),
        )


def test_legal_obligation_and_technical_rejection_mode_are_separate_axes() -> None:
    resolver = RtcEmissionPolicyResolver(
        (
            RtcEmissionPolicyRule(
                rule_id="nfe-normal-2026",
                version=1,
                document_kind=FiscalDocumentKind.NFE,
                effective_from=datetime(2026, 8, 3, tzinfo=UTC),
                obligation=LegalObligationStatus.REQUIRED,
                validation_mode=TechnicalValidationMode.TOLERANT,
                source_normative="ATO-4-2026 + technical-validation-update",
                tax_regime=TaxRegimeCode.NORMAL,
            ),
        )
    )

    policy = resolver.resolve(
        document_kind=FiscalDocumentKind.NFE,
        tax_regime=TaxRegimeCode.NORMAL,
        instant=_instant(),
    )

    assert policy.obligation is LegalObligationStatus.REQUIRED
    assert policy.validation_mode is TechnicalValidationMode.TOLERANT


def test_rtc_policy_resolution_fails_closed_when_absent_or_ambiguous() -> None:
    generic = RtcEmissionPolicyRule(
        rule_id="generic-a",
        version=1,
        document_kind=FiscalDocumentKind.NFCE,
        effective_from=datetime(2026, 1, 1, tzinfo=UTC),
        obligation=LegalObligationStatus.DEFERRED,
        validation_mode=TechnicalValidationMode.TOLERANT,
        source_normative="synthetic-policy-a",
    )
    duplicate_rank = RtcEmissionPolicyRule(
        rule_id="generic-b",
        version=1,
        document_kind=FiscalDocumentKind.NFCE,
        effective_from=datetime(2026, 1, 1, tzinfo=UTC),
        obligation=LegalObligationStatus.DEFERRED,
        validation_mode=TechnicalValidationMode.TOLERANT,
        source_normative="synthetic-policy-b",
    )

    with pytest.raises(RtcPolicyResolutionError, match="ambiguous"):
        RtcEmissionPolicyResolver((generic, duplicate_rank)).resolve(
            document_kind=FiscalDocumentKind.NFCE,
            tax_regime=TaxRegimeCode.NORMAL,
            instant=_instant(),
        )

    with pytest.raises(RtcPolicyResolutionError, match="no effective"):
        RtcEmissionPolicyResolver((generic,)).resolve(
            document_kind=FiscalDocumentKind.NFE,
            tax_regime=TaxRegimeCode.NORMAL,
            instant=_instant(),
        )


def _state_rule(state_code: str) -> JurisdictionCapabilityRule:
    return JurisdictionCapabilityRule(
        rule_id=f"contract-{state_code.lower()}-nfe",
        version=1,
        state_code=state_code,
        document_kind=FiscalDocumentKind.NFE,
        environment=FiscalEnvironment.HOMOLOGATION,
        capability_level=FiscalCapabilityLevel.CONTRACT_ONLY,
        validation_mode=TechnicalValidationMode.TOLERANT,
        effective_from=datetime(2026, 1, 1, tzinfo=UTC),
        source_normative="synthetic-contract-coverage-only",
    )


def test_all_27_ufs_require_explicit_rules_and_resolve_without_implicit_fallback() -> None:
    matrix = JurisdictionCapabilityMatrix(tuple(_state_rule(uf) for uf in _ALL_UFS))

    resolved = {
        uf: matrix.resolve(
            jurisdiction=BrazilianJurisdiction(uf),
            document_kind=FiscalDocumentKind.NFE,
            environment=FiscalEnvironment.HOMOLOGATION,
            instant=_instant(),
        ).state_code
        for uf in _ALL_UFS
    }

    assert set(resolved) == set(_ALL_UFS)
    assert len(resolved) == 27


def test_capability_matrix_blocks_missing_environment_and_insufficient_readiness() -> None:
    matrix = JurisdictionCapabilityMatrix((_state_rule("SP"),))

    with pytest.raises(JurisdictionCapabilityError, match="no explicit"):
        matrix.resolve(
            jurisdiction=BrazilianJurisdiction("SP"),
            document_kind=FiscalDocumentKind.NFE,
            environment=FiscalEnvironment.PRODUCTION,
            instant=_instant(),
        )

    with pytest.raises(JurisdictionCapabilityError, match="below"):
        matrix.resolve(
            jurisdiction=BrazilianJurisdiction("SP"),
            document_kind=FiscalDocumentKind.NFE,
            environment=FiscalEnvironment.HOMOLOGATION,
            instant=_instant(),
            minimum_level=FiscalCapabilityLevel.HOMOLOGATION_READY,
        )


def test_municipality_rule_overrides_state_rule_for_nfse() -> None:
    state = JurisdictionCapabilityRule(
        rule_id="sp-nfse-state",
        version=1,
        state_code="SP",
        document_kind=FiscalDocumentKind.NFSE,
        environment=FiscalEnvironment.HOMOLOGATION,
        capability_level=FiscalCapabilityLevel.CONTRACT_ONLY,
        validation_mode=TechnicalValidationMode.TOLERANT,
        effective_from=datetime(2026, 1, 1, tzinfo=UTC),
        source_normative="state-fallback-synthetic",
    )
    city = JurisdictionCapabilityRule(
        rule_id="sp-sao-paulo-nfse",
        version=1,
        state_code="SP",
        municipality_ibge_code="3550308",
        document_kind=FiscalDocumentKind.NFSE,
        environment=FiscalEnvironment.HOMOLOGATION,
        capability_level=FiscalCapabilityLevel.HOMOLOGATION_READY,
        validation_mode=TechnicalValidationMode.STRICT_REJECTION,
        effective_from=datetime(2026, 1, 1, tzinfo=UTC),
        source_normative="municipal-contract-synthetic",
    )
    matrix = JurisdictionCapabilityMatrix((state, city))

    selected = matrix.resolve(
        jurisdiction=BrazilianJurisdiction("SP", "3550308"),
        document_kind=FiscalDocumentKind.NFSE,
        environment=FiscalEnvironment.HOMOLOGATION,
        instant=_instant(),
    )

    assert selected.rule_id == "sp-sao-paulo-nfse"
    assert selected.capability_level is FiscalCapabilityLevel.HOMOLOGATION_READY


def test_equal_specificity_jurisdiction_rules_are_ambiguous_fail_closed() -> None:
    first = _state_rule("SP")
    second = JurisdictionCapabilityRule(
        rule_id="contract-sp-nfe-b",
        version=1,
        state_code="SP",
        document_kind=FiscalDocumentKind.NFE,
        environment=FiscalEnvironment.HOMOLOGATION,
        capability_level=FiscalCapabilityLevel.CONTRACT_ONLY,
        validation_mode=TechnicalValidationMode.TOLERANT,
        effective_from=datetime(2026, 1, 1, tzinfo=UTC),
        source_normative="second-synthetic-rule",
    )

    with pytest.raises(JurisdictionCapabilityError, match="ambiguous"):
        JurisdictionCapabilityMatrix((first, second)).resolve(
            jurisdiction=BrazilianJurisdiction("SP"),
            document_kind=FiscalDocumentKind.NFE,
            environment=FiscalEnvironment.HOMOLOGATION,
            instant=_instant(),
        )
