"""Extrema WebISS SOAP tests; no real issuance, A1, endpoint or approval."""
from __future__ import annotations

from dataclasses import replace
from datetime import date
from unittest.mock import Mock

import pytest
from lxml import etree
from test_mg_homologation_authorization import CNPJ, _request
from test_mg_homologation_authorization import material as material
from test_nfse_abrasf203_envelope import _CANCEL, _payload

from kordena_fiscal.control_plane.commercial import ConfiguredFiscalOperation
from kordena_fiscal.domain import (
    BrazilianJurisdiction,
    Cnpj,
    FiscalDocumentKind,
    FiscalEnvironment,
    TaxRegimeCode,
)
from kordena_fiscal.gateway.mg_webiss_soap import (
    EXTREMA_WEBISS_HOMOLOGATION_URL,
    EXTREMA_WEBISS_PROVIDER_ID,
    UBERABA_WEBISS_PROVIDER_ID,
    WebissExtremaHomologationTransport,
    WebissMgContractError,
    WebissUberabaHomologationTransport,
    parse_webiss_soap_response,
)
from kordena_fiscal.gateway.nfse_abrasf203_envelope import (
    Abrasf203Operation,
    prepare_abrasf203_soap,
)

SOAP = "http://schemas.xmlsoap.org/soap/envelope/"
WSDL = "http://nfse.abrasf.org.br"
EXTREMA = BrazilianJurisdiction("MG", "3125101")


def _envelope(operation: Abrasf203Operation):
    return prepare_abrasf203_soap(
        operation=operation,
        xml=_payload(operation),
        scope=_request().scope,
        issuer_cnpj=Cnpj(CNPJ),
        resolve_certificate=Mock(),
        preaudit=Mock(),
    ) if operation is Abrasf203Operation.QUERY_BATCH else None


def _response(operation: Abrasf203Operation, *, xml: str = "<retorno/>") -> bytes:
    root = etree.Element(f"{{{SOAP}}}Envelope", nsmap={"soap": SOAP})
    body = etree.SubElement(root, f"{{{SOAP}}}Body")
    wrapper = etree.SubElement(body, f"{{{WSDL}}}{operation.value[1]}Response")
    etree.SubElement(wrapper, "outputXML").text = xml
    return etree.tostring(root, encoding="utf-8")


def test_extrema_webiss_soap_endpoint_is_pinned_to_restricted_environment() -> None:
    assert EXTREMA_WEBISS_HOMOLOGATION_URL == (
        "https://homologacao.webiss.com.br/ws/nfse.asmx"
    )
    assert "extremamg.webiss.com.br" not in EXTREMA_WEBISS_HOMOLOGATION_URL


@pytest.mark.parametrize("operation", [Abrasf203Operation.QUERY_BATCH])
def test_exact_municipal_binding_precedes_vault_and_transport(
    operation: Abrasf203Operation, material,
) -> None:
    resolver, cert, exchange = Mock(), Mock(return_value=material), Mock()
    resolver.resolve_provider_id.return_value = "wrong-provider"
    gateway = WebissExtremaHomologationTransport(
        provider_resolver=resolver, resolve_certificate=cert, exchange=exchange,
    )
    envelope = _envelope(operation)
    scope = _request().scope
    args = dict(
        envelope=envelope, operation=operation, scope=scope,
        issuer_cnpj=Cnpj(CNPJ), issuer_tax_regime=TaxRegimeCode.NORMAL,
        competence_date=date(2026, 10, 31), jurisdiction=EXTREMA,
    )
    with pytest.raises(WebissMgContractError, match="binding"):
        gateway.exchange_prepared(**args)
    cert.assert_not_called()
    exchange.assert_not_called()
    assert resolver.resolve_provider_id.call_args.kwargs == {
        "scope": scope,
        "document_kind": FiscalDocumentKind.NFSE,
        "jurisdiction": EXTREMA,
        "operation": ConfiguredFiscalOperation.QUERY.value,
    }
    resolver.resolve_provider_id.return_value = EXTREMA_WEBISS_PROVIDER_ID
    exchange.return_value = _response(operation)
    assert gateway.exchange_prepared(**args) == b"<retorno/>"
    cert.assert_called_once_with(scope, CNPJ)
    exchange.assert_called_once()
    assert envelope.soap_action == exchange.call_args.args[1]
    assert exchange.call_args.args[0] == envelope.body


@pytest.mark.parametrize("regime", [
    TaxRegimeCode.MEI,
    TaxRegimeCode.SIMPLES_NACIONAL,
    TaxRegimeCode.SIMPLES_NACIONAL_EXCESS_SUBLIMIT,
])
def test_national_issuer_must_not_dispatch_into_webiss(
    regime: TaxRegimeCode,
) -> None:
    resolver, cert, exchange = Mock(), Mock(), Mock()
    gateway = WebissExtremaHomologationTransport(
        provider_resolver=resolver, resolve_certificate=cert, exchange=exchange,
    )
    with pytest.raises(WebissMgContractError, match="Emissor Nacional"):
        gateway.exchange_prepared(
            envelope=_envelope(Abrasf203Operation.QUERY_BATCH),
            operation=Abrasf203Operation.QUERY_BATCH,
            scope=_request().scope,
            issuer_cnpj=Cnpj(CNPJ), issuer_tax_regime=regime,
            competence_date=date(2026, 11, 11), jurisdiction=EXTREMA,
        )
    resolver.resolve_provider_id.assert_not_called()
    cert.assert_not_called()
    exchange.assert_not_called()


