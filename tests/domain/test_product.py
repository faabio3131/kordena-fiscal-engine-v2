from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest

from kordena_fiscal.domain import (
    CestCode,
    ExecutionScope,
    FiscalEnvironment,
    FiscalProductProfile,
    FiscalUnitCode,
    FiscalValidationError,
    Gtin,
    NcmCode,
    ProductOrigin,
    TaxClassificationHints,
)


def _scope() -> ExecutionScope:
    return ExecutionScope(
        tenant_id="tenant-synthetic",
        unit_id="unit-synthetic",
        environment=FiscalEnvironment.HOMOLOGATION,
        correlation_id="corr-product-1",
    )


def _instant(day: int) -> datetime:
    return datetime(2026, 9, day, 12, 0, tzinfo=UTC)


def _profile(**overrides: object) -> FiscalProductProfile:
    values: dict[str, object] = {
        "profile_id": "profile-product-1",
        "product_id": "product-1",
        "scope": _scope(),
        "commercial_code": "SKU-001",
        "description": "Produto sintético de teste",
        "ncm": NcmCode("21069090"),
        "commercial_unit": FiscalUnitCode("UN"),
        "taxable_unit": FiscalUnitCode("UN"),
        "origin": ProductOrigin.NATIONAL,
        "effective_from": _instant(10),
        "gtin": Gtin("SEM GTIN"),
    }
    values.update(overrides)
    return FiscalProductProfile(**values)  # type: ignore[arg-type]


def test_ncm_requires_exactly_eight_digits() -> None:
    assert NcmCode("2106.90.90").value == "21069090"

    with pytest.raises(FiscalValidationError, match="8 digits"):
        NcmCode("2106909")

    with pytest.raises(FiscalValidationError, match="8 digits"):
        NcmCode("2106AB90")


def test_cest_normalizes_supported_punctuation_and_rejects_other_content() -> None:
    assert CestCode("12.345.67").value == "1234567"

    with pytest.raises(FiscalValidationError, match="7 digits"):
        CestCode("123456")

    with pytest.raises(FiscalValidationError, match="7 digits"):
        CestCode("ABC1234567")


def test_fiscal_unit_is_normalized_and_bounded() -> None:
    assert FiscalUnitCode(" kg ").value == "KG"

    with pytest.raises(FiscalValidationError, match="1 to 6"):
        FiscalUnitCode("UNIDADE")


def test_gtin_accepts_supported_lengths_and_sem_gtin() -> None:
    assert Gtin("12345670").value == "12345670"
    assert Gtin("123456789012").value == "123456789012"
    assert Gtin("1234567890128").value == "1234567890128"
    assert Gtin("12345678901231").value == "12345678901231"
    assert Gtin(" sem gtin ").is_absent is True


def test_gtin_rejects_invalid_length_and_check_digit() -> None:
    with pytest.raises(FiscalValidationError, match="8, 12, 13 or 14"):
        Gtin("123456")

    with pytest.raises(FiscalValidationError, match="check digit"):
        Gtin("12345671")


def test_classification_hints_are_normalized_but_not_tax_decisions() -> None:
    hints = TaxClassificationHints(
        fiscal_benefit_code=" sp123 ",
        ibs_cbs_classification_code="000001",
    )

    assert hints.fiscal_benefit_code == "SP123"
    assert hints.ibs_cbs_classification_code == "000001"

    with pytest.raises(FiscalValidationError, match="invalid format"):
        TaxClassificationHints(fiscal_benefit_code="benefício com espaço")


def test_product_profile_is_immutable_and_effective_dated() -> None:
    profile = _profile(
        effective_from=_instant(10),
        effective_to=_instant(20),
        version=2,
        cest=CestCode("1234567"),
    )

    assert profile.is_effective_at(_instant(9)) is False
    assert profile.is_effective_at(_instant(10)) is True
    assert profile.is_effective_at(_instant(19)) is True
    assert profile.is_effective_at(_instant(20)) is False

    with pytest.raises(FrozenInstanceError):
        profile.description = "alterado"  # type: ignore[misc]


def test_product_profile_rejects_invalid_window_and_naive_instants() -> None:
    with pytest.raises(FiscalValidationError, match="after effective_from"):
        _profile(effective_from=_instant(20), effective_to=_instant(10))

    with pytest.raises(FiscalValidationError, match="timezone-aware"):
        _profile(effective_from=datetime(2026, 9, 10, 12, 0))

    profile = _profile()
    with pytest.raises(FiscalValidationError, match="timezone-aware"):
        profile.is_effective_at(datetime(2026, 9, 11, 12, 0))


def test_product_profile_rejects_invalid_version_and_wrong_value_objects() -> None:
    with pytest.raises(FiscalValidationError, match="version"):
        _profile(version=0)

    with pytest.raises(FiscalValidationError, match="ncm must be"):
        _profile(ncm="21069090")

    with pytest.raises(FiscalValidationError, match="origin must be"):
        _profile(origin=0)
