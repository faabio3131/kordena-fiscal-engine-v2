from datetime import UTC, datetime

import pytest

from kordena_fiscal.domain import Cnpj, ElectronicInvoiceModel, FiscalValidationError
from kordena_fiscal.xml import AccessKeyInput, NfeAccessKey, build_access_key


def test_numeric_mod11_vector_remains_backward_compatible() -> None:
    key = NfeAccessKey("35260912345678000195650010000000011123456784")

    assert key.value.endswith("4")
    assert key.model is ElectronicInvoiceModel.NFCE
    assert key.series == 1
    assert key.invoice_number == 1


def test_builder_supports_alphanumeric_cnpj_inside_44_character_key() -> None:
    key = build_access_key(
        AccessKeyInput(
            state_ibge_code="35",
            issued_at=datetime(2026, 9, 10, 22, 0, tzinfo=UTC),
            issuer_cnpj=Cnpj("AB.C12.345/0001-10"),
            model=ElectronicInvoiceModel.NFCE,
            series=3,
            invoice_number=12345,
            emission_type=1,
            numeric_code=87654321,
        )
    )

    assert key.value == "352609ABC12345000110650030000123451876543210"
    assert len(key.value) == 44
    assert key.value[6:20] == "ABC12345000110"
    assert key.issuer_identifier == "ABC12345000110"
    assert key.model is ElectronicInvoiceModel.NFCE
    assert key.series == 3
    assert key.invoice_number == 12345
    assert NfeAccessKey(key.value) == key


def test_tampering_body_character_breaks_check_digit() -> None:
    key = build_access_key(
        AccessKeyInput(
            state_ibge_code="35",
            issued_at=datetime(2026, 9, 1, tzinfo=UTC),
            issuer_cnpj=Cnpj("AB.C12.345/0001-10"),
            model=ElectronicInvoiceModel.NFCE,
            series=1,
            invoice_number=1,
            emission_type=1,
            numeric_code=12345678,
        )
    )
    tampered = f"{key.value[:6]}Z{key.value[7:]}"

    with pytest.raises(FiscalValidationError, match="check digit"):
        NfeAccessKey(tampered)


def test_access_key_rejects_letter_outside_cnpj_alpha_segment() -> None:
    key = build_access_key(
        AccessKeyInput(
            state_ibge_code="35",
            issued_at=datetime(2026, 9, 1, tzinfo=UTC),
            issuer_cnpj=Cnpj("AB.C12.345/0001-10"),
            model=ElectronicInvoiceModel.NFCE,
            series=1,
            invoice_number=1,
            emission_type=1,
            numeric_code=12345678,
        )
    )
    invalid = f"A{key.value[1:]}"

    with pytest.raises(FiscalValidationError, match="layout"):
        NfeAccessKey(invalid)


def test_builder_rejects_out_of_range_fields_and_naive_time() -> None:
    common = {
        "state_ibge_code": "35",
        "issued_at": datetime(2026, 9, 1, tzinfo=UTC),
        "issuer_cnpj": Cnpj("AB.C12.345/0001-10"),
        "model": ElectronicInvoiceModel.NFCE,
        "series": 1,
        "invoice_number": 1,
        "emission_type": 1,
        "numeric_code": 12345678,
    }

    with pytest.raises(FiscalValidationError, match="series"):
        AccessKeyInput(**{**common, "series": 1000})  # type: ignore[arg-type]
    with pytest.raises(FiscalValidationError, match="invoice_number"):
        AccessKeyInput(**{**common, "invoice_number": 0})  # type: ignore[arg-type]
    with pytest.raises(FiscalValidationError, match="emission_type"):
        AccessKeyInput(**{**common, "emission_type": 0})  # type: ignore[arg-type]
    with pytest.raises(FiscalValidationError, match="timezone-aware"):
        AccessKeyInput(  # type: ignore[arg-type]
            **{**common, "issued_at": datetime(2026, 9, 1)}
        )
