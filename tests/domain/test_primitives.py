from decimal import Decimal

import pytest

from kordena_fiscal.domain import (
    BrazilianJurisdiction,
    ElectronicInvoiceModel,
    ExecutionScope,
    FiscalDocumentKind,
    FiscalEnvironment,
    FiscalValidationError,
    Money,
    SourceReference,
)


def test_execution_scope_normalizes_ids_and_exposes_partition_key() -> None:
    scope = ExecutionScope(
        tenant_id=" tenant-a ",
        unit_id=" unit-1 ",
        environment=FiscalEnvironment.HOMOLOGATION,
        correlation_id=" corr-123 ",
    )

    assert scope.tenant_id == "tenant-a"
    assert scope.unit_id == "unit-1"
    assert scope.correlation_id == "corr-123"
    assert scope.partition_key == (
        "tenant-a",
        "unit-1",
        FiscalEnvironment.HOMOLOGATION,
    )


@pytest.mark.parametrize("field", ["tenant_id", "unit_id", "correlation_id"])
def test_execution_scope_rejects_blank_required_fields(field: str) -> None:
    values = {
        "tenant_id": "tenant-a",
        "unit_id": "unit-1",
        "environment": FiscalEnvironment.PRODUCTION,
        "correlation_id": "corr-123",
    }
    values[field] = "   "

    with pytest.raises(FiscalValidationError):
        ExecutionScope(**values)  # type: ignore[arg-type]


def test_brazilian_jurisdiction_normalizes_state_and_country() -> None:
    jurisdiction = BrazilianJurisdiction(
        state_code="sp",
        municipality_ibge_code="3550308",
        country_code="br",
    )

    assert jurisdiction.state_code == "SP"
    assert jurisdiction.country_code == "BR"
    assert jurisdiction.municipality_ibge_code == "3550308"


@pytest.mark.parametrize("state_code", ["XX", "S", "123"])
def test_brazilian_jurisdiction_rejects_invalid_state(state_code: str) -> None:
    with pytest.raises(FiscalValidationError):
        BrazilianJurisdiction(state_code=state_code)


@pytest.mark.parametrize("municipality", ["355030", "35503080", "ABC0308"])
def test_brazilian_jurisdiction_rejects_invalid_ibge_code(municipality: str) -> None:
    with pytest.raises(FiscalValidationError):
        BrazilianJurisdiction(state_code="SP", municipality_ibge_code=municipality)


def test_source_reference_is_host_neutral_and_stable() -> None:
    source = SourceReference(source_type=" Sale ", source_id="order-42")

    assert source.source_type == "sale"
    assert source.source_id == "order-42"
    assert source.canonical_tuple == ("sale", "order-42")


def test_money_requires_decimal_and_preserves_precision() -> None:
    value = Money(Decimal("10.1234"))

    assert value.amount == Decimal("10.1234")
    assert value.currency == "BRL"

    with pytest.raises(FiscalValidationError):
        Money(10.12)  # type: ignore[arg-type]


def test_money_rejects_non_finite_values() -> None:
    with pytest.raises(FiscalValidationError):
        Money(Decimal("NaN"))


def test_money_arithmetic_does_not_apply_hidden_rounding() -> None:
    total = Money(Decimal("10.1234")) + Money(Decimal("0.8766"))
    remaining = total - Money(Decimal("1.0000"))

    assert total.amount == Decimal("11.0000")
    assert remaining.amount == Decimal("10.0000")


def test_document_enums_keep_official_nfe_nfce_model_numbers_separate_from_kind() -> None:
    assert FiscalDocumentKind.NFE.value == "nfe"
    assert FiscalDocumentKind.NFCE.value == "nfce"
    assert FiscalDocumentKind.NFSE.value == "nfse"
    assert ElectronicInvoiceModel.NFE.value == 55
    assert ElectronicInvoiceModel.NFCE.value == 65
