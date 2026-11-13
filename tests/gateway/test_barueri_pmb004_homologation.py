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


def _synthetic_pmb004() -> bytes:
    """Physical record widths only: full fiscal values need official validator."""
    header = b"11234567PMB00420261113001"
    record2 = b"2RPS  " + b" " * (1970 - 6)
    record4 = b"41" + b" " * (531 - 2)
    trailer = b"9" + b"0000004" + b"0" * 30
    assert list(map(len, (header, record2, record4, trailer))) == [25, 1970, 531, 38]
    return b"\r\n".join((header, record2, record4, trailer)) + b"\r\n"


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
        rps_bytes=data if data is not None else _synthetic_pmb004(),
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
    from lxml import etree

    root = etree.fromstring(xml)
    fields = root.xpath("//*[local-name()='MensagemXML']")
    assert len(fields) == 1  # SOAP serializes default namespace with a prefix


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
        _batch(data=_synthetic_pmb004().replace(b"PMB004", b"PMB003", 1))
    with pytest.raises(BarueriContractError, match="header/remittance"):
        _batch(data=_synthetic_pmb004().replace(b"20261113001", b"20261113002", 1))


def test_pmb004_requires_complete_rps_rtc_and_footer() -> None:
    valid = _synthetic_pmb004()
    with pytest.raises(BarueriContractError, match="fixed-width"):
        _batch(data=valid.replace(b"2RPS  ", b"2RPS ", 1))
    with pytest.raises(BarueriContractError, match="missing required fiscal records"):
        _batch(data=valid.replace(b"41" + b" " * 529 + b"\r\n", b"", 1))
    with pytest.raises(BarueriContractError, match="trailer count"):
        _batch(data=valid.replace(b"90000004", b"90000003", 1))


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
        side_effect=[
            _receipt("NFeLoteEnviarArquivo"),
            _receipt("NFeLoteStatusArquivo"),
        ]
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