def test_wrong_state_or_environment_denied_before_vault() -> None:
    resolver, cert, exchange = Mock(), Mock(), Mock()
    gateway = WebissExtremaHomologationTransport(
        provider_resolver=resolver, resolve_certificate=cert, exchange=exchange,
    )
    args = dict(
        envelope=_envelope(Abrasf203Operation.QUERY_BATCH),
        operation=Abrasf203Operation.QUERY_BATCH,
        scope=_request().scope,
        issuer_cnpj=Cnpj(CNPJ), issuer_tax_regime=TaxRegimeCode.NORMAL,
        competence_date=date(2026, 10, 31), jurisdiction=EXTREMA,
    )
    with pytest.raises(WebissMgContractError, match="scoped MG municipality"):
        gateway.exchange_prepared(
            **{**args, "jurisdiction": BrazilianJurisdiction("MG", "3170107")}
        )
    with pytest.raises(WebissMgContractError, match="scoped MG municipality"):
        gateway.exchange_prepared(**{
            **args,
            "scope": replace(args["scope"], environment=FiscalEnvironment.PRODUCTION),
        })
    resolver.resolve_provider_id.assert_not_called()
    cert.assert_not_called()
    exchange.assert_not_called()


def test_wrong_soap_action_and_wrapper_denied_before_binding() -> None:
    resolver, cert, exchange = Mock(), Mock(), Mock()
    gateway = WebissExtremaHomologationTransport(
        provider_resolver=resolver, resolve_certificate=cert, exchange=exchange,
    )
    env = _envelope(Abrasf203Operation.QUERY_BATCH)
    with pytest.raises(WebissMgContractError, match="SOAPAction"):
        gateway.exchange_prepared(
            envelope=replace(env, soap_action='"http://evil.invalid/Consulta"'),
            operation=Abrasf203Operation.QUERY_BATCH,
            scope=_request().scope,
            issuer_cnpj=Cnpj(CNPJ), issuer_tax_regime=TaxRegimeCode.NORMAL,
            competence_date=date(2026, 10, 31), jurisdiction=EXTREMA,
        )
    resolver.resolve_provider_id.assert_not_called()
    cert.assert_not_called()


def test_soap_fault_or_cross_operation_never_appears_fiscally_authorized() -> None:
    query = Abrasf203Operation.QUERY_BATCH
    fault = (
        f'<soap:Envelope xmlns:soap="{SOAP}">'
        "<soap:Body><soap:Fault><faultcode>soap:Server</faultcode>"
        "</soap:Fault></soap:Body></soap:Envelope>"
    ).encode()
    with pytest.raises(WebissMgContractError, match="SOAP Fault"):
        parse_webiss_soap_response(fault, query)
    with pytest.raises(WebissMgContractError, match="does not match"):
        parse_webiss_soap_response(
            _response(Abrasf203Operation.GENERATE), query,
        )
    with pytest.raises(WebissMgContractError, match="outputXML"):
        parse_webiss_soap_response(_response(query, xml="not-xml"), query)
    with pytest.raises(WebissMgContractError, match="DTD"):
        parse_webiss_soap_response(
            _response(query, xml='<!DOCTYPE retorno [<!ENTITY x "untrusted">]><retorno/>'),
            query,
        )


def test_uberaba_webiss_uses_the_same_transport_with_a_distinct_provider(material) -> None:
    resolver = Mock()
    resolver.resolve_provider_id.return_value = UBERABA_WEBISS_PROVIDER_ID
    certificate = Mock(return_value=material)
    exchange = Mock(return_value=_response(Abrasf203Operation.QUERY_BATCH))
    gateway = WebissUberabaHomologationTransport(
        provider_resolver=resolver,
        resolve_certificate=certificate,
        exchange=exchange,
    )
    args = dict(
        envelope=_envelope(Abrasf203Operation.QUERY_BATCH),
        operation=Abrasf203Operation.QUERY_BATCH,
        scope=_request().scope, issuer_cnpj=Cnpj(CNPJ),
        issuer_tax_regime=TaxRegimeCode.NORMAL,
        competence_date=date(2026, 10, 31),
    )
    uberaba = BrazilianJurisdiction("MG", "3170107")
    assert gateway.exchange_prepared(**args, jurisdiction=uberaba) == b"<retorno/>"
    assert resolver.resolve_provider_id.call_args.kwargs["jurisdiction"] == uberaba
    assert exchange.call_count == 1
    with pytest.raises(WebissMgContractError, match="scoped MG municipality"):
        gateway.exchange_prepared(**args, jurisdiction=EXTREMA)
    assert exchange.call_count == 1
    resolver.resolve_provider_id.return_value = EXTREMA_WEBISS_PROVIDER_ID
    with pytest.raises(WebissMgContractError, match="binding"):
        gateway.exchange_prepared(**args, jurisdiction=uberaba)
    assert exchange.call_count == 1


