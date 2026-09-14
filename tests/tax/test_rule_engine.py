from datetime import UTC, datetime

import pytest

from kordena_fiscal.domain import (
    BrazilianJurisdiction,
    ExecutionScope,
    FiscalDocumentKind,
    FiscalEnvironment,
    FiscalProductProfile,
    FiscalUnitCode,
    FiscalValidationError,
    Gtin,
    NcmCode,
    ProductOrigin,
    TaxRegimeCode,
)
from kordena_fiscal.tax import (
    RecipientTaxProfile,
    TaxOperationType,
    TaxRule,
    TaxRuleAmbiguityError,
    TaxRuleContext,
    TaxRuleEngine,
    TaxRuleNotFoundError,
    TaxRuleOutcome,
    TaxRuleSelector,
)


def _instant(day: int) -> datetime:
    return datetime(2026, 9, day, 12, 0, tzinfo=UTC)


def _scope() -> ExecutionScope:
    return ExecutionScope(
        tenant_id="tenant-synthetic",
        unit_id="unit-synthetic",
        environment=FiscalEnvironment.HOMOLOGATION,
        correlation_id="corr-tax-1",
    )


def _product(scope: ExecutionScope | None = None) -> FiscalProductProfile:
    return FiscalProductProfile(
        profile_id="product-profile-1",
        product_id="product-1",
        scope=scope or _scope(),
        commercial_code="SKU-001",
        description="Produto sintético",
        ncm=NcmCode("21069090"),
        commercial_unit=FiscalUnitCode("UN"),
        taxable_unit=FiscalUnitCode("UN"),
        origin=ProductOrigin.NATIONAL,
        effective_from=_instant(1),
        gtin=Gtin("SEM GTIN"),
    )


def _context(**overrides: object) -> TaxRuleContext:
    scope = overrides.pop("scope", _scope())
    assert isinstance(scope, ExecutionScope)
    values: dict[str, object] = {
        "scope": scope,
        "instant": _instant(10),
        "jurisdiction": BrazilianJurisdiction("SP", "3550308"),
        "tax_regime": TaxRegimeCode.SIMPLES_NACIONAL,
        "document_kind": FiscalDocumentKind.NFCE,
        "operation_type": TaxOperationType.SALE,
        "recipient_profile": RecipientTaxProfile.CONSUMER_FINAL,
        "product": _product(scope),
    }
    values.update(overrides)
    return TaxRuleContext(**values)  # type: ignore[arg-type]


def _outcome(cfop: str = "5102") -> TaxRuleOutcome:
    return TaxRuleOutcome(
        cfop=cfop,
        icms_code="102",
        pis_cst="49",
        cofins_cst="49",
        ibs_cbs_classification_code="000001",
        legal_notes=("Regra sintética de teste",),
    )


def _rule(
    rule_id: str,
    selector: TaxRuleSelector,
    *,
    cfop: str = "5102",
    start: int = 1,
    end: int | None = None,
    priority: int = 0,
    version: int = 1,
) -> TaxRule:
    return TaxRule(
        rule_id=rule_id,
        version=version,
        selector=selector,
        outcome=_outcome(cfop),
        source_normative="NORMA-SINTETICA-TESTE",
        effective_from=_instant(start),
        effective_to=_instant(end) if end is not None else None,
        priority=priority,
    )


def test_engine_prefers_more_specific_rule() -> None:
    generic = _rule("generic", TaxRuleSelector(), cfop="5101")
    state = _rule("state", TaxRuleSelector(state_code="SP"), cfop="5102")
    ncm = _rule(
        "state-ncm",
        TaxRuleSelector(state_code="SP", ncm_prefix="2106"),
        cfop="5103",
    )

    decision = TaxRuleEngine().resolve(_context(), [generic, state, ncm])

    assert decision.rule_id == "state-ncm"
    assert decision.outcome.cfop == "5103"
    assert decision.source_normative == "NORMA-SINTETICA-TESTE"
    assert decision.rank == (2, 4, 0)


