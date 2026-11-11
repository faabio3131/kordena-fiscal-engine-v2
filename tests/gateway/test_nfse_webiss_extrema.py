"""Synthetic wire tests only; NOT official Extrema/RTC XSD certification."""
import hashlib
from dataclasses import replace

import pytest
from lxml import etree
from test_mg_homologation_authorization import CNPJ, _request

from kordena_fiscal.domain import Cnpj, FiscalEnvironment, FiscalValidationError
from kordena_fiscal.gateway.nfse_webiss_extrema import (
    EXTREMA_MUNICIPALITY_IBGE,
    EXTREMA_WEBISS_PUBLIC_SERVICE,
    ExtremaWebissOperation,
    ExtremaWebissSchema,
    parse_extrema_webiss_soap,
    prepare_extrema_webiss_soap,
)
from kordena_fiscal.xml.schema import SchemaResource, SchemaSet, XmlSchemaValidator

_ABRASF = "http://www.abrasf.org.br/nfse.xsd"
_SERVICE = "http://nfse.abrasf.org.br"
_SOAP = "http://schemas.xmlsoap.org/soap/envelope/"
_DS = "http://www.w3.org/2000/09/xmldsig#"


@pytest.fixture(scope="module")
def synthetic_schema():
    """Deliberately permissive local XSD: checks dispatch roots, not provider semantics."""
    names = {"cabecalho"}
    for operation in ExtremaWebissOperation:
        names.add(operation.request_root)
        names.add(operation.response_root)
    definitions = "".join(
        f'<xs:element name="{name}"><xs:complexType><xs:sequence>'
        '<xs:any minOccurs="0" maxOccurs="unbounded" processContents="skip"/>'
        '</xs:sequence><xs:anyAttribute processContents="skip"/>'
        '</xs:complexType></xs:element>'
        for name in sorted(names)
    )
    xsd = (
        '<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"'
        f' targetNamespace="{_ABRASF}" elementFormDefault="qualified">'
        f'{definitions}</xs:schema>'
    ).encode()
    resource = SchemaResource.from_bytes("test-only.xsd", xsd)
    validator = XmlSchemaValidator(SchemaSet(
        version="SYNTHETIC TEST ONLY -- NOT EXTREMA 2026",
        root_schema="test-only.xsd",
        resources=(resource,),
        source_uri="urn:synthetic:no-external-fiscal-authorization",
    ))
    return ExtremaWebissSchema(validator, validator._schema_set.package_sha256)


def _xml(operation, *, issuer=CNPJ, signed=None):
    tag = operation.request_root
    signed = operation.changes_fiscal_state if signed is None else signed
    kind = "Tomador" if operation is ExtremaWebissOperation.QUERY_RECEIVED else "Prestador"
    signature = f'<ds:Signature xmlns:ds="{_DS}"/>' if signed else ""
    return (
        f'<a:{tag} xmlns:a="{_ABRASF}">'
        f'<a:{kind}><a:CpfCnpj><a:Cnpj>{issuer}</a:Cnpj></a:CpfCnpj></a:{kind}>'
        f'{signature}</a:{tag}>'
    ).encode()


def _request_for(operation, schema, **kwargs):
    params = dict(
        operation=operation, signed_or_query_xml=_xml(operation), scope=_request().scope,
        issuer_cnpj=Cnpj(CNPJ), issuer_municipality_ibge=EXTREMA_MUNICIPALITY_IBGE,
        schema=schema,
    )
    return prepare_extrema_webiss_soap(**(params | kwargs))


def _response_xml(operation):
    return f'<a:{operation.response_root} xmlns:a="{_ABRASF}"/>'.encode()


def _soap(operation, inner):
    outer = etree.Element(f"{{{_SOAP}}}Envelope", nsmap={"soap": _SOAP})
    body = etree.SubElement(outer, f"{{{_SOAP}}}Body")
    response = etree.SubElement(body, f"{{{_SERVICE}}}{operation.method}Response")
    etree.SubElement(response, "outputXML").text = inner.decode()
    return etree.tostring(outer)


