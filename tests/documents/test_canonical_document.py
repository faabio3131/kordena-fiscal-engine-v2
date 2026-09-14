from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from kordena_fiscal.documents import (
    CanonicalFiscalDocument,
    FiscalLineSnapshot,
    FiscalPaymentSnapshot,
    PaymentMethodKind,
    canonical_sha256,
    to_canonical_json,
    to_canonical_payload,
)
from kordena_fiscal.domain import (
    BrazilianJurisdiction,
    CnaeCode,
    Cnpj,
    ExecutionScope,
    FiscalAddress,
    FiscalDocumentKind,
    FiscalEnvironment,
    FiscalProductProfile,
    FiscalProfile,
    FiscalUnitCode,
    FiscalValidationError,
    Gtin,
    Money,
    NcmCode,
    ProductOrigin,
    SourceReference,
    StateRegistration,
    TaxRegimeCode,
)
from kordena_fiscal.tax import (
    RestaurantSupplyDecision,
    RestaurantTaxTreatment,
    TaxDecision,
    TaxRuleOutcome,
)


def _instant() -> datetime:
    return datetime(2026, 9, 10, 20, 0, tzinfo=UTC)


def _scope(tenant: str = "tenant-test") -> ExecutionScope:
    return ExecutionScope(
        tenant_id=tenant,
        unit_id="unit-test",
        environment=FiscalEnvironment.HOMOLOGATION,
        correlation_id="corr-document-1",
    )


def _issuer(scope: ExecutionScope | None = None) -> FiscalProfile:
    return FiscalProfile(
        profile_id="issuer-profile-1",
        scope=scope or _scope(),
        cnpj=Cnpj("12.345.678/0001-95"),
        legal_name="Empresa Fiscal Sintetica Ltda",
        tax_regime=TaxRegimeCode.SIMPLES_NACIONAL,
        state_registration=StateRegistration("SP", "123456789"),
        primary_cnae=CnaeCode("5611-2/01"),
        address=FiscalAddress(
            street="Rua Sintetica",
            number="100",
            district="Centro",
            municipality_name="Sao Paulo",
            jurisdiction=BrazilianJurisdiction("SP", "3550308"),
            postal_code="01001000",
        ),
        effective_from=datetime(2026, 1, 1, tzinfo=UTC),
    )


def _product(scope: ExecutionScope | None = None) -> FiscalProductProfile:
    return FiscalProductProfile(
        profile_id="product-profile-1",
        product_id="product-1",
        scope=scope or _scope(),
        commercial_code="SKU-001",
        description="Produto fiscal sintetico",
        ncm=NcmCode("21069090"),
        commercial_unit=FiscalUnitCode("UN"),
        taxable_unit=FiscalUnitCode("UN"),
        origin=ProductOrigin.NATIONAL,
        effective_from=datetime(2026, 1, 1, tzinfo=UTC),
        gtin=Gtin("SEM GTIN"),
    )


def _tax_decision() -> TaxDecision:
    return TaxDecision(
        rule_id="rule-synthetic-1",
        rule_version=3,
        source_normative="NORMA-SINTETICA",
        outcome=TaxRuleOutcome(
            cfop="5102",
            icms_code="102",
            pis_cst="49",
            cofins_cst="49",
            ibs_cbs_classification_code="000001",
            legal_notes=("Nota sintetica",),
        ),
        rank=(3, 4, 1),
    )


def _restaurant_decision() -> RestaurantSupplyDecision:
    return RestaurantSupplyDecision(
        treatment=RestaurantTaxTreatment.SPECIFIC_REGIME,
        reason_code="prepared_food_or_non_alcoholic_beverage_in_specific_regime",
        normative_references=("NORMA-RESTAURANTE-SINTETICA",),
        rate_reduction_percent=Decimal("40.0"),
        recipient_credit_allowed=False,
    )


