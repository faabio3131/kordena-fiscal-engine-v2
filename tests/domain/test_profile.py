from datetime import UTC, datetime

import pytest

from kordena_fiscal.domain import (
    BrazilianJurisdiction,
    CnaeCode,
    Cnpj,
    ExecutionScope,
    FiscalAddress,
    FiscalEnvironment,
    FiscalProfile,
    FiscalValidationError,
    MunicipalRegistration,
    StateRegistration,
    TaxRegimeCode,
)


def _scope() -> ExecutionScope:
    return ExecutionScope(
        tenant_id="tenant-test",
        unit_id="unit-test",
        environment=FiscalEnvironment.HOMOLOGATION,
        correlation_id="corr-profile-1",
    )


def _address(state_code: str = "SP") -> FiscalAddress:
    municipality_code = "3550308" if state_code == "SP" else "3304557"
    municipality_name = "Sao Paulo" if state_code == "SP" else "Rio de Janeiro"
    return FiscalAddress(
        street="Rua de Teste",
        number="100",
        district="Centro",
        municipality_name=municipality_name,
        jurisdiction=BrazilianJurisdiction(state_code, municipality_code),
        postal_code="01001-000",
        complement="Sala 1",
    )


def _profile(**overrides: object) -> FiscalProfile:
    values: dict[str, object] = {
        "profile_id": "profile-test-1",
        "scope": _scope(),
        "cnpj": Cnpj("12.345.678/0001-95"),
        "legal_name": "Empresa Fiscal de Teste Ltda",
        "trade_name": "Empresa Teste",
        "tax_regime": TaxRegimeCode.SIMPLES_NACIONAL,
        "state_registration": StateRegistration("SP", "123.456.789"),
        "municipal_registration": MunicipalRegistration("987.654.321"),
        "primary_cnae": CnaeCode("5611-2/01"),
        "address": _address(),
        "effective_from": datetime(2026, 1, 1, tzinfo=UTC),
        "version": 1,
    }
    values.update(overrides)
    return FiscalProfile(**values)  # type: ignore[arg-type]


def test_fiscal_profile_is_immutable_versioned_snapshot() -> None:
    profile = _profile()

    assert profile.snapshot_key == ("profile-test-1", 1)
    assert profile.cnpj.value == "12345678000195"
    assert profile.address.postal_code == "01001000"
    assert profile.state_registration.number == "123456789"
    assert profile.municipal_registration == MunicipalRegistration("987654321")


def test_profile_effective_interval_is_half_open() -> None:
    profile = _profile(effective_to=datetime(2027, 1, 1, tzinfo=UTC))

    assert not profile.is_effective_at(datetime(2025, 12, 31, 23, 59, tzinfo=UTC))
    assert profile.is_effective_at(datetime(2026, 1, 1, tzinfo=UTC))
    assert profile.is_effective_at(datetime(2026, 12, 31, 23, 59, tzinfo=UTC))
    assert not profile.is_effective_at(datetime(2027, 1, 1, tzinfo=UTC))


def test_profile_rejects_state_registration_address_mismatch() -> None:
    with pytest.raises(FiscalValidationError, match="same state"):
        _profile(address=_address("RJ"))


def test_profile_rejects_invalid_effective_interval() -> None:
    with pytest.raises(FiscalValidationError, match="after effective_from"):
        _profile(effective_to=datetime(2025, 12, 31, tzinfo=UTC))


def test_state_registration_requires_number_when_not_exempt() -> None:
    with pytest.raises(FiscalValidationError, match="required"):
        StateRegistration("SP")


def test_state_registration_exemption_is_explicit() -> None:
    registration = StateRegistration("SP", exempt=True)

    assert registration.exempt is True
    assert registration.number is None

    with pytest.raises(FiscalValidationError, match="absent"):
        StateRegistration("SP", "123", exempt=True)


def test_fiscal_address_requires_municipality_ibge_code() -> None:
    with pytest.raises(FiscalValidationError, match="municipality_ibge_code"):
        FiscalAddress(
            street="Rua de Teste",
            number="100",
            district="Centro",
            municipality_name="Sao Paulo",
            jurisdiction=BrazilianJurisdiction("SP"),
            postal_code="01001000",
        )


def test_tax_regime_code_includes_mei_crt_4() -> None:
    assert TaxRegimeCode.MEI.value == 4
