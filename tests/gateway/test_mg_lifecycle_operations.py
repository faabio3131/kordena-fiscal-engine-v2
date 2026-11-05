"""MG operational lifecycle uses actual offline XSD and synthetic A1 only."""
from dataclasses import replace
from datetime import UTC, datetime
from unittest.mock import Mock

import pytest
from lxml import etree
from test_mg_homologation_authorization import _request
from test_mg_homologation_authorization import material as material

from kordena_fiscal.domain import ElectronicInvoiceModel, FiscalEnvironment
from kordena_fiscal.gateway.nfe_sp_homologation import HomologationAuthorizationTarget
from kordena_fiscal.gateway.nfe_sp_operations_homologation import (
    OfficialNfeOperationsError,
    SefazHomologationOperationsGateway,
    SefazSpHomologationOperationsGateway,
)
from kordena_fiscal.operations import (
    CancellationRequest,
    FiscalEventStatus,
    FiscalQueryRequest,
    FiscalQueryStatus,
    InutilizationRequest,
)
from kordena_fiscal.xml.official_operation_schema import ROOTS, OfficialOperationXmlValidator

NS = "http://www.portalfiscal.inf.br/nfe"


def _gateway(material, exchange, issuer=None):
    return SefazHomologationOperationsGateway(
        target=HomologationAuthorizationTarget.MG_NFE,
        resolve_certificate=Mock(return_value=material),
        resolve_issuer=issuer or Mock(return_value="11222333000181"),
        exchange=exchange,
    )


def _soap(xml):
    return (
        '<Envelope xmlns="http://www.w3.org/2003/05/soap-envelope"><Body>'
        + xml + '</Body></Envelope>'
    ).encode()


def _cancel():
    request = _request()
    return CancellationRequest.build(
        scope=request.scope, access_key=request.access_key,
        authorization_protocol="131260000000001",
        justification="Cancelamento sintetico para teste interno",
    )


def _inutilize(model=ElectronicInvoiceModel.NFE):
    return InutilizationRequest.build(
        scope=_request().scope, model=model, series=1, first_number=10, last_number=12,
        justification="Inutilizacao sintetica para teste interno",
    )


def test_all_lifecycle_schemas_compile_without_network():
    OfficialOperationXmlValidator(tuple(ROOTS))


@pytest.mark.parametrize("status,expected", [
    ("100", FiscalQueryStatus.AUTHORIZED), ("101", FiscalQueryStatus.CANCELLED),
    ("217", FiscalQueryStatus.NOT_FOUND), ("105", FiscalQueryStatus.PENDING),
])
def test_mg_query_schema_and_normalization(material, status, expected):
    original = _request()
    exchange = Mock(return_value=_soap(
        f'<retConsSitNFe xmlns="{NS}"><tpAmb>2</tpAmb><cUF>31</cUF>'
        f'<chNFe>{original.access_key.value}</chNFe><cStat>{status}</cStat>'
        '<nProt>131260000000001</nProt></retConsSitNFe>'
    ))
    result = _gateway(material, exchange).query(FiscalQueryRequest(
        original.scope, original.access_key,
    ))
    assert result.status is expected
    assert result.provider.provider_name == "sefaz-mg-homologacao-nfe4"
    assert exchange.call_count == 1
    assert exchange.call_args.args[0] == "NFeConsultaProtocolo4"


def test_mg_cancellation_is_signed_xsd_valid_and_correlated(material):
    original = _cancel()
    exchange = Mock(return_value=_soap(
        f'<retEnvEvento xmlns="{NS}"><retEvento><infEvento>'
        f'<tpAmb>2</tpAmb><cOrgao>31</cOrgao><chNFe>{original.access_key.value}</chNFe>'
        '<tpEvento>110111</tpEvento><nSeqEvento>1</nSeqEvento>'
        '<cStat>135</cStat><nProt>131260000000002</nProt>'
        '</infEvento></retEvento></retEnvEvento>'
    ))
    result = _gateway(material, exchange).cancel(original)
    assert result.status is FiscalEventStatus.ACCEPTED
    from mg_golden_fixture import verify_soap_signature
    verify_soap_signature(exchange.call_args.args[1], material)
    payload = etree.fromstring(exchange.call_args.args[1])
    signature = payload.find(".//{http://www.w3.org/2000/09/xmldsig#}Signature")
    assert signature is not None
    assert signature.find(
        ".//{http://www.w3.org/2000/09/xmldsig#}SignatureMethod"
    ).get("Algorithm").endswith("rsa-sha1")


