from __future__ import annotations

from datetime import UTC, datetime

import pytest

from kordena_fiscal.compliance import (
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
from kordena_fiscal.gateway import ProviderOperation
from kordena_fiscal.homologation import (
    HomologationEvidence,
    HomologationGateEvaluator,
    HomologationGateKey,
    HomologationGateNotConfiguredError,
    TechnicalGateState,
    TechnicalHomologationMatrix,
    TechnicalHomologationRule,
)
from kordena_fiscal.resilience import (
    CircuitBreakerPolicy,
    CircuitBreakerRegistry,
    CircuitKey,
    CircuitState,
)

NOW = datetime(2026, 9, 13, 13, 0, tzinfo=UTC)
SP = BrazilianJurisdiction("SP")
SAO_PAULO = BrazilianJurisdiction("SP", "3550308")


def _evidence(**changes: bool) -> HomologationEvidence:
    values = {
        "provider_adapter_available": True,
        "credentials_reference_configured": True,
        "signer_capability": True,
        "csc_reference_configured": True,
        "transport_configured": True,
        "resilience_certified": True,
        "contract_tests_certified": True,
        "jurisdiction_mapping": True,
        "operation_supported": True,
    }
    values.update(changes)
    return HomologationEvidence(**values)


def _key(
    *,
    provider_id: str = "provider-a",
    kind: FiscalDocumentKind = FiscalDocumentKind.NFE,
    jurisdiction: BrazilianJurisdiction = SP,
    environment: FiscalEnvironment = FiscalEnvironment.HOMOLOGATION,
    operation: ProviderOperation = ProviderOperation.AUTHORIZE,
) -> HomologationGateKey:
    return HomologationGateKey(
        provider_id=provider_id,
        document_kind=kind,
        jurisdiction=jurisdiction,
        environment=environment,
        operation=operation,
    )


def _rule(
    key: HomologationGateKey,
    *,
    evidence: HomologationEvidence | None = None,
    requires_signer: bool = True,
    requires_csc: bool = False,
) -> TechnicalHomologationRule:
    return TechnicalHomologationRule(
        key=key,
        evidence=evidence or _evidence(),
        requires_signer=requires_signer,
        requires_csc=requires_csc,
    )


def _readiness(
    *,
    kind: FiscalDocumentKind = FiscalDocumentKind.NFE,
    jurisdiction: BrazilianJurisdiction = SP,
    environment: FiscalEnvironment = FiscalEnvironment.HOMOLOGATION,
    level: FiscalCapabilityLevel = FiscalCapabilityLevel.HOMOLOGATION_READY,
    actions: frozenset[FiscalActionCapability] = frozenset({FiscalActionCapability.ISSUE}),
) -> CapabilityReadinessService:
    return CapabilityReadinessService(
        JurisdictionCapabilityMatrix(
            (
                JurisdictionCapabilityRule(
                    rule_id=(
                        f"gate-{jurisdiction.state_code}-"
                        f"{jurisdiction.municipality_ibge_code or 'state'}-{kind.value}-"
                        f"{environment.value}-{level.name.lower()}"
                    ),
                    version=1,
                    state_code=jurisdiction.state_code,
                    municipality_ibge_code=jurisdiction.municipality_ibge_code,
                    document_kind=kind,
                    environment=environment,
                    capability_level=level,
                    validation_mode=TechnicalValidationMode.STRICT_REJECTION,
                    effective_from=datetime(2026, 1, 1, tzinfo=UTC),
                    source_normative="synthetic technical gate evidence",
                    capabilities=actions,
                ),
            )
        )
    )


def test_complete_technical_evidence_combines_with_central_homologation_readiness() -> None:
    key = _key()
    evaluator = HomologationGateEvaluator(
        matrix=TechnicalHomologationMatrix((_rule(key),)),
        readiness=_readiness(),
    )

    result = evaluator.evaluate(key, instant=NOW)

    assert result.technical_state is TechnicalGateState.TECHNICALLY_CERTIFIED
    assert result.readiness is FiscalCapabilityLevel.HOMOLOGATION_READY
    assert result.execution_authorized is True
    assert result.homologation_ready is True
    assert result.missing_evidence == ()


def test_missing_evidence_never_becomes_ready_from_configuration_alone() -> None:
    key = _key()
    rule = _rule(
        key,
        evidence=_evidence(contract_tests_certified=False, resilience_certified=False),
    )
    result = HomologationGateEvaluator(
        matrix=TechnicalHomologationMatrix((rule,)),
        readiness=_readiness(),
    ).evaluate(key, instant=NOW)

    assert result.technical_state is TechnicalGateState.CONTRACT_READY
    assert result.execution_authorized is False
    assert result.homologation_ready is False
    assert set(result.missing_evidence) == {
        "contract_tests_certified",
        "resilience_certified",
    }


def test_missing_provider_adapter_is_not_configured() -> None:
    key = _key()
    rule = _rule(key, evidence=_evidence(provider_adapter_available=False))
    result = HomologationGateEvaluator(
        matrix=TechnicalHomologationMatrix((rule,)),
        readiness=_readiness(),
    ).evaluate(key, instant=NOW)

    assert result.technical_state is TechnicalGateState.NOT_CONFIGURED
    assert result.execution_authorized is False


def test_unknown_provider_combination_fails_closed_without_default() -> None:
    configured = _key(provider_id="provider-a")
    matrix = TechnicalHomologationMatrix((_rule(configured),))

    with pytest.raises(HomologationGateNotConfiguredError, match="exact provider"):
        matrix.resolve(_key(provider_id="provider-b"))


def test_contract_only_central_readiness_is_never_promoted_by_technical_gate() -> None:
    key = _key()
    evaluator = HomologationGateEvaluator(
        matrix=TechnicalHomologationMatrix((_rule(key),)),
        readiness=_readiness(level=FiscalCapabilityLevel.CONTRACT_ONLY),
    )

    with pytest.raises(JurisdictionCapabilityError, match="below"):
        evaluator.evaluate(key, instant=NOW)


def test_production_requires_central_production_approval() -> None:
    key = _key(environment=FiscalEnvironment.PRODUCTION)
    evaluator = HomologationGateEvaluator(
        matrix=TechnicalHomologationMatrix((_rule(key),)),
        readiness=_readiness(
            environment=FiscalEnvironment.PRODUCTION,
            level=FiscalCapabilityLevel.HOMOLOGATION_READY,
        ),
    )

    with pytest.raises(JurisdictionCapabilityError, match="below"):
        evaluator.evaluate(key, instant=NOW)


def test_nfce_missing_csc_is_explicit_contract_gap() -> None:
    key = _key(kind=FiscalDocumentKind.NFCE)
    rule = _rule(
        key,
        evidence=_evidence(csc_reference_configured=False),
        requires_csc=True,
    )
    result = HomologationGateEvaluator(
        matrix=TechnicalHomologationMatrix((rule,)),
        readiness=_readiness(kind=FiscalDocumentKind.NFCE),
    ).evaluate(key, instant=NOW)

    assert result.technical_state is TechnicalGateState.CONTRACT_READY
    assert result.missing_evidence == ("csc_reference_configured",)
    assert result.execution_authorized is False


def test_nfse_gate_requires_municipality_and_resolves_exact_municipal_context() -> None:
    with pytest.raises(FiscalValidationError, match="municipality"):
        _key(kind=FiscalDocumentKind.NFSE, jurisdiction=SP)

    key = _key(kind=FiscalDocumentKind.NFSE, jurisdiction=SAO_PAULO)
    result = HomologationGateEvaluator(
        matrix=TechnicalHomologationMatrix((_rule(key),)),
        readiness=_readiness(kind=FiscalDocumentKind.NFSE, jurisdiction=SAO_PAULO),
    ).evaluate(key, instant=NOW)

    assert result.technical_state is TechnicalGateState.TECHNICALLY_CERTIFIED
    assert result.homologation_ready is True
    assert result.key.jurisdiction.municipality_ibge_code == "3550308"


def test_two_providers_coexist_but_evidence_and_gate_keys_remain_isolated() -> None:
    key_a = _key(provider_id="provider-a")
    key_b = _key(provider_id="provider-b")
    rule_a = _rule(key_a)
    rule_b = _rule(
        key_b,
        evidence=_evidence(credentials_reference_configured=False),
    )
    matrix = TechnicalHomologationMatrix((rule_a, rule_b))
    evaluator = HomologationGateEvaluator(matrix=matrix, readiness=_readiness())

    result_a = evaluator.evaluate(key_a, instant=NOW)
    result_b = evaluator.evaluate(key_b, instant=NOW)

    assert result_a.technical_state is TechnicalGateState.TECHNICALLY_CERTIFIED
    assert result_a.execution_authorized is True
    assert result_b.technical_state is TechnicalGateState.CONTRACT_READY
    assert result_b.execution_authorized is False
    assert result_b.missing_evidence == ("credentials_reference_configured",)


def test_unsupported_operation_remains_technical_gap_even_if_readiness_exists() -> None:
    key = _key(operation=ProviderOperation.CANCEL)
    rule = _rule(key, evidence=_evidence(operation_supported=False))
    actions = frozenset(
        {
            FiscalActionCapability.ISSUE,
            FiscalActionCapability.CANCEL,
        }
    )
    readiness = _readiness(actions=actions)

    result = HomologationGateEvaluator(
        matrix=TechnicalHomologationMatrix((rule,)),
        readiness=readiness,
    ).evaluate(key, instant=NOW)

    assert result.technical_state is TechnicalGateState.CONTRACT_READY
    assert result.execution_authorized is False
    assert result.missing_evidence == ("operation_supported",)


def test_circuit_failure_for_provider_a_does_not_change_provider_b_gate_or_circuit() -> None:
    key_a = _key(provider_id="provider-a")
    key_b = _key(provider_id="provider-b")
    evaluator = HomologationGateEvaluator(
        matrix=TechnicalHomologationMatrix((_rule(key_a), _rule(key_b))),
        readiness=_readiness(),
    )
    circuits = CircuitBreakerRegistry(
        policy=CircuitBreakerPolicy(failure_threshold=1, recovery_timeout_seconds=30)
    )
    circuit_a = CircuitKey("provider-a", "homologation", "SP")
    circuit_b = CircuitKey("provider-b", "homologation", "SP")

    circuits.record_failure(circuit_a)
    result_b = evaluator.evaluate(key_b, instant=NOW)

    assert circuits.state(circuit_a) is CircuitState.OPEN
    assert circuits.state(circuit_b) is CircuitState.CLOSED
    assert result_b.execution_authorized is True


def test_gate_evaluation_is_read_only_over_central_readiness_snapshot() -> None:
    key = _key()
    readiness = _readiness()
    before = readiness.query(
        jurisdiction=SP,
        document_kind=FiscalDocumentKind.NFE,
        environment=FiscalEnvironment.HOMOLOGATION,
        instant=NOW,
    )
    evaluator = HomologationGateEvaluator(
        matrix=TechnicalHomologationMatrix((_rule(key),)),
        readiness=readiness,
    )

    result = evaluator.evaluate(key, instant=NOW)
    after = readiness.query(
        jurisdiction=SP,
        document_kind=FiscalDocumentKind.NFE,
        environment=FiscalEnvironment.HOMOLOGATION,
        instant=NOW,
    )

    assert before == after
    assert result.readiness_snapshot == before
