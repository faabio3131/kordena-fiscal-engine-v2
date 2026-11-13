"""Cajamar immutable original RPS archive: isolated offline contract tests."""
from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal

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
    Money,
    SourceReference,
    StateRegistration,
    TaxRegimeCode,
)
from kordena_fiscal.issuance.nfe_nfse import (
    NfseAuthorizationRequest,
    NfseCanonicalDocument,
    NfseServiceLine,
)
from kordena_fiscal.issuance.sp4_original_rps_archive import (
    build_sp4_original_from_reservation,
    decode_sp4_original,
    encode_sp4_original,
    expected_sp4_batch,
)
from kordena_fiscal.numbering import (
    FiscalNumberReservation,
    FiscalSequenceKey,
    InternalFiscalSequenceStream,
)

_NOW = datetime(2026, 11, 12, 12, tzinfo=UTC)
_CNPJ = Cnpj("11222333000181")

def _request(ibge: str, identifier: str = "one", *, tenant: str = "tenant-cajamar",
             unit: str = "unit-a") -> NfseAuthorizationRequest:
    scope = ExecutionScope(
        tenant_id=tenant, unit_id=unit, host_namespace="nfcore",
        environment=FiscalEnvironment.HOMOLOGATION,
        correlation_id="sp4-" + identifier,
    )
    city = BrazilianJurisdiction("SP", ibge)
    issuer = FiscalProfile(
        profile_id="issuer-" + identifier, scope=scope,
        cnpj=_CNPJ, legal_name="Emissor sintetico de servicos",
        tax_regime=TaxRegimeCode.NORMAL,
        state_registration=StateRegistration("SP", "123456789"),
        primary_cnae=CnaeCode("6201501"),
        address=FiscalAddress(
            street="Rua Sintetica", number="100", district="Centro",
            municipality_name="Municipio SP4", jurisdiction=city,
            postal_code="01001000",
        ),
        effective_from=datetime(2026, 1, 1, tzinfo=UTC),
    )
    doc = NfseCanonicalDocument(
        document_id="sp4-document-" + identifier, scope=scope,
        source=SourceReference("service-order", "sp4-order-" + identifier),
        issued_at=_NOW, competence_date=date(2026, 11, 12),
        issuer=issuer, service_jurisdiction=city,
        services=(NfseServiceLine(
            line_number=1, municipal_service_code="0107",
            national_taxation_code="010701",
            description="Servico sintetico revisado",
            gross_amount=Money(Decimal("150.00")),
            iss_amount=Money(Decimal("3.00")),
            source_normative="urn:nfcore:synthetic:sp4-2026",
        ),),
    )
    return NfseAuthorizationRequest.build(doc)



def _reservation(request: NfseAuthorizationRequest, number: int = 42) -> FiscalNumberReservation:
    key = FiscalSequenceKey.from_scope(
        request.document.scope, model=InternalFiscalSequenceStream.NFSE_RPS,
        series=1,
    )
    token = hashlib.sha256(
        f"{key.canonical_material}|{number}".encode(),
    ).hexdigest()
    return FiscalNumberReservation(key=key, number=number, reservation_token=token)


def test_cajamar_rps_sequence_lot_archive_and_replay_are_stable() -> None:
    request = _request("3509205")
    first = _reservation(request)
    original = build_sp4_original_from_reservation(request, first, rps_series="NF")
    assert original.rps_number == "42"
    assert original.municipal_batch_id == expected_sp4_batch("3509205", 42)
    raw = encode_sp4_original(request, original, first)
    assert decode_sp4_original(raw, scope=request.document.scope, request=request) == original
    assert encode_sp4_original(request, original, first) == raw


@pytest.mark.parametrize("field,value", [
    ("issuer_ibge", "3534401"),
    ("rps_number", "43"),
    ("gross_amount", "151.00"),
    ("municipal_batch_id", "999"),
])
def test_cajamar_rps_tamper_never_returns_original(field: str, value: str) -> None:
    request = _request("3509205")
    reservation = _reservation(request)
    original = build_sp4_original_from_reservation(request, reservation, rps_series="NF")
    evidence = json.loads(encode_sp4_original(request, original, reservation))
    evidence[field] = value
    with pytest.raises(FiscalValidationError, match="altered|diverge"):
        decode_sp4_original(
            json.dumps(evidence).encode(), scope=request.document.scope, request=request,
        )


def test_cajamar_other_tenant_and_unit_cannot_reuse_original_archive() -> None:
    request = _request("3509205")
    reservation = _reservation(request)
    original = build_sp4_original_from_reservation(request, reservation, rps_series="NF")
    raw = encode_sp4_original(request, original, reservation)
    for scope in (
        replace(request.document.scope, tenant_id="another-tenant"),
        replace(request.document.scope, unit_id="another-unit"),
    ):
        with pytest.raises(FiscalValidationError):
            decode_sp4_original(raw, scope=scope, request=request)


def test_cajamar_numbering_limit_keeps_durable_RPS_in_bounds() -> None:
    assert expected_sp4_batch("3509205", 99_999_999) == "99999999"
    with pytest.raises(FiscalValidationError, match="exceeds"):
        expected_sp4_batch("3509205", 100_000_000)

def test_cajamar_same_tenant_and_unit_cannot_exchange_issuer_cnpj() -> None:
    """A different issuer CNPJ in the same unit cannot consume another original RPS."""
    request = _request("3509205")
    reservation = _reservation(request)
    original = build_sp4_original_from_reservation(request, reservation, rps_series="NF")
    raw = encode_sp4_original(request, original, reservation)

    other_issuer = replace(request.document.issuer, cnpj=Cnpj("22333444000181"))
    another_document = replace(request.document, issuer=other_issuer)
    another_request = NfseAuthorizationRequest.build(another_document)

    assert another_request.document.scope == request.document.scope
    assert another_request.document.issuer.cnpj != request.document.issuer.cnpj
    with pytest.raises(FiscalValidationError, match="altered|diverge"):
        decode_sp4_original(
            raw, scope=request.document.scope, request=another_request,
        )
