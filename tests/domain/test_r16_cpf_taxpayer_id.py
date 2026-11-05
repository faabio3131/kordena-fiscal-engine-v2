"""Canonical CPF identity validation for NFS-e taker input."""
import pytest

from kordena_fiscal.domain import Cpf, FiscalValidationError


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("529.982.247-25", "52998224725"),
        ("111.444.777-35", "11144477735"),
    ],
)
def test_valid_cpf_normalizes(raw: str, expected: str) -> None:
    assert Cpf(raw).value == expected


@pytest.mark.parametrize(
    "invalid",
    ["00000000000", "11111111111", "52998224724", "12345678900", "abc"],
)
def test_cpf_rejects_bad_check_digits(invalid: str) -> None:
    with pytest.raises(FiscalValidationError):
        Cpf(invalid)
