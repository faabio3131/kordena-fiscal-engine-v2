"""Offline Barueri PMB004 contract checks: no public WebService used."""
from __future__ import annotations

from datetime import date
from unittest.mock import Mock

import pytest

from kordena_fiscal.domain import (
    Cnpj,
    ExecutionScope,
    FiscalEnvironment,
    TaxRegimeCode,
)
from kordena_fiscal.gateway.barueri_pmb004_homologation import (
    BARUERI_PMB004_PROVIDER,
    BarueriContractError,
    BarueriPmb004HomologationTransport,
    BarueriRpsBatch,
    _build_soap,
    _parse_reply,
)


def _batch(
    regime: TaxRegimeCode = TaxRegimeCode.NORMAL,
    competence: date = date(2026, 11, 13),
    data: bytes | None = None,
) -> BarueriRpsBatch:
    return BarueriRpsBatch(
        scope=ExecutionScope(
            host_namespace="nfcore", tenant_id="tenant-a", unit_id="unit-b",
            environment=FiscalEnvironment.HOMOLOGATION, correlation_id="pmb004",
        ),
        issuer_cnpj=Cnpj("11222333000181"),
        municipal_registration="1234567",
        tax_regime=regime,
        competence_date=competence,
        remittance="20261113001",
        file_name="20261113001.txt",
        rps_bytes=data or b"11234567PMB00420261113001\r\n2RPS  1234\r\n",
    )


def _receipt(method: str) -> bytes:
    return (
        '<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/" '
        'xmlns:b="http://www.barueri.sp.gov.br/nfe"><soap:Body>'
        f'<b:{method}Response><b:{method}Result>'
        '<b:ListaMensagemRetorno><b:Codigo>OK200</b:Codigo></b:ListaMensagemRetorno>'
        '<b:ProtocoloRemessa>1234567</b:ProtocoloRemessa>'
        '<b:ListaNfeArquivosRPS><b:SituacaoArq>-1</b:SituacaoArq>'
        '</b:ListaNfeArquivosRPS>'
        f'</b:{method}Result></b:{method}Response></soap:Body></soap:Envelope>'
    ).encode()


@pytest.mark.parametrize("method", [
    "NFeLoteEnviarArquivo", "NFeLoteStatusArquivo", "NFeLoteBaixarArquivo",
    "NFeLoteListarArquivos",
])
def test_pinned_soap_action_and_method(method: str) -> None:
    xml, action = _build_soap(method, (("InscricaoMunicipal", "1234567"),))
    assert method.encode() in xml
    assert action == f'"http://www.barueri.sp.gov.br/nfe/{method}"'
    assert b"<MensagemXML>" in xml


def test_async_receipt_is_never_authorization() -> None:
    received = _parse_reply(_receipt("NFeLoteEnviarArquivo"), "NFeLoteEnviarArquivo")
    assert received.code == "OK200"
    assert received.document_authorized is False
    assert received.remittance_protocol == "1234567"


@pytest.mark.parametrize("regime,competence", [
    (TaxRegimeCode.SIMPLES_NACIONAL, date(2026, 11, 13)),
    (TaxRegimeCode.SIMPLES_NACIONAL_EXCESS_SUBLIMIT, date(2026, 11, 1)),
    (TaxRegimeCode.MEI, date(2023, 9, 1)),
])
def test_national_taxpayer_cannot_submit_municipal_batch(
    regime: TaxRegimeCode, competence: date,
) -> None:
    with pytest.raises(BarueriContractError, match="National NFS-e"):
        _batch(regime, competence)


def test_batch_rejects_layout_and_remittance_tampering() -> None:
    with pytest.raises(BarueriContractError, match="header/remittance"):
        _batch(data=b"11234567PMB00320261113001\r\n2RPS  1234\r\n")
    with pytest.raises(BarueriContractError, match="header/remittance"):
        _batch(data=b"11234567PMB00420261113002\r\n2RPS  1234\r\n")


def test_provider_mismatch_prevents_a1_and_http() -> None:
    resolver, certificate, exchange = Mock(), Mock(), Mock()
    resolver.resolve_provider_id.return_value = "unapproved-provider"
    gateway = BarueriPmb004HomologationTransport(
        provider_resolver=resolver,
        resolve_certificate=certificate,
        validate_pmb004=Mock(),
        exchange=exchange,
    )
    with pytest.raises(BarueriContractError, match="binding mismatched"):
        gateway.submit(_batch())
    certificate.assert_not_called()
    exchange.assert_not_called()


def test_unvalidated_rps_cannot_reach_a1() -> None:
    resolver, certificate, exchange = Mock(), Mock(), Mock()
    validator = Mock(side_effect=BarueriContractError("XSD/layout not verified"))
    gateway = BarueriPmb004HomologationTransport(
        provider_resolver=resolver,
        resolve_certificate=certificate,
        validate_pmb004=validator,
        exchange=exchange,
    )
    with pytest.raises(BarueriContractError, match="layout not verified"):
        gateway.submit(_batch())
    certificate.assert_not_called()
    exchange.assert_not_called()


def test_signed_remittance_dispatch_stays_pending(monkeypatch: pytest.MonkeyPatch) -> None:
    from kordena_fiscal.gateway import barueri_pmb004_homologation as mod

    monkeypatch.setattr(mod, "validate_a1_for_issuer", lambda *a, **kw: None)
    monkeypatch.setattr(mod, "build_fiscal_tls_context", lambda cert: Mock())
    resolver, cert, exchange = Mock(), Mock(return_value=Mock()), Mock(
        return_value=_receipt("NFeLoteEnviarArquivo")
    )
    resolver.resolve_provider_id.return_value = BARUERI_PMB004_PROVIDER
    validator = Mock()
    adapter = BarueriPmb004HomologationTransport(
        provider_resolver=resolver, resolve_certificate=cert,
        validate_pmb004=validator, exchange=exchange,
    )
    batch = _batch()
    result = adapter.submit(batch)
    assert result.code == "OK200"
    assert result.document_authorized is False
    validator.assert_called_once_with(batch.rps_bytes)
    assert exchange.call_count == 1
    assert resolver.resolve_provider_id.call_args.kwargs["operation"] == "authorize"
    result2 = adapter.status(batch=batch, protocol="1234567")
    assert result2.document_authorized is False
    assert resolver.resolve_provider_id.call_args.kwargs["operation"] == "query"
