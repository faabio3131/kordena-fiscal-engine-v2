"""Strict SOAP 1.1 wire contract for Extrema/MG WebISS 2.02 (RTC 2026).

This is a *municipal* transport boundary, not the national SEFIN emitter and
not an ABRASF 2.03 alias. The caller must supply XML already signed by the
canonical scoped A1 signing flow and an immutable, hash-pinned municipal XSD
validator. This module never marks a fiscal document authorized, sends to a
municipal endpoint, or chooses a taxpayer/provider binding.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from enum import Enum

from lxml import etree

from kordena_fiscal.domain import Cnpj, ExecutionScope, FiscalEnvironment, FiscalValidationError
from kordena_fiscal.xml.schema import XmlSchemaValidator

_EXTREMA = "3125101"
_ABRASF = "http://www.abrasf.org.br/nfse.xsd"
_SERVICE = "http://nfse.abrasf.org.br"
_SOAP11 = "http://schemas.xmlsoap.org/soap/envelope/"
_XMLDSIG = "http://www.w3.org/2000/09/xmldsig#"
_MAX_XML_BYTES = 512 * 1024
_MAX_SOAP_BYTES = 2 * 1024 * 1024

# Public service metadata only. This is a production address, NOT an
# authorization to transmit and NOT a homologation URL.
EXTREMA_WEBISS_PUBLIC_SERVICE = "https://extremamg.webiss.com.br/ws/nfse.asmx"
EXTREMA_MUNICIPALITY_IBGE = _EXTREMA


class ExtremaWebissOperation(Enum):
    """Method names verified against the municipal ASMX service listing.

    The request/response XML roots are ABRASF 2.02 wire-contract candidates;
    each remains subject to validation against Extrema's RTC 2026 XSD package.
    """

    GENERATE = ("GerarNfse", "GerarNfseEnvio", "GerarNfseResposta", True)
    SUBMIT_BATCH = (
        "RecepcionarLoteRps", "EnviarLoteRpsEnvio", "EnviarLoteRpsResposta", True,
    )
    SUBMIT_BATCH_SYNC = (
        "RecepcionarLoteRpsSincrono", "EnviarLoteRpsSincronoEnvio",
        "EnviarLoteRpsSincronoResposta", True,
    )
    CANCEL = ("CancelarNfse", "CancelarNfseEnvio", "CancelarNfseResposta", True)
    SUBSTITUTE = ("SubstituirNfse", "SubstituirNfseEnvio", "SubstituirNfseResposta", True)
    QUERY_BATCH = ("ConsultarLoteRps", "ConsultarLoteRpsEnvio", "ConsultarLoteRpsResposta", False)
    QUERY_RPS = ("ConsultarNfsePorRps", "ConsultarNfseRpsEnvio", "ConsultarNfseRpsResposta", False)
    QUERY_RANGE = (
        "ConsultarNfsePorFaixa", "ConsultarNfseFaixaEnvio", "ConsultarNfseFaixaResposta",
        False,
    )
    QUERY_PROVIDED = (
        "ConsultarNfseServicoPrestado", "ConsultarNfseServicoPrestadoEnvio",
        "ConsultarNfseServicoPrestadoResposta", False,
    )
    QUERY_RECEIVED = (
        "ConsultarNfseServicoTomado", "ConsultarNfseServicoTomadoEnvio",
        "ConsultarNfseServicoTomadoResposta", False,
    )

    @property
    def method(self) -> str:
        return self.value[0]

    @property
    def request_root(self) -> str:
        return self.value[1]

    @property
    def response_root(self) -> str:
        return self.value[2]

    @property
    def changes_fiscal_state(self) -> bool:
        return self.value[3]


@dataclass(frozen=True, slots=True)
class ExtremaWebissSchema:
    """Trusted engineering-supplied XSD; NEVER selected by request/tenant input.

    The manifest digest must come from a verified, immutable municipal RTC XSD
    package. A generic ABRASF 2.03 validator is not interchangeable.
    """

    validator: XmlSchemaValidator
    approved_package_sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self.validator, XmlSchemaValidator):
            raise FiscalValidationError("Extrema requires a trusted municipal XSD validator")
        digest = self.approved_package_sha256
        if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
            raise FiscalValidationError("Invalid Extrema XSD package manifest digest")


@dataclass(frozen=True, slots=True)
class ExtremaWebissSoapRequest:
    operation: ExtremaWebissOperation
    body: bytes
    xml_sha256: str
    schema_package_sha256: str
    soap_action: str
    content_type: str = "text/xml; charset=utf-8"


@dataclass(frozen=True, slots=True)
class ExtremaWebissSoapResponse:
    operation: ExtremaWebissOperation
    xml: bytes
    xml_sha256: str
    schema_package_sha256: str


def _safe_root(xml: bytes, *, limit: int) -> etree._Element:
    if not isinstance(xml, bytes) or not 0 < len(xml) <= limit:
        raise FiscalValidationError("Invalid Extrema XML size")
    if b"<!DOCTYPE" in xml.upper() or b"<!ENTITY" in xml.upper():
        raise FiscalValidationError("DTD or entities forbidden in Extrema XML")
    try:
        return etree.fromstring(
            xml,
            parser=etree.XMLParser(
                resolve_entities=False, load_dtd=False, no_network=True,
                huge_tree=False, remove_comments=False,
            ),
        )
    except (etree.XMLSyntaxError, ValueError):
        raise FiscalValidationError("Invalid Extrema XML syntax") from None


def _validate_xsd(xml: bytes, schema: ExtremaWebissSchema) -> str:
    result = schema.validator.validate_document(xml)
    if result.schema_package_sha256 != schema.approved_package_sha256:
        raise FiscalValidationError("Extrema XSD manifest mismatch")
    return result.xml_sha256


def prepare_extrema_webiss_soap(
    *,
    operation: ExtremaWebissOperation,
    signed_or_query_xml: bytes,
    scope: ExecutionScope,
    issuer_cnpj: Cnpj,
    issuer_municipality_ibge: str,
    schema: ExtremaWebissSchema,
) -> ExtremaWebissSoapRequest:
    """Prepare a schema-verified SOAP envelope; never perform fiscal I/O.

    Mutations are permitted only after the canonical signer supplied its
    XMLDSig-bearing XML. Signature authenticity/preaudit is the responsibility
    of that upstream authority, NOT of this structural envelope function.
    """
    if not isinstance(operation, ExtremaWebissOperation):
        raise FiscalValidationError("Unknown Extrema WebISS SOAP operation")
    if (
        not isinstance(scope, ExecutionScope)
        or scope.environment is not FiscalEnvironment.HOMOLOGATION
    ):
        raise FiscalValidationError("Extrema contract restricted to homologation")
    if issuer_municipality_ibge != _EXTREMA or not isinstance(issuer_cnpj, Cnpj):
        raise FiscalValidationError("Extrema issuer municipality or identity mismatch")
    if not isinstance(schema, ExtremaWebissSchema):
        raise FiscalValidationError("Verified municipal Extrema schema is required")
    root = _safe_root(signed_or_query_xml, limit=_MAX_XML_BYTES)
    if root.tag != f"{{{_ABRASF}}}{operation.request_root}":
        raise FiscalValidationError("Incorrect Extrema WebISS XML root")
    # Identify the authorized party from XML, never from the HTTP request.
    party = "Tomador" if operation is ExtremaWebissOperation.QUERY_RECEIVED else "Prestador"
    cnpjs = root.xpath(
        ".//*[local-name()=$party]/*[local-name()='CpfCnpj']/*[local-name()='Cnpj']/text()",
        party=party,
    )
    if not cnpjs or any(value != issuer_cnpj.value for value in cnpjs):
        raise FiscalValidationError("Extrema XML issuer CNPJ mismatch")
    signatures = root.findall(f".//{{{_XMLDSIG}}}Signature")
    if operation.changes_fiscal_state and not signatures:
        raise FiscalValidationError("Extrema mutating XML must be signed by canonical A1")
    if not operation.changes_fiscal_state and signatures:
        raise FiscalValidationError("Extrema query XML must use unsigned query contract")
    xml_hash = _validate_xsd(signed_or_query_xml, schema)
    header = etree.Element(
        f"{{{_ABRASF}}}cabecalho", nsmap={None: _ABRASF}, versao="2.02",
    )
    etree.SubElement(header, f"{{{_ABRASF}}}versaoDados").text = "2.02"
    header_xml = etree.tostring(header, encoding="unicode")
    _validate_xsd(header_xml.encode("utf-8"), schema)
    envelope = etree.Element(f"{{{_SOAP11}}}Envelope", nsmap={"soap": _SOAP11})
    body = etree.SubElement(envelope, f"{{{_SOAP11}}}Body")
    request = etree.SubElement(
        body, f"{{{_SERVICE}}}{operation.method}Request", nsmap={"ws": _SERVICE},
    )
    etree.SubElement(request, "nfseCabecMsg").text = header_xml
    try:
        xml_text = signed_or_query_xml.decode("utf-8")
    except UnicodeDecodeError:
        raise FiscalValidationError("Extrema XML must be UTF-8") from None
    etree.SubElement(request, "nfseDadosMsg").text = xml_text
    return ExtremaWebissSoapRequest(
        operation=operation,
        body=etree.tostring(envelope, encoding="utf-8", xml_declaration=True),
        xml_sha256=xml_hash,
        schema_package_sha256=schema.approved_package_sha256,
        soap_action=f'"{_SERVICE}/{operation.method}"',
    )


def parse_extrema_webiss_soap(
    *, operation: ExtremaWebissOperation, soap_response: bytes,
    schema: ExtremaWebissSchema,
) -> ExtremaWebissSoapResponse:
    """Unwrap an exact SOAP 1.1 response; NO authorization state is inferred.

    The caller must subsequently correlate the returned identifiers, invoice,
    tenant, municipality and protocol with its persisted fiscal intention.
    """
    if (
        not isinstance(operation, ExtremaWebissOperation)
        or not isinstance(schema, ExtremaWebissSchema)
    ):
        raise FiscalValidationError("Invalid Extrema response contract")
    outer = _safe_root(soap_response, limit=_MAX_SOAP_BYTES)
    if outer.tag != f"{{{_SOAP11}}}Envelope":
        raise FiscalValidationError("Unexpected Extrema SOAP envelope")
    bodies = outer.findall(f"{{{_SOAP11}}}Body")
    if len(bodies) != 1 or len(bodies[0]) != 1:
        raise FiscalValidationError("Unexpected Extrema SOAP body")
    response = bodies[0][0]
    if response.tag != f"{{{_SERVICE}}}{operation.method}Response":
        raise FiscalValidationError("Unexpected Extrema SOAP operation or fault")
    if len(response) != 1 or response[0].tag != "outputXML" or response[0].text is None:
        raise FiscalValidationError("Missing or ambiguous Extrema outputXML")
    xml = response[0].text.encode("utf-8")
    inner = _safe_root(xml, limit=_MAX_XML_BYTES)
    if inner.tag != f"{{{_ABRASF}}}{operation.response_root}":
        raise FiscalValidationError("Unexpected Extrema municipal XML response root")
    digest = _validate_xsd(xml, schema)
    return ExtremaWebissSoapResponse(
        operation=operation, xml=xml,
        xml_sha256=digest, schema_package_sha256=schema.approved_package_sha256,
    )