def _line(
    *,
    scope: ExecutionScope | None = None,
    line_number: int = 1,
    gross: str = "20.00",
    discount: str = "2.00",
    surcharge: str = "1.00",
) -> FiscalLineSnapshot:
    return FiscalLineSnapshot(
        line_number=line_number,
        product=_product(scope),
        quantity=Decimal("2.000"),
        unit_price=Money(Decimal("10.00")),
        gross_amount=Money(Decimal(gross)),
        discount_amount=Money(Decimal(discount)),
        surcharge_amount=Money(Decimal(surcharge)),
        tax_decision=_tax_decision(),
        restaurant_decision=_restaurant_decision(),
    )


def _document(**overrides: object) -> CanonicalFiscalDocument:
    scope = overrides.pop("scope", _scope())
    assert isinstance(scope, ExecutionScope)
    values: dict[str, object] = {
        "document_id": "doc-1",
        "scope": scope,
        "source": SourceReference("sale", "sale-42"),
        "document_kind": FiscalDocumentKind.NFCE,
        "issued_at": _instant(),
        "issuer": _issuer(scope),
        "items": (_line(scope=scope),),
        "payments": (
            FiscalPaymentSnapshot(
                method=PaymentMethodKind.PIX,
                amount=Money(Decimal("20.00")),
                provider_reference="payment-synthetic-1",
            ),
        ),
        "change_amount": Money(Decimal("1.00")),
    }
    values.update(overrides)
    return CanonicalFiscalDocument(**values)  # type: ignore[arg-type]


def test_document_derives_totals_without_implicit_rounding() -> None:
    document = _document()

    assert document.totals.gross_amount.amount == Decimal("20.00")
    assert document.totals.discount_amount.amount == Decimal("2.00")
    assert document.totals.surcharge_amount.amount == Decimal("1.00")
    assert document.totals.net_amount.amount == Decimal("19.00")
    assert document.totals.payment_amount.amount == Decimal("20.00")
    assert document.totals.change_amount.amount == Decimal("1.00")


def test_canonical_json_is_stable_across_decimal_scale_and_timezone_representation() -> None:
    first = _document()
    local_tz = timezone(timedelta(hours=-3))
    second = _document(
        issued_at=datetime(2026, 9, 10, 17, 0, tzinfo=local_tz),
        items=(
            _line(gross="20.0", discount="2.0", surcharge="1.0"),
        ),
        payments=(
            FiscalPaymentSnapshot(
                method=PaymentMethodKind.PIX,
                amount=Money(Decimal("20.0")),
                provider_reference="payment-synthetic-1",
            ),
        ),
        change_amount=Money(Decimal("1.0")),
    )

    assert to_canonical_json(first) == to_canonical_json(second)
    assert canonical_sha256(first) == canonical_sha256(second)
    assert len(canonical_sha256(first)) == 64


def test_canonical_payload_preserves_frozen_fiscal_evidence() -> None:
    payload = to_canonical_payload(_document())

    assert payload["document_kind"] == "nfce"
    assert payload["issuer"]["cnpj"] == "12345678000195"
    assert payload["items"][0]["product"]["ncm"] == "21069090"
    assert payload["items"][0]["tax_decision"]["rule_id"] == "rule-synthetic-1"
    assert payload["items"][0]["tax_decision"]["rule_version"] == 3
    assert payload["items"][0]["restaurant_decision"]["rate_reduction_percent"] == "40"
    assert payload["totals"]["net_amount"]["amount"] == "19"


def test_document_and_lines_are_immutable() -> None:
    document = _document()

    with pytest.raises(FrozenInstanceError):
        document.document_id = "changed"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        document.items[0].line_number = 2  # type: ignore[misc]


def test_line_requires_positive_finite_quantity() -> None:
    with pytest.raises(FiscalValidationError, match="greater than zero"):
        FiscalLineSnapshot(
            line_number=1,
            product=_product(),
            quantity=Decimal("0"),
            unit_price=Money(Decimal("10")),
            gross_amount=Money(Decimal("10")),
            tax_decision=_tax_decision(),
        )

    with pytest.raises(FiscalValidationError, match="finite Decimal"):
        FiscalLineSnapshot(
            line_number=1,
            product=_product(),
            quantity=Decimal("NaN"),
            unit_price=Money(Decimal("10")),
            gross_amount=Money(Decimal("10")),
            tax_decision=_tax_decision(),
        )