def test_uberaba_legacy_webiss_is_blocked_after_federal_simples_cutover() -> None:
    resolver, certificate, exchange = Mock(), Mock(), Mock()
    gateway = WebissUberabaHomologationTransport(
        provider_resolver=resolver,
        resolve_certificate=certificate,
        exchange=exchange,
    )
    with pytest.raises(WebissMgContractError, match="Emissor Nacional"):
        gateway.exchange_prepared(
            envelope=_envelope(Abrasf203Operation.QUERY_BATCH),
            operation=Abrasf203Operation.QUERY_BATCH,
            scope=_request().scope,
            issuer_cnpj=Cnpj(CNPJ),
            issuer_tax_regime=TaxRegimeCode.SIMPLES_NACIONAL,
            competence_date=date(2026, 11, 1),
            jurisdiction=BrazilianJurisdiction("MG", "3170107"),
        )
    resolver.resolve_provider_id.assert_not_called()
    certificate.assert_not_called()
    exchange.assert_not_called()


@pytest.mark.parametrize(
    ("city_ibge", "cls", "provider_id"),
    [
        ("3125101", WebissExtremaHomologationTransport, EXTREMA_WEBISS_PROVIDER_ID),
        ("3170107", WebissUberabaHomologationTransport, UBERABA_WEBISS_PROVIDER_ID),
    ],
)
def test_municipal_cancellation_is_signed_and_scope_bound_before_send(
    city_ibge, cls, provider_id, material,
) -> None:
    from unittest.mock import Mock

    resolved = Mock(return_value=material)
    cancelled = prepare_abrasf203_soap(
        operation=Abrasf203Operation.CANCEL,
        xml=_CANCEL.replace("3125101", city_ibge).encode(),
        scope=_request().scope,
        issuer_cnpj=Cnpj(CNPJ),
        resolve_certificate=resolved,
        preaudit=Mock(),
        preaudit_cancel=Mock(),
    )
    resolver = Mock()
    resolver.resolve_provider_id.return_value = provider_id
    exchange = Mock(return_value=_response(Abrasf203Operation.CANCEL))
    adapter = cls(
        provider_resolver=resolver,
        resolve_certificate=Mock(return_value=material),
        exchange=exchange,
    )
    jurisdiction = BrazilianJurisdiction("MG", city_ibge)
    assert adapter.exchange_prepared(
        envelope=cancelled,
        operation=Abrasf203Operation.CANCEL,
        scope=_request().scope,
        issuer_cnpj=Cnpj(CNPJ),
        issuer_tax_regime=TaxRegimeCode.NORMAL,
        competence_date=date(2026, 10, 31),
        jurisdiction=jurisdiction,
    ) == b"<retorno/>"
    assert resolver.resolve_provider_id.call_args.kwargs["operation"] == (
        ConfiguredFiscalOperation.CANCEL.value
    )
    assert exchange.call_args.args[1] == '"http://nfse.abrasf.org.br/CancelarNfse"'
    fake_scope = BrazilianJurisdiction(
        "MG", "3170107" if city_ibge == "3125101" else "3125101"
    )
    with pytest.raises(WebissMgContractError, match="scoped MG municipality"):
        adapter.exchange_prepared(
            envelope=cancelled,
            operation=Abrasf203Operation.CANCEL,
            scope=_request().scope, issuer_cnpj=Cnpj(CNPJ),
            issuer_tax_regime=TaxRegimeCode.NORMAL,
            competence_date=date(2026, 10, 31),
            jurisdiction=fake_scope,
        )
    assert exchange.call_count == 1


def test_municipal_cancellation_cross_city_payload_is_not_accepted(material) -> None:
    cancelled = prepare_abrasf203_soap(
        operation=Abrasf203Operation.CANCEL,
        xml=_CANCEL.encode(), scope=_request().scope,
        issuer_cnpj=Cnpj(CNPJ),
        resolve_certificate=Mock(return_value=material),
        preaudit=Mock(), preaudit_cancel=Mock(),
    )
    resolver, exchange, certificate = Mock(), Mock(), Mock()
    adapter = WebissUberabaHomologationTransport(
        provider_resolver=resolver,
        resolve_certificate=certificate,
        exchange=exchange,
    )
    with pytest.raises(WebissMgContractError, match="bound issuer and city"):
        adapter.exchange_prepared(
            envelope=cancelled, operation=Abrasf203Operation.CANCEL,
            scope=_request().scope, issuer_cnpj=Cnpj(CNPJ),
            issuer_tax_regime=TaxRegimeCode.NORMAL,
            competence_date=date(2026, 10, 31),
            jurisdiction=BrazilianJurisdiction("MG", "3170107"),
        )
    resolver.resolve_provider_id.assert_not_called()
    certificate.assert_not_called()
    exchange.assert_not_called()
