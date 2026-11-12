"""BH National NFS-e recovery never retransmits fiscal DPS."""
from __future__ import annotations

import base64
import gzip
import json
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import Mock

import pytest

from kordena_fiscal.domain import (
    BrazilianJurisdiction, CnaeCode, Cnpj, ExecutionScope, FiscalAddress,
    FiscalEnvironment, FiscalProfile, Money, SourceReference,
    StateRegistration, TaxRegimeCode,
)
from kordena_fiscal.gateway import AuthorizationStatus
from kordena_fiscal.gateway import nfse_nacional_homologation as national
from kordena_fiscal.issuance.nfe_nfse import (
    NfseAuthorizationRequest, NfseCanonicalDocument, NfseServiceLine,
)
from kordena_fiscal.numbering import (
    FiscalSequenceKey, FiscalSequencePolicy,
    InMemoryFiscalSequenceStore, InternalFiscalSequenceStream,
)

_NOW = datetime(2026, 11, 12, 12, 0, tzinfo=UTC)
_NS = "http://www.sped.fazenda.gov.br/nfse"
_ACCESS_KEY = "31" + "0" * 48


def _request() -> NfseAuthorizationRequest:
    scope = ExecutionScope(
        "bh-tenant", "bh-unit", FiscalEnvironment.HOMOLOGATION, "corr-bh", "host-bh",
    )
    bh = BrazilianJurisdiction("MG", "3106200")
    issuer = FiscalProfile(
        profile_id="bh-synthetic-issuer", scope=scope, cnpj=Cnpj("12345678000195"),
        legal_name="Synthetic BH Fiscal Issuer",
        tax_regime=TaxRegimeCode.SIMPLES_NACIONAL,
        state_registration=StateRegistration("MG", "123456789"),
        primary_cnae=CnaeCode("6201501"),
        address=FiscalAddress(
            street="Rua Sintetica", number="10", district="Centro",
            municipality_name="Belo Horizonte", jurisdiction=bh,
            postal_code="30100000",
        ),
        effective_from=datetime(2026, 1, 1, tzinfo=UTC),
    )
    document = NfseCanonicalDocument(
        document_id="bh-nfse-1", scope=scope,
        source=SourceReference("service-order", "bh-1"),
        issued_at=_NOW, competence_date=_NOW.date(),
        issuer=issuer, service_jurisdiction=bh,
        services=(NfseServiceLine(
            line_number=1, municipal_service_code="0107",
            national_taxation_code="010701",
            municipal_taxation_detail="001", national_service_nbs="123456789",
            description="Synthetic reviewed service",
            gross_amount=Money(Decimal("100.00")),
            iss_amount=Money(Decimal("3.00")),
        ),),
    )
    return NfseAuthorizationRequest.build(document)


def _reservation(request: NfseAuthorizationRequest):
    scope = request.document.scope
    return InMemoryFiscalSequenceStore().reserve_next(
        FiscalSequenceKey.from_scope(
            scope, model=InternalFiscalSequenceStream.NFSE_DPS, series=1,
        ), FiscalSequencePolicy(),
    )


def _receipt() -> bytes:
    xml = f'<NFSe xmlns="{_NS}"><infNFSe Id="NFS{_ACCESS_KEY}"/></NFSe>'.encode()
    return json.dumps({
        "chaveAcesso": _ACCESS_KEY,
        "nfseXmlGZipB64": base64.b64encode(gzip.compress(xml)).decode(),
    }).encode()


def _gateway(monkeypatch, response):
    certificate = Mock(pkcs12_bytes=b"synthetic", password=b"synthetic")
    vault = Mock(return_value=certificate)
    monkeypatch.setattr(national, "validate_a1_for_issuer", lambda *a, **k: None)
    monkeypatch.setattr(national, "build_fiscal_tls_context", lambda *a, **k: Mock())
    calls = []

    def reader(url, tls, timeout):
        calls.append(url)
        return response(url)

    send = Mock(side_effect=AssertionError("recovery must never POST"))
    gateway = national.NfseNacionalHomologationGateway(
        resolve_certificate=vault,
        build_signed_dps=Mock(side_effect=AssertionError("recovery must never re-sign")),
        exchange=send, exchange_read=reader,
    )
    return gateway, calls, vault, send


def test_bh_readonly_recovery_correlates_dps_and_signed_invoice(monkeypatch) -> None:
    request = _request()
    reserved = _reservation(request)
    ident = "DPS31062001" + request.document.issuer.cnpj.value + "00001" + "000000000000001"
    def response(url):
        if "/dps/" in url:
            assert url.endswith(ident)
            return json.dumps({
                "tipoAmbiente": 2, "idDps": ident, "chaveAcesso": _ACCESS_KEY,
            }).encode()
        assert url.endswith("/nfse/" + _ACCESS_KEY)
        return _receipt()

    gateway, urls, vault, send = _gateway(monkeypatch, response)
    result = gateway.query(request, dps_reservation=reserved)
    assert result.status is AuthorizationStatus.AUTHORIZED
    assert result.invoice_reference == _ACCESS_KEY
    assert result.authorized_xml is not None
    assert len(urls) == 2
    assert vault.call_count == 1
    send.assert_not_called()


def test_bh_missing_dps_remains_pending_without_resend(monkeypatch) -> None:
    request = _request()
    gateway, urls, _, send = _gateway(monkeypatch, lambda url: None)
    result = gateway.query(request, dps_reservation=_reservation(request))
    assert result.status is AuthorizationStatus.PENDING
    assert len(urls) == 1
    send.assert_not_called()


def test_bh_recovery_rejects_mismatched_official_dps_id(monkeypatch) -> None:
    request = _request()
    gateway, _, _, send = _gateway(monkeypatch, lambda url: json.dumps({
        "tipoAmbiente": 2, "idDps": "DPSOTHER", "chaveAcesso": _ACCESS_KEY,
    }).encode())
    with pytest.raises(national.OfficialNfseTransportError, match="divergente"):
        gateway.query(request, dps_reservation=_reservation(request))
    send.assert_not_called()


def test_bh_recovery_rejects_other_tenant_before_opening_vault(monkeypatch) -> None:
    request = _request()
    wrong = replace(request.document.scope, tenant_id="wrong-tenant")
    foreign = InMemoryFiscalSequenceStore().reserve_next(
        FiscalSequenceKey.from_scope(
            wrong, model=InternalFiscalSequenceStream.NFSE_DPS, series=1,
        ), FiscalSequencePolicy(),
    )
    gateway, urls, vault, send = _gateway(monkeypatch, lambda url: _receipt())
    with pytest.raises(national.OfficialNfseTransportError, match="outro escopo"):
        gateway.query(request, dps_reservation=foreign)
    vault.assert_not_called()
    send.assert_not_called()
    assert not urls