@pytest.mark.parametrize("operation", list(ExtremaWebissOperation))
def test_all_ten_published_operations_have_strict_soap11_wire_format(synthetic_schema, operation):
    request = _request_for(operation, synthetic_schema)
    assert request.body.startswith(b"<?xml")
    assert EXTREMA_WEBISS_PUBLIC_SERVICE.endswith("/ws/nfse.asmx")
    assert request.soap_action == f'"{_SERVICE}/{operation.method}"'
    assert request.content_type == "text/xml; charset=utf-8"
    root = etree.fromstring(request.body)
    assert root.tag == f"{{{_SOAP}}}Envelope"
    wrapper = root[0][0]
    assert wrapper.tag == f"{{{_SERVICE}}}{operation.method}Request"
    assert set(child.tag for child in wrapper) == {"nfseCabecMsg", "nfseDadosMsg"}
    header = etree.fromstring(wrapper.findtext("nfseCabecMsg").encode())
    assert header.get("versao") == "2.02"
    assert header.findtext(f"{{{_ABRASF}}}versaoDados") == "2.02"
    payload = etree.fromstring(wrapper.findtext("nfseDadosMsg").encode())
    assert payload.tag == f"{{{_ABRASF}}}{operation.request_root}"
    assert request.xml_sha256 == hashlib.sha256(_xml(operation)).hexdigest()
    response = parse_extrema_webiss_soap(
        operation=operation, soap_response=_soap(operation, _response_xml(operation)),
        schema=synthetic_schema,
    )
    assert response.xml == _response_xml(operation)
    assert response.schema_package_sha256 == request.schema_package_sha256


@pytest.mark.parametrize(("overrides", "reason"), [
    ({"issuer_municipality_ibge": "3550308"}, "municipality"),
    ({"signed_or_query_xml": b'<!DOCTYPE doc><a:GerarNfseEnvio/>'}, "DTD"),
    ({"signed_or_query_xml": b'<x/>'}, "root"),
    ({"signed_or_query_xml": _xml(ExtremaWebissOperation.GENERATE, issuer="0" * 14)}, "CNPJ"),
    ({"signed_or_query_xml": _xml(ExtremaWebissOperation.GENERATE, signed=False)}, "signed"),
    ({"scope": replace(_request().scope, environment=FiscalEnvironment.PRODUCTION)}, "homologation"),
])
def test_mutation_fail_closed_before_soap_creation(synthetic_schema, overrides, reason):
    with pytest.raises(FiscalValidationError, match=reason):
        _request_for(ExtremaWebissOperation.GENERATE, synthetic_schema, **overrides)


def test_query_cannot_smuggle_signature_and_tomador_is_scoped(synthetic_schema):
    operation = ExtremaWebissOperation.QUERY_RECEIVED
    with pytest.raises(FiscalValidationError, match="unsigned query"):
        _request_for(operation, synthetic_schema, signed_or_query_xml=_xml(operation, signed=True))
    with pytest.raises(FiscalValidationError, match="CNPJ"):
        _request_for(
            operation, synthetic_schema, signed_or_query_xml=_xml(operation, issuer="0" * 14),
        )


def test_pinned_schema_digest_mismatch_blocks_both_directions(synthetic_schema):
    altered = ExtremaWebissSchema(synthetic_schema.validator, "0" * 64)
    operation = ExtremaWebissOperation.GENERATE
    with pytest.raises(FiscalValidationError, match="manifest mismatch"):
        _request_for(operation, altered)
    with pytest.raises(FiscalValidationError, match="manifest mismatch"):
        parse_extrema_webiss_soap(
            operation=operation, soap_response=_soap(operation, _response_xml(operation)),
            schema=altered,
        )


@pytest.mark.parametrize(("soap", "reason"), [
    (b"<x/>", "envelope"),
    (b"<!DOCTYPE x><x/>", "DTD"),
    (
        b'<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">'
        b'<soap:Body><soap:Fault/></soap:Body></soap:Envelope>',
        "operation or fault",
    ),
    (
        b'<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">'
        b'<soap:Body/></soap:Envelope>',
        "body",
    ),
])
def test_rejects_invalid_soap_or_fault(synthetic_schema, soap, reason):
    with pytest.raises(FiscalValidationError, match=reason):
        parse_extrema_webiss_soap(
            operation=ExtremaWebissOperation.GENERATE, soap_response=soap,
            schema=synthetic_schema,
        )


def test_response_root_must_match_operation(synthetic_schema):
    with pytest.raises(FiscalValidationError, match="response root"):
        parse_extrema_webiss_soap(
            operation=ExtremaWebissOperation.GENERATE,
            soap_response=_soap(
                ExtremaWebissOperation.GENERATE,
                _response_xml(ExtremaWebissOperation.CANCEL),
            ),
            schema=synthetic_schema,
        )


def test_response_must_not_have_remote_entities(synthetic_schema):
    xml = b'<!DOCTYPE x [<!ENTITY ext SYSTEM "file:///etc/passwd">]><x>&ext;</x>'
    with pytest.raises(FiscalValidationError, match="DTD"):
        parse_extrema_webiss_soap(
            operation=ExtremaWebissOperation.GENERATE,
            soap_response=_soap(ExtremaWebissOperation.GENERATE, xml),
            schema=synthetic_schema,
        )
