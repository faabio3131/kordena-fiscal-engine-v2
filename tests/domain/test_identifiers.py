import pytest

from kordena_fiscal.domain import CnaeCode, Cnpj, FiscalValidationError


def test_cnpj_accepts_numeric_format_and_normalizes_mask() -> None:
    cnpj = Cnpj("12.345.678/0001-95")

    assert cnpj.value == "12345678000195"
    assert cnpj.formatted == "12.345.678/0001-95"


def test_cnpj_accepts_alphanumeric_first_twelve_positions() -> None:
    cnpj = Cnpj("AB.C12.345/0001-10")

    assert cnpj.value == "ABC12345000110"
    assert cnpj.formatted == "AB.C12.345/0001-10"


def test_cnpj_rejects_invalid_check_digits() -> None:
    with pytest.raises(FiscalValidationError, match="check digits"):
        Cnpj("12.345.678/0001-94")


def test_cnpj_rejects_letter_in_check_digit_positions() -> None:
    with pytest.raises(FiscalValidationError):
        Cnpj("ABC1234500011A")


def test_cnpj_rejects_all_zero_value() -> None:
    with pytest.raises(FiscalValidationError, match="all-zero"):
        Cnpj("00.000.000/0000-00")


def test_cnae_normalizes_common_presentation_format() -> None:
    cnae = CnaeCode("5611-2/01")

    assert cnae.value == "5611201"
    assert cnae.formatted == "5611-2/01"


def test_cnae_rejects_wrong_length() -> None:
    with pytest.raises(FiscalValidationError):
        CnaeCode("561120")
