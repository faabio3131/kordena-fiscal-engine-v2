from datetime import UTC, datetime

import pytest

from kordena_fiscal.compliance import (
    CapabilityReadinessError,
    CapabilityReadinessService,
    FiscalActionCapability,
    FiscalCapabilityLevel,
    JurisdictionCapabilityError,
    JurisdictionCapabilityMatrix,
    JurisdictionCapabilityRule,
    TechnicalValidationMode,
)
from kordena_fiscal.domain import (
    BrazilianJurisdiction,
    FiscalDocumentKind,
    FiscalEnvironment,
    FiscalValidationError,
)


def _instant() -> datetime:
    return datetime(2026, 9, 11, 20, 0, tzinfo=UTC)


def _rule(
    *,
    rule_id: str = "sp-nfe-homologation",
    version: int = 3,
    state_code: str = "SP",
    municipality_ibge_code: str | None = None,
    document_kind: FiscalDocumentKind = FiscalDocumentKind.NFE,
    environment: FiscalEnvironment = FiscalEnvironment.HOMOLOGATION,
    readiness: FiscalCapabilityLevel = FiscalCapabilityLevel.HOMOLOGATION_READY,
    capabilities: frozenset[FiscalActionCapability] = frozenset(
        {
            FiscalActionCapability.ISSUE,
            FiscalActionCapability.QUERY,
            FiscalActionCapability.CANCEL,
        }
    ),
    priority: int = 0,
) -> JurisdictionCapabilityRule:
    return JurisdictionCapabilityRule(
        rule_id=rule_id,
        version=version,
        state_code=state_code,
        municipality_ibge_code=municipality_ibge_code,
        document_kind=document_kind,
        environment=environment,
        capability_level=readiness,
        validation_mode=TechnicalValidationMode.TOLERANT,
        effective_from=datetime(2026, 1, 1, tzinfo=UTC),
        source_normative=f"synthetic-provenance:{rule_id}:v{version}",
        priority=priority,
        capabilities=capabilities,
    )


def _service(*rules: JurisdictionCapabilityRule) -> CapabilityReadinessService:
    return CapabilityReadinessService(JurisdictionCapabilityMatrix(tuple(rules)))


def test_query_returns_versioned_deterministic_bridge_snapshot() -> None:
    service = _service(_rule())

    snapshot = service.query(
        jurisdiction=BrazilianJurisdiction("SP"),
        document_kind=FiscalDocumentKind.NFE,
        environment=FiscalEnvironment.HOMOLOGATION,
        instant=_instant(),
    )

    assert snapshot.readiness is FiscalCapabilityLevel.HOMOLOGATION_READY
    assert snapshot.public_capabilities == ("nfe", "issue", "query", "cancel")
    assert snapshot.capability_version.startswith("r3-")
    assert len(snapshot.capability_version) == 19
    assert snapshot.provenance == "synthetic-provenance:sp-nfe-homologation:v3"
    assert snapshot.to_bridge_response(correlation_id="corr-001") == {
        "contract_version": "1.0.0",
        "readiness": "HOMOLOGATION_READY",
        "capability_version": snapshot.capability_version,
        "capabilities": ["nfe", "issue", "query", "cancel"],
        "correlation_id": "corr-001",
        "provenance": snapshot.provenance,
    }


def test_contract_only_is_queryable_but_not_executable_in_homologation() -> None:
    service = _service(
        _rule(
            readiness=FiscalCapabilityLevel.CONTRACT_ONLY,
            capabilities=frozenset({FiscalActionCapability.ISSUE}),
        )
    )

    snapshot = service.query(
        jurisdiction=BrazilianJurisdiction("SP"),
        document_kind=FiscalDocumentKind.NFE,
        environment=FiscalEnvironment.HOMOLOGATION,
        instant=_instant(),
    )
    assert snapshot.public_capabilities == ("nfe", "issue")

    with pytest.raises(JurisdictionCapabilityError, match="below"):
        service.require_action(
            jurisdiction=BrazilianJurisdiction("SP"),
            document_kind=FiscalDocumentKind.NFE,
            environment=FiscalEnvironment.HOMOLOGATION,
            instant=_instant(),
            action=FiscalActionCapability.ISSUE,
        )


def test_require_action_allows_only_explicit_homologation_capabilities() -> None:
    service = _service(
        _rule(capabilities=frozenset({FiscalActionCapability.ISSUE}))
    )

    allowed = service.require_action(
        jurisdiction=BrazilianJurisdiction("SP"),
        document_kind=FiscalDocumentKind.NFE,
        environment=FiscalEnvironment.HOMOLOGATION,
        instant=_instant(),
        action=FiscalActionCapability.ISSUE,
    )
    assert allowed.readiness is FiscalCapabilityLevel.HOMOLOGATION_READY

    with pytest.raises(CapabilityReadinessError, match="cancel"):
        service.require_action(
            jurisdiction=BrazilianJurisdiction("SP"),
            document_kind=FiscalDocumentKind.NFE,
            environment=FiscalEnvironment.HOMOLOGATION,
            instant=_instant(),
            action=FiscalActionCapability.CANCEL,
        )