def test_line_rejects_discount_above_gross_plus_surcharge() -> None:
    with pytest.raises(FiscalValidationError, match="discount cannot exceed"):
        _line(gross="10", discount="12", surcharge="1")


def test_document_requires_items_and_unique_line_numbers() -> None:
    with pytest.raises(FiscalValidationError, match="at least one item"):
        _document(items=())

    scope = _scope()
    with pytest.raises(FiscalValidationError, match="line_number values must be unique"):
        _document(scope=scope, items=(_line(scope=scope), _line(scope=scope)))


def test_document_rejects_issuer_from_another_scope() -> None:
    scope = _scope()
    other_scope = _scope("tenant-other")

    with pytest.raises(FiscalValidationError, match="issuer and document"):
        _document(scope=scope, issuer=_issuer(other_scope))


def test_document_rejects_product_from_another_scope() -> None:
    scope = _scope()
    other_scope = _scope("tenant-other")

    with pytest.raises(FiscalValidationError, match="item product and document"):
        _document(scope=scope, items=(_line(scope=other_scope),))


def test_document_rejects_non_effective_issuer_and_product() -> None:
    scope = _scope()
    future_issuer = FiscalProfile(
        profile_id="future-issuer",
        scope=scope,
        cnpj=Cnpj("12.345.678/0001-95"),
        legal_name="Empresa Futura Sintetica",
        tax_regime=TaxRegimeCode.SIMPLES_NACIONAL,
        state_registration=StateRegistration("SP", "123456789"),
        primary_cnae=CnaeCode("5611-2/01"),
        address=FiscalAddress(
            street="Rua Sintetica",
            number="100",
            district="Centro",
            municipality_name="Sao Paulo",
            jurisdiction=BrazilianJurisdiction("SP", "3550308"),
            postal_code="01001000",
        ),
        effective_from=datetime(2027, 1, 1, tzinfo=UTC),
    )
    with pytest.raises(FiscalValidationError, match="issuer fiscal profile is not effective"):
        _document(scope=scope, issuer=future_issuer)

    future_product = FiscalProductProfile(
        profile_id="future-product",
        product_id="product-future",
        scope=scope,
        commercial_code="SKU-FUTURE",
        description="Produto futuro sintetico",
        ncm=NcmCode("21069090"),
        commercial_unit=FiscalUnitCode("UN"),
        taxable_unit=FiscalUnitCode("UN"),
        origin=ProductOrigin.NATIONAL,
        effective_from=datetime(2027, 1, 1, tzinfo=UTC),
    )
    line = FiscalLineSnapshot(
        line_number=1,
        product=future_product,
        quantity=Decimal("1"),
        unit_price=Money(Decimal("10")),
        gross_amount=Money(Decimal("10")),
        tax_decision=_tax_decision(),
    )
    with pytest.raises(FiscalValidationError, match="item product fiscal profile is not effective"):
        _document(scope=scope, items=(line,))


def test_payment_and_change_invariants_fail_closed() -> None:
    with pytest.raises(FiscalValidationError, match="greater than zero"):
        FiscalPaymentSnapshot(
            method=PaymentMethodKind.CASH,
            amount=Money(Decimal("0")),
        )

    with pytest.raises(FiscalValidationError, match="cannot exceed payment"):
        _document(change_amount=Money(Decimal("21")))


def test_payment_total_is_representational_not_reconciliation_gate() -> None:
    document = _document(
        payments=(
            FiscalPaymentSnapshot(
                method=PaymentMethodKind.OTHER,
                amount=Money(Decimal("5")),
            ),
        ),
        change_amount=Money.zero(),
    )

    assert document.totals.net_amount.amount == Decimal("19")
    assert document.totals.payment_amount.amount == Decimal("5")