def test_mg_inutilization_is_signed_xsd_valid_and_correlated(material):
    original = _inutilize()
    year = datetime.now(UTC).strftime("%y")
    exchange = Mock(return_value=_soap(
        f'<retInutNFe xmlns="{NS}"><infInut><tpAmb>2</tpAmb><cUF>31</cUF>'
        f'<ano>{year}</ano><CNPJ>11222333000181</CNPJ><mod>55</mod><serie>1</serie>'
        '<nNFIni>10</nNFIni><nNFFin>12</nNFFin><cStat>102</cStat>'
        '<nProt>131260000000003</nProt></infInut></retInutNFe>'
    ))
    result = _gateway(material, exchange).inutilize(original)
    assert result.status is FiscalEventStatus.ACCEPTED
    from mg_golden_fixture import verify_soap_signature
    verify_soap_signature(exchange.call_args.args[1], material)
    payload = exchange.call_args.args[1]
    assert etree.fromstring(payload).findtext(f".//{{{NS}}}cUF") == "31"
    assert b"ID31" in payload


@pytest.mark.parametrize("operation", ["query", "cancel"])
@pytest.mark.parametrize("uf,model", [
    ("35", ElectronicInvoiceModel.NFE), ("31", ElectronicInvoiceModel.NFCE),
])
def test_wrong_state_or_model_never_accesses_certificate(operation, uf, model):
    source = _request(uf, model)
    resolver, exchange = Mock(), Mock()
    gateway = SefazHomologationOperationsGateway(
        target=HomologationAuthorizationTarget.MG_NFE,
        resolve_certificate=resolver, exchange=exchange,
    )
    request = (
        FiscalQueryRequest(source.scope, source.access_key) if operation == "query"
        else replace(_cancel(), access_key=source.access_key)
    )
    with pytest.raises(OfficialNfeOperationsError, match="state/model"):
        getattr(gateway, operation)(request)
    resolver.assert_not_called()
    exchange.assert_not_called()


def test_model65_inutilization_never_resolves_issuer_or_vault():
    issuer, resolver, exchange = Mock(), Mock(), Mock()
    gateway = SefazHomologationOperationsGateway(
        target=HomologationAuthorizationTarget.MG_NFE,
        resolve_certificate=resolver, resolve_issuer=issuer, exchange=exchange,
    )
    with pytest.raises(OfficialNfeOperationsError, match="model 65"):
        gateway.inutilize(_inutilize(ElectronicInvoiceModel.NFCE))
    issuer.assert_not_called()
    resolver.assert_not_called()
    exchange.assert_not_called()


@pytest.mark.parametrize("operation", ["query", "cancel", "inutilize"])
def test_production_is_denied_before_vault(operation):
    resolver, issuer, exchange = Mock(), Mock(), Mock()
    gateway = SefazHomologationOperationsGateway(
        target=HomologationAuthorizationTarget.MG_NFE, resolve_certificate=resolver,
        resolve_issuer=issuer, exchange=exchange,
    )
    source = _request()
    request = {
        "query": FiscalQueryRequest(source.scope, source.access_key),
        "cancel": _cancel(), "inutilize": _inutilize(),
    }[operation]
    request = replace(
        request, scope=replace(source.scope, environment=FiscalEnvironment.PRODUCTION),
    )
    with pytest.raises(OfficialNfeOperationsError):
        getattr(gateway, operation)(request)
    resolver.assert_not_called()
    issuer.assert_not_called()
    exchange.assert_not_called()


def test_mismatched_query_reply_never_authorizes(material):
    exchange = Mock(return_value=_soap(
        f'<retConsSitNFe xmlns="{NS}"><tpAmb>2</tpAmb><cUF>31</cUF><cStat>100</cStat>'
        f'<chNFe>{"1" * 44}</chNFe><nProt>131260000000001</nProt></retConsSitNFe>'
    ))
    with pytest.raises(OfficialNfeOperationsError, match="key mismatch"):
        _gateway(material, exchange).query(FiscalQueryRequest(
            _request().scope, _request().access_key,
        ))


def test_sp_wrapper_remains_fixed_and_invalid_target_is_denied():
    sp = SefazSpHomologationOperationsGateway(resolve_certificate=Mock())
    assert sp._state == "35"
    with pytest.raises(ValueError):
        SefazHomologationOperationsGateway(resolve_certificate=Mock(), target="mg_nfe")


@pytest.mark.parametrize("operation,field", [
    ("cancel", "chNFe"), ("cancel", "tpEvento"), ("cancel", "nSeqEvento"),
    ("cancel", "cOrgao"), ("inutilize", "CNPJ"), ("inutilize", "nNFFin"),
    ("inutilize", "serie"), ("inutilize", "mod"), ("inutilize", "ano"),
])
def test_cross_document_or_range_reply_is_denied(material, operation, field):
    source = _cancel()
    year = datetime.now(UTC).strftime("%y")
    if operation == "cancel":
        fields = {
            "tpAmb": "2", "cOrgao": "31", "chNFe": source.access_key.value,
            "tpEvento": "110111", "nSeqEvento": "1", "cStat": "135",
            "nProt": "131260000000001",
        }
        fields[field] = "999"
        body = "".join(f"<{name}>{value}</{name}>" for name, value in fields.items())
        xml = f'<retEnvEvento xmlns="{NS}"><retEvento><infEvento>{body}'
        xml += '</infEvento></retEvento></retEnvEvento>'
        request = source
    else:
        fields = {
            "tpAmb": "2", "cUF": "31", "ano": year, "CNPJ": "11222333000181",
            "mod": "55", "serie": "1", "nNFIni": "10", "nNFFin": "12",
            "cStat": "102", "nProt": "131260000000001",
        }
        fields[field] = "999"
        body = "".join(f"<{name}>{value}</{name}>" for name, value in fields.items())
        xml = f'<retInutNFe xmlns="{NS}"><infInut>{body}</infInut></retInutNFe>'
        request = _inutilize()
    exchange = Mock(return_value=_soap(xml))
    with pytest.raises(OfficialNfeOperationsError, match="correlation mismatch"):
        getattr(_gateway(material, exchange), operation)(request)
    assert exchange.call_count == 1