def test_municipality_rule_beats_state_rule() -> None:
    state = _rule("state", TaxRuleSelector(state_code="SP"))
    municipality = _rule(
        "municipality",
        TaxRuleSelector(state_code="SP", municipality_ibge_code="3550308"),
        cfop="5103",
    )

    decision = TaxRuleEngine().resolve(_context(), [state, municipality])

    assert decision.rule_id == "municipality"


def test_engine_respects_effective_window() -> None:
    expired = _rule("expired", TaxRuleSelector(state_code="SP"), start=1, end=5)
    current = _rule("current", TaxRuleSelector(state_code="SP"), start=5)

    decision = TaxRuleEngine().resolve(_context(), [expired, current])

    assert decision.rule_id == "current"


def test_priority_breaks_tie_after_specificity() -> None:
    low = _rule("low", TaxRuleSelector(state_code="SP"), priority=1)
    high = _rule("high", TaxRuleSelector(state_code="SP"), priority=2)

    decision = TaxRuleEngine().resolve(_context(), [low, high])

    assert decision.rule_id == "high"
    assert decision.rank == (1, 0, 2)


def test_equal_winning_rank_is_rejected_as_ambiguous() -> None:
    first = _rule("first", TaxRuleSelector(state_code="SP"))
    second = _rule("second", TaxRuleSelector(state_code="SP"), version=2)

    with pytest.raises(TaxRuleAmbiguityError, match="ambiguous tax rules"):
        TaxRuleEngine().resolve(_context(), [first, second])


def test_no_match_fails_closed() -> None:
    rio = _rule("rio", TaxRuleSelector(state_code="RJ"))

    with pytest.raises(TaxRuleNotFoundError, match="no effective tax rule"):
        TaxRuleEngine().resolve(_context(), [rio])


def test_selector_matches_regime_document_operation_recipient_and_ncm() -> None:
    selector = TaxRuleSelector(
        state_code="SP",
        municipality_ibge_code="3550308",
        tax_regime=TaxRegimeCode.SIMPLES_NACIONAL,
        document_kind=FiscalDocumentKind.NFCE,
        operation_type=TaxOperationType.SALE,
        recipient_profile=RecipientTaxProfile.CONSUMER_FINAL,
        ncm_prefix="210690",
    )

    assert selector.matches(_context()) is True
    assert selector.matches(_context(tax_regime=TaxRegimeCode.NORMAL)) is False


def test_tax_context_rejects_product_from_another_scope() -> None:
    context_scope = _scope()
    other_scope = ExecutionScope(
        tenant_id="tenant-other",
        unit_id="unit-synthetic",
        environment=FiscalEnvironment.HOMOLOGATION,
        correlation_id="corr-other",
    )

    with pytest.raises(FiscalValidationError, match="same scope"):
        _context(scope=context_scope, product=_product(other_scope))


def test_tax_context_requires_effective_product_snapshot() -> None:
    scope = _scope()
    product = FiscalProductProfile(
        profile_id="future-product",
        product_id="product-1",
        scope=scope,
        commercial_code="SKU-001",
        description="Produto futuro sintético",
        ncm=NcmCode("21069090"),
        commercial_unit=FiscalUnitCode("UN"),
        taxable_unit=FiscalUnitCode("UN"),
        origin=ProductOrigin.NATIONAL,
        effective_from=_instant(20),
    )

    with pytest.raises(FiscalValidationError, match="not effective"):
        _context(scope=scope, product=product)


def test_rule_and_outcome_validate_required_shapes() -> None:
    with pytest.raises(FiscalValidationError, match="cfop"):
        _outcome("510")

    with pytest.raises(FiscalValidationError, match="source_normative"):
        TaxRule(
            rule_id="rule-1",
            version=1,
            selector=TaxRuleSelector(),
            outcome=_outcome(),
            source_normative=" ",
            effective_from=_instant(1),
        )

    with pytest.raises(FiscalValidationError, match="ncm_prefix"):
        TaxRuleSelector(ncm_prefix="2")

    with pytest.raises(FiscalValidationError, match="explicit state_code"):
        TaxRuleSelector(municipality_ibge_code="3550308")