def test_production_execution_requires_production_approved_rule() -> None:
    insufficient = _rule(
        rule_id="sp-nfe-production-not-approved",
        environment=FiscalEnvironment.PRODUCTION,
        readiness=FiscalCapabilityLevel.HOMOLOGATION_READY,
        capabilities=frozenset({FiscalActionCapability.ISSUE}),
    )
    with pytest.raises(JurisdictionCapabilityError, match="below"):
        _service(insufficient).require_action(
            jurisdiction=BrazilianJurisdiction("SP"),
            document_kind=FiscalDocumentKind.NFE,
            environment=FiscalEnvironment.PRODUCTION,
            instant=_instant(),
            action=FiscalActionCapability.ISSUE,
        )

    approved = _rule(
        rule_id="sp-nfe-production-approved",
        environment=FiscalEnvironment.PRODUCTION,
        readiness=FiscalCapabilityLevel.PRODUCTION_APPROVED,
        capabilities=frozenset({FiscalActionCapability.ISSUE}),
    )
    snapshot = _service(approved).require_action(
        jurisdiction=BrazilianJurisdiction("SP"),
        document_kind=FiscalDocumentKind.NFE,
        environment=FiscalEnvironment.PRODUCTION,
        instant=_instant(),
        action=FiscalActionCapability.ISSUE,
    )
    assert snapshot.readiness is FiscalCapabilityLevel.PRODUCTION_APPROVED


def test_nfse_municipality_rule_overrides_state_readiness_and_actions() -> None:
    state = _rule(
        rule_id="sp-nfse-state-contract",
        document_kind=FiscalDocumentKind.NFSE,
        readiness=FiscalCapabilityLevel.CONTRACT_ONLY,
        capabilities=frozenset(),
    )
    city = _rule(
        rule_id="sp-sao-paulo-nfse-homologation",
        municipality_ibge_code="3550308",
        document_kind=FiscalDocumentKind.NFSE,
        readiness=FiscalCapabilityLevel.HOMOLOGATION_READY,
        capabilities=frozenset(
            {
                FiscalActionCapability.ISSUE,
                FiscalActionCapability.QUERY,
                FiscalActionCapability.CANCEL,
            }
        ),
    )

    snapshot = _service(state, city).query(
        jurisdiction=BrazilianJurisdiction("SP", "3550308"),
        document_kind=FiscalDocumentKind.NFSE,
        environment=FiscalEnvironment.HOMOLOGATION,
        instant=_instant(),
    )

    assert snapshot.readiness is FiscalCapabilityLevel.HOMOLOGATION_READY
    assert snapshot.public_capabilities == ("nfse", "issue", "query", "cancel")
    assert snapshot.provenance == "synthetic-provenance:sp-sao-paulo-nfse-homologation:v3"


def test_document_family_does_not_imply_any_executable_action() -> None:
    snapshot = _service(
        _rule(readiness=FiscalCapabilityLevel.CONTRACT_ONLY, capabilities=frozenset())
    ).query(
        jurisdiction=BrazilianJurisdiction("SP"),
        document_kind=FiscalDocumentKind.NFE,
        environment=FiscalEnvironment.HOMOLOGATION,
        instant=_instant(),
    )

    assert snapshot.public_capabilities == ("nfe",)


@pytest.mark.parametrize(
    ("document_kind", "state_code", "municipality_code"),
    [
        (FiscalDocumentKind.NFE, "SP", None),
        (FiscalDocumentKind.NFCE, "RJ", None),
        (FiscalDocumentKind.NFSE, "MG", "3106200"),
    ],
)
def test_all_public_document_families_are_resolved_only_by_explicit_rule(
    document_kind: FiscalDocumentKind,
    state_code: str,
    municipality_code: str | None,
) -> None:
    rule = _rule(
        rule_id=f"{state_code.lower()}-{document_kind.value}-explicit",
        state_code=state_code,
        municipality_ibge_code=municipality_code,
        document_kind=document_kind,
        capabilities=frozenset({FiscalActionCapability.QUERY}),
    )
    snapshot = _service(rule).query(
        jurisdiction=BrazilianJurisdiction(state_code, municipality_code),
        document_kind=document_kind,
        environment=FiscalEnvironment.HOMOLOGATION,
        instant=_instant(),
    )

    assert snapshot.public_capabilities == (document_kind.value, "query")


def test_invalid_action_declarations_fail_closed_at_rule_construction() -> None:
    with pytest.raises(FiscalValidationError, match="frozenset"):
        _rule(capabilities={FiscalActionCapability.ISSUE})  # type: ignore[arg-type]