@pytest.mark.parametrize("operation", ["query", "cancel", "inutilize"])
def test_soap_fault_never_becomes_success(material, operation):
    exchange = Mock(return_value=_soap("<Fault/>"))
    request = {
        "query": FiscalQueryRequest(_request().scope, _request().access_key),
        "cancel": _cancel(), "inutilize": _inutilize(),
    }[operation]
    with pytest.raises(OfficialNfeOperationsError, match="SOAP"):
        getattr(_gateway(material, exchange), operation)(request)
    assert exchange.call_count == 1


@pytest.mark.parametrize("service,endpoint,method", [
    ("NFeConsultaProtocolo4", "NFeConsultaProtocolo4", "nfeConsultaNF"),
    ("NFeRecepcaoEvento4", "NFeRecepcaoEvento4", "nfeRecepcaoEvento"),
    ("NFeInutilizacao4", "NFeInutilizacao4", "nfeInutilizacaoNF"),
])
def test_fixed_mg_destination_action_and_no_redirect_handler(
    monkeypatch, material, service, endpoint, method,
):
    import ssl

    import kordena_fiscal.gateway.nfe_sp_operations_homologation as module
    from kordena_fiscal.gateway.nfe_sp_homologation import _RejectFiscalRedirects
    response = Mock()
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    response.read.return_value = b"<reply/>"
    opener = Mock()
    opener.open.return_value = response
    build = Mock(return_value=opener)
    monkeypatch.setattr(module, "build_opener", build)
    gateway = _gateway(material, Mock())
    gateway._https_exchange(service, b"<synthetic/>", ssl.create_default_context(), 2)
    request = opener.open.call_args.args[0]
    assert request.full_url == "https://hnfe.fazenda.mg.gov.br/nfe2/services/" + endpoint
    assert method in request.headers["Content-type"]
    assert any(isinstance(handler, _RejectFiscalRedirects) for handler in build.call_args.args)


def test_schema_complete_nfe_authorization_roundtrip_to_official_nfe_proc(material):
    from mg_golden_fixture import unsigned_golden_request

    from kordena_fiscal.gateway.authorization import AuthorizationStatus
    from kordena_fiscal.gateway.nfe_sp_homologation import build_mg_nfe_homologation_gateway
    from kordena_fiscal.xml.official_operation_schema import load_operation_schema
    from kordena_fiscal.xml.schema import SchemaSet, XmlSchemaValidator
    original = unsigned_golden_request()
    def reply(payload, *_args):
        from mg_golden_fixture import verify_soap_signature
        verify_soap_signature(payload, material)
        digest = etree.fromstring(payload).findtext(
            ".//{http://www.w3.org/2000/09/xmldsig#}DigestValue"
        )
        return _soap(
            f'<retEnviNFe xmlns="{NS}" versao="4.00"><tpAmb>2</tpAmb>'
            '<verAplic>SYNTHETIC-TEST</verAplic><cStat>104</cStat>'
            '<xMotivo>Lote processado</xMotivo><cUF>31</cUF>'
            '<dhRecbto>2026-11-05T12:00:01-03:00</dhRecbto>'
            f'<protNFe versao="4.00"><infProt><tpAmb>2</tpAmb><verAplic>SYNTHETIC</verAplic>'
            f'<chNFe>{original.access_key.value}</chNFe>'
            '<dhRecbto>2026-11-05T12:00:01-03:00</dhRecbto>'
            f'<nProt>131260000000001</nProt><digVal>{digest}</digVal>'
            '<cStat>100</cStat><xMotivo>Autorizado uso NF-e</xMotivo>'
            '</infProt></protNFe></retEnviNFe>'
        )
    exchange = Mock(side_effect=reply)
    gateway = build_mg_nfe_homologation_gateway(
        resolve_certificate=Mock(return_value=material), exchange=exchange,
    )
    result = gateway.authorize(original)
    assert result.status is AuthorizationStatus.AUTHORIZED
    assert result.authorized_xml
    base = load_operation_schema("NFeAutorizacao4")
    proc = SchemaSet(
        version=base.version, root_schema="nfe/procNFe_v4.00.xsd",
        resources=base.resources, source_uri=base.source_uri,
    )
    XmlSchemaValidator(proc).validate_document(result.authorized_xml)
    assert exchange.call_count == 1
