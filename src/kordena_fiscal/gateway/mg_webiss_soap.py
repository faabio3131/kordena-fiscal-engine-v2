"""Scoped WebISS MG SOAP 1.1 homologation transport, no alternate fiscal authority.

The public Extrema WebISS WSDL advertises SOAP actions for GerarNfse,
RecepcionarLoteRps and ConsultarLoteRps. This transport reuses the existing
ABRASF 2.03 XML/XSD/XMLDSig preparer and the canonical DURABLE unit binding.
The provider's municipality-specific schema version is not certified here:
do not register this adapter as production-ready until WSDL/XSD parity,
credentials, municipal ISS rules and official responses are proved.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import ssl
from collections.abc import Callable
from datetime import UTC, date, datetime
from urllib.error import HTTPError, URLError
from urllib.request import HTTPSHandler, Request, build_opener

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from lxml import etree

from kordena_fiscal.control_plane.commercial import ConfiguredFiscalOperation
from kordena_fiscal.domain import (
    BrazilianJurisdiction,
    Cnpj,
    ExecutionScope,
    FiscalDocumentKind,
    FiscalEnvironment,
    FiscalValidationError,
    TaxRegimeCode,
)
from kordena_fiscal.gateway.fiscal_tls import (
    RejectFiscalRedirects,
    build_fiscal_tls_context,
)
from kordena_fiscal.gateway.nfse_abrasf203_envelope import (
    Abrasf203Envelope,
    Abrasf203Operation,
)
from kordena_fiscal.gateway.provider import ProviderSelectionResolver
from kordena_fiscal.gateway.webiss_2026_schema import (
    WEBISS_RTC_LAYOUT_VERSION,
    Webiss2026SchemaEvidence,
    WebissMunicipalSchemaUnverified,
    validate_webiss_official_xml,
)
from kordena_fiscal.vault import EphemeralCertificateMaterial
from kordena_fiscal.vault.a1_preflight import validate_a1_for_issuer
from kordena_fiscal.xml.schema import XmlSchemaValidator

EXTREMA_IBGE = "3125101"
UBERABA_IBGE = "3170107"
EXTREMA_WEBISS_PROVIDER_ID = "webiss-extrema-mg-homologation"
UBERABA_WEBISS_PROVIDER_ID = "webiss-uberaba-mg-homologation"
EXTREMA_WEBISS_HOMOLOGATION_URL = "https://homologacao.webiss.com.br/ws/nfse.asmx"
EXTREMA_WEBISS_PUBLIC_SERVICE = "https://extremamg.webiss.com.br/ws/nfse.asmx"
UBERABA_WEBISS_PUBLIC_SERVICE = "https://uberabamg.webiss.com.br/ws/nfse.asmx"
_MG_WEBISS_PROVIDERS = {
    EXTREMA_IBGE: EXTREMA_WEBISS_PROVIDER_ID,
    UBERABA_IBGE: UBERABA_WEBISS_PROVIDER_ID,
}
_SOAP = "http://schemas.xmlsoap.org/soap/envelope/"
_WSDL = "http://nfse.abrasf.org.br"
_RESPONSE_LIMIT = 2_097_152
_DS = "http://www.w3.org/2000/09/xmldsig#"
_RESPONSE_ROOTS = {
    Abrasf203Operation.GENERATE: "GerarNfseResposta",
    Abrasf203Operation.SUBMIT_BATCH: "EnviarLoteRpsResposta",
    Abrasf203Operation.QUERY_BATCH: "ConsultarLoteRpsResposta",
    Abrasf203Operation.CANCEL: "CancelarNfseResposta",
}
_EXPECTED_SIGNATURE_COUNTS = {
    Abrasf203Operation.GENERATE: 1,
    Abrasf203Operation.SUBMIT_BATCH: 2,
    Abrasf203Operation.QUERY_BATCH: 0,
    Abrasf203Operation.CANCEL: 1,
}
_ACTIONS = {
    Abrasf203Operation.GENERATE: ConfiguredFiscalOperation.AUTHORIZE,
    Abrasf203Operation.SUBMIT_BATCH: ConfiguredFiscalOperation.AUTHORIZE,
    Abrasf203Operation.QUERY_BATCH: ConfiguredFiscalOperation.QUERY,
    Abrasf203Operation.CANCEL: ConfiguredFiscalOperation.CANCEL,
}


class WebissMgContractError(FiscalValidationError):
    """Sanitized municipal mismatch, response error or ambiguous transport."""


def _validate_request_envelope(
    envelope: Abrasf203Envelope,
    operation: Abrasf203Operation,
    *,
    evidence: Webiss2026SchemaEvidence,
    municipal_validator: XmlSchemaValidator,
) -> None:
    if not isinstance(envelope, Abrasf203Envelope) or not isinstance(
        operation, Abrasf203Operation
    ):
        raise WebissMgContractError("WebISS requires the trusted ABRASF preparer")
    if (
        not isinstance(envelope.body, bytes)
        or not 0 < len(envelope.body) <= _RESPONSE_LIMIT
        or envelope.content_type != "text/xml; charset=utf-8"
    ):
        raise WebissMgContractError("Invalid prepared WebISS envelope")
    method = operation.value[1]
    if envelope.soap_action != f'"{_WSDL}/{method}"':
        raise WebissMgContractError("SOAPAction does not match prepared operation")
    if (
        envelope.schema_version != WEBISS_RTC_LAYOUT_VERSION
        or envelope.schema_package_sha256 != evidence.schema_package_sha256
    ):
        raise WebissMunicipalSchemaUnverified(
            "WebISS 2.02 RTC envelope has no certified municipal schema digest"
        )
    try:
        root = etree.fromstring(
            envelope.body,
            parser=etree.XMLParser(resolve_entities=False, no_network=True),
        )
    except etree.XMLSyntaxError:
        raise WebissMgContractError("Invalid prepared WebISS XML") from None
    if root.tag != f"{{{_SOAP}}}Envelope" or getattr(root.getroottree().docinfo, "doctype", None):
        raise WebissMgContractError("Unexpected WebISS SOAP envelope")
    children = list(root)
    if len(children) != 1 or children[0].tag != f"{{{_SOAP}}}Body":
        raise WebissMgContractError("Unexpected WebISS SOAP body")
    requests = list(children[0])
    if len(requests) != 1 or requests[0].tag != f"{{{_WSDL}}}{method}Request":
        raise WebissMgContractError("Unexpected WebISS SOAP method")
    values = list(requests[0])
    if (
        len(values) != 2
        or [v.tag for v in values] != ["nfseCabecMsg", "nfseDadosMsg"]
        or any(not v.text for v in values)
    ):
        raise WebissMgContractError("WebISS request is missing signed XML or header")
    for part in values:
        encoded = str(part.text).encode("utf-8")
        if len(encoded) > _RESPONSE_LIMIT:
            raise WebissMgContractError("WebISS inner XML exceeds limit")
        try:
            inner = etree.fromstring(
                encoded, parser=etree.XMLParser(resolve_entities=False, no_network=True),
            )
        except etree.XMLSyntaxError:
            raise WebissMgContractError("WebISS inner XML is malformed") from None
        if getattr(inner.getroottree().docinfo, "doctype", None):
            raise WebissMgContractError("WebISS inner XML DTD is prohibited")
        validate_webiss_official_xml(
            evidence=evidence, validator=municipal_validator, xml=encoded,
        )
        if part.tag == "nfseCabecMsg":
            if (
                inner.tag != "{http://www.abrasf.org.br/nfse.xsd}cabecalho"
                or inner.get("versao") != WEBISS_RTC_LAYOUT_VERSION
                or inner.findtext(
                    "{http://www.abrasf.org.br/nfse.xsd}versaoDados"
                ) != WEBISS_RTC_LAYOUT_VERSION
            ):
                raise WebissMunicipalSchemaUnverified(
                    "WebISS SOAP header must use certified RTC layout version 2.02"
                )
        if part.tag == "nfseDadosMsg":
            signatures = inner.findall(f".//{{{_DS}}}Signature")
            if len(signatures) != _EXPECTED_SIGNATURE_COUNTS[operation]:
                raise WebissMgContractError(
                    "Unexpected WebISS signature count for fiscal operation"
                )
            for signature in signatures:
                ref = signature.find(
                    "{http://www.w3.org/2000/09/xmldsig#}SignedInfo/"
                    "{http://www.w3.org/2000/09/xmldsig#}Reference"
                )
                if ref is None or not ref.get("URI", "").startswith("#"):
                    raise WebissMgContractError("WebISS XMLDSig reference is missing")
                referenced_id = ref.get("URI", "")[1:]
                if sum(1 for node in inner.iter() if node.get("Id") == referenced_id) != 1:
                    raise WebissMgContractError("WebISS XMLDSig reference is ambiguous")


def _verify_fiscal_issuer_identity(
    *,
    envelope: Abrasf203Envelope,
    operation: Abrasf203Operation,
    issuer_cnpj: Cnpj,
    municipality_ibge: str,
) -> None:
    """Never allow a correctly signed SOAP envelope to change legal issuer.

    Consultation is unsigned and therefore MUST have its requester CNPJ
    checked against the scoped A1 before any network access. Issuance and
    cancellation are also checked before extracting tenant secrets.
    """
    try:
        soap = etree.fromstring(
            envelope.body,
            parser=etree.XMLParser(resolve_entities=False, no_network=True),
        )
        part = soap.find(f"{{{_SOAP}}}Body")[0][0]
        xml = etree.fromstring(
            str(part.findtext("nfseDadosMsg")).encode("utf-8"),
            parser=etree.XMLParser(resolve_entities=False, no_network=True),
        )
    except (AttributeError, IndexError, TypeError, etree.XMLSyntaxError):
        raise WebissMgContractError("Municipal fiscal issuer data is malformed") from None
    ns = {"a": "http://www.abrasf.org.br/nfse.xsd"}
    if operation is Abrasf203Operation.QUERY_BATCH:
        identities = [xml.findtext("a:Prestador/a:CpfCnpj/a:Cnpj", "", ns)]
    elif operation is Abrasf203Operation.SUBMIT_BATCH:
        identities = [xml.findtext("a:LoteRps/a:CpfCnpj/a:Cnpj", "", ns)]
        identities += [
            node.findtext("a:Prestador/a:CpfCnpj/a:Cnpj", "", ns)
            for node in xml.findall(
                "a:LoteRps/a:ListaRps/a:Rps/a:InfDeclaracaoPrestacaoServico", ns
            )
        ]
        if len(identities) <= 1:
            raise WebissMgContractError("Municipal issuance lacks RPS issuer identities")
    elif operation is Abrasf203Operation.GENERATE:
        identities = [
            xml.findtext(
                "a:Rps/a:InfDeclaracaoPrestacaoServico/a:Prestador/a:CpfCnpj/a:Cnpj",
                "", ns,
            )
        ]
    elif operation is Abrasf203Operation.CANCEL:
        identities = [
            xml.findtext(
                "a:Pedido/a:InfPedidoCancelamento/a:IdentificacaoNfse/"
                "a:CpfCnpj/a:Cnpj", "", ns,
            )
        ]
        municipality = xml.findtext(
            "a:Pedido/a:InfPedidoCancelamento/a:IdentificacaoNfse/"
            "a:CodigoMunicipio", "", ns,
        )
        if municipality != municipality_ibge:
            raise WebissMgContractError("Municipal cancellation belongs to another city")
    else:
        raise WebissMgContractError("Unsupported fiscal WebISS operation")
    if not identities or any(cnpj != issuer_cnpj.value for cnpj in identities):
        raise WebissMgContractError(
            "Municipal issuer CNPJ does not match the authorized tenant unit"
        )


def parse_webiss_soap_response(
    raw: bytes,
    operation: Abrasf203Operation,
    *,
    evidence: Webiss2026SchemaEvidence | None = None,
    municipal_validator: XmlSchemaValidator | None = None,
) -> bytes:
    """Return only the XML response payload; never infer fiscal authorization."""
    if not isinstance(raw, bytes) or not 0 < len(raw) <= _RESPONSE_LIMIT:
        raise WebissMgContractError("WebISS response exceeds the permitted size")
    try:
        root = etree.fromstring(
            raw, parser=etree.XMLParser(resolve_entities=False, no_network=True),
        )
    except etree.XMLSyntaxError:
        raise WebissMgContractError("Invalid WebISS SOAP response") from None
    if root.tag != f"{{{_SOAP}}}Envelope" or getattr(root.getroottree().docinfo, "doctype", None):
        raise WebissMgContractError("Invalid WebISS SOAP response root")
    body = root.find(f"{{{_SOAP}}}Body")
    if body is None or len(list(body)) != 1:
        raise WebissMgContractError("WebISS SOAP response lacks a single body")
    if body.find(f"{{{_SOAP}}}Fault") is not None:
        raise WebissMgContractError("WebISS returned SOAP Fault; reconcile before retry")
    method = operation.value[1]
    response = body[0]
    if response.tag != f"{{{_WSDL}}}{method}Response":
        raise WebissMgContractError("WebISS response method does not match request")
    values = list(response)
    if len(values) != 1 or values[0].tag != "outputXML" or not values[0].text:
        raise WebissMgContractError("WebISS outputXML is missing")
    xml: bytes = str(values[0].text).encode("utf-8")
    if len(xml) > _RESPONSE_LIMIT:
        raise WebissMgContractError("WebISS outputXML exceeds permitted size")
    try:
        extracted = etree.fromstring(
            xml, parser=etree.XMLParser(resolve_entities=False, no_network=True),
        )
    except etree.XMLSyntaxError:
        raise WebissMgContractError("Invalid WebISS outputXML") from None
    if getattr(extracted.getroottree().docinfo, "doctype", None):
        raise WebissMgContractError("DTD is prohibited in WebISS outputXML")
    expected = _RESPONSE_ROOTS.get(operation)
    if expected is None or extracted.tag != (
        "{http://www.abrasf.org.br/nfse.xsd}" + expected
    ):
        raise WebissMgContractError(
            "Municipal response XML root does not match the fiscal operation"
        )
    if (evidence is None) != (municipal_validator is None):
        raise WebissMunicipalSchemaUnverified(
            "Municipal response requires both XSD and pinned evidence"
        )
    if evidence is not None and municipal_validator is not None:
        validate_webiss_official_xml(
            evidence=evidence, validator=municipal_validator, xml=xml,
        )
    # An ABRASF receipt can contain rejection messages, PENDING status or
    # invoice data. Parsing does NOT promote it to AUTHORIZED; only the
    # canonical fiscal application may finalize an official result.
    return xml


def _verify_webiss_signature_with_scoped_a1(
    *, envelope: Abrasf203Envelope,
    operation: Abrasf203Operation,
    material: EphemeralCertificateMaterial,
) -> None:
    """Verify digest, issuer A1 cert and RSA/SHA-1 before municipal HTTP.

    The ABRASF/WebISS 2.02 legacy XMLDSig signature is not interchangeable
    with the SHA-256 signature of the National DPS 1.01. A tampered, wrapped
    or differently signed request is rejected even if its XML is XSD-valid.
    """
    if operation is Abrasf203Operation.QUERY_BATCH:
        return
    try:
        root = etree.fromstring(
            envelope.body,
            parser=etree.XMLParser(resolve_entities=False, no_network=True),
        )
        body_node = root.find(f"{{{_SOAP}}}Body")
        if body_node is None or len(body_node) != 1:
            raise ValueError
        wrapper = body_node[0]
        raw_xml = wrapper.findtext("nfseDadosMsg")
        fiscal = etree.fromstring(
            str(raw_xml).encode("utf-8"),
            parser=etree.XMLParser(resolve_entities=False, no_network=True),
        )
        signatures = fiscal.findall(f".//{{{_DS}}}Signature")
        key, cert, _ = pkcs12.load_key_and_certificates(
            material.pkcs12_bytes, material.password,
        )
        if key is None or cert is None or len(signatures) != (
            _EXPECTED_SIGNATURE_COUNTS[operation]
        ):
            raise ValueError
        public_key = cert.public_key()
        if not isinstance(public_key, rsa.RSAPublicKey):
            raise ValueError
        for signature in signatures:
            signed_info = signature.find(f"{{{_DS}}}SignedInfo")
            if signed_info is None:
                raise ValueError
            signed_method = signed_info.find(f"{{{_DS}}}SignatureMethod")
            reference = signed_info.find(f"{{{_DS}}}Reference")
            digest_value = (
                reference.find(f"{{{_DS}}}DigestValue") if reference is not None else None
            )
            digest_method = (
                reference.find(f"{{{_DS}}}DigestMethod") if reference is not None else None
            )
            transforms = (
                reference.findall(f"{{{_DS}}}Transforms/{{{_DS}}}Transform")
                if reference is not None else []
            )
            if (
                signed_method is None
                or signed_method.get("Algorithm") != _DS + "rsa-sha1"
                or reference is None
                or digest_method is None
                or digest_method.get("Algorithm") != _DS + "sha1"
                or digest_value is None
                or len(transforms) != 2
                or [t.get("Algorithm") for t in transforms] != [
                    _DS + "enveloped-signature",
                    "http://www.w3.org/TR/2001/REC-xml-c14n-20010315",
                ]
                or not reference.get("URI", "").startswith("#")
            ):
                raise ValueError
            identity = reference.get("URI", "")[1:]
            targets = [
                node for node in fiscal.iter() if node.get("Id") == identity
            ]
            if len(targets) != 1:
                raise ValueError
            canonical_target = etree.tostring(
                targets[0], method="c14n", exclusive=False, with_comments=False,
            )
            expected_digest = hashlib.sha1(canonical_target).digest()
            if not hmac.compare_digest(
                base64.b64decode(str(digest_value.text), validate=True),
                expected_digest,
            ):
                raise ValueError
            x509_blob = signature.find(
                f"{{{_DS}}}KeyInfo/{{{_DS}}}X509Data/{{{_DS}}}X509Certificate"
            )
            if x509_blob is None or not hmac.compare_digest(
                base64.b64decode(str(x509_blob.text), validate=True),
                cert.public_bytes(serialization.Encoding.DER),
            ):
                raise ValueError
            value = signature.find(f"{{{_DS}}}SignatureValue")
            if value is None:
                raise ValueError
            public_key.verify(
                base64.b64decode(str(value.text), validate=True),
                etree.tostring(
                    signed_info, method="c14n",
                    exclusive=False, with_comments=False,
                ),
                padding.PKCS1v15(), hashes.SHA1(),
            )
    except (
        AttributeError, IndexError, TypeError, ValueError, InvalidSignature,
        etree.XMLSyntaxError,
    ):
        raise WebissMgContractError(
            "WebISS XMLDSig does not match the scoped A1 or signed fiscal content"
        ) from None


def _webiss_exchange(
    body: bytes, soap_action: str, tls_context: ssl.SSLContext, timeout: float,
) -> bytes:
    request = Request(
        EXTREMA_WEBISS_HOMOLOGATION_URL, data=body, method="POST",
        headers={
            "Content-Type": "text/xml; charset=utf-8",
            "SOAPAction": soap_action,
            "Accept": "text/xml",
        },
    )
    try:
        opener = build_opener(HTTPSHandler(context=tls_context), RejectFiscalRedirects())
        with opener.open(request, timeout=timeout) as response:
            content = response.read(_RESPONSE_LIMIT + 1)
        if len(content) > _RESPONSE_LIMIT:
            raise WebissMgContractError("WebISS SOAP response is too large")
        return bytes(content)
    except (HTTPError, URLError, TimeoutError, OSError, ssl.SSLError):
        raise WebissMgContractError(
            "WebISS transport is ambiguous; query before any retransmission"
        ) from None


class WebissMgHomologationTransport:
    """Shared WebISS transport for two sourced cities, no second provider authority."""

    def __init__(
        self,
        *,
        provider_resolver: ProviderSelectionResolver,
        resolve_certificate: Callable[[ExecutionScope, str], EphemeralCertificateMaterial],
        municipality_ibge: str,
        municipal_schema_evidence: Webiss2026SchemaEvidence | None = None,
        municipal_schema_validator: XmlSchemaValidator | None = None,
        exchange: Callable[[bytes, str, ssl.SSLContext, float], bytes] | None = None,
        timeout_seconds: float = 15,
    ) -> None:
        if (
            not callable(getattr(provider_resolver, "resolve_provider_id", None))
            or not callable(resolve_certificate)
            or not 0 < timeout_seconds <= 30
        ):
            raise ValueError("WebISS requires canonical provider, A1 resolver and timeout")
        if municipality_ibge not in _MG_WEBISS_PROVIDERS:
            raise ValueError("Only sourced WebISS MG municipal channels are allowed")
        if (municipal_schema_evidence is None) != (municipal_schema_validator is None):
            raise ValueError("WebISS RTC schema evidence and validator must match")
        if (
            municipal_schema_evidence is not None
            and municipal_schema_evidence.municipality_ibge != municipality_ibge
        ):
            raise ValueError("WebISS schema evidence belongs to another municipality")
        self._municipality = municipality_ibge
        self._schema_evidence = municipal_schema_evidence
        self._schema_validator = municipal_schema_validator
        self._resolver = provider_resolver
        self._certificate = resolve_certificate
        # No municipality-specific verified Uberaba homologation endpoint yet.
        # Never leak an Uberaba document to the Extrema default URL.
        self._exchange = (
            exchange if exchange is not None
            else _webiss_exchange if municipality_ibge == EXTREMA_IBGE
            else self._unsupported_municipal_transport
        )
        self._timeout = timeout_seconds

    @staticmethod
    def _unsupported_municipal_transport(
        body: bytes, soap_action: str, context: ssl.SSLContext, timeout: float,
    ) -> bytes:
        del body, soap_action, context, timeout
        raise WebissMgContractError(
            "WebISS city-specific homologation URL is not officially certified"
        )

    def exchange_prepared(
        self,
        *,
        envelope: Abrasf203Envelope,
        operation: Abrasf203Operation,
        scope: ExecutionScope,
        issuer_cnpj: Cnpj,
        issuer_tax_regime: TaxRegimeCode,
        competence_date: date,
        jurisdiction: BrazilianJurisdiction,
    ) -> bytes:
        if (
            not isinstance(scope, ExecutionScope)
            or scope.host_namespace is None
            or scope.environment is not FiscalEnvironment.HOMOLOGATION
            or jurisdiction != BrazilianJurisdiction("MG", self._municipality)
        ):
            raise WebissMgContractError("WebISS is restricted to the scoped MG municipality")
        if not isinstance(issuer_cnpj, Cnpj):
            raise WebissMgContractError("Issuer CNPJ is required")
        if not isinstance(issuer_tax_regime, TaxRegimeCode) or not isinstance(
            competence_date, date
        ):
            raise WebissMgContractError("Trusted regime and competence are required")
        if issuer_tax_regime is TaxRegimeCode.MEI or (
            issuer_tax_regime in (
                TaxRegimeCode.SIMPLES_NACIONAL,
                TaxRegimeCode.SIMPLES_NACIONAL_EXCESS_SUBLIMIT,
            )
            and competence_date >= date(2026, 11, 1)
        ):
            raise WebissMgContractError(
                "Competence/regime requires Emissor Nacional, not municipal WebISS"
            )
        if self._schema_evidence is None or self._schema_validator is None:
            raise WebissMunicipalSchemaUnverified(
                "Official WebISS municipal RTC XSD not installed; transmission denied"
            )
        _validate_request_envelope(
            envelope, operation, evidence=self._schema_evidence,
            municipal_validator=self._schema_validator,
        )
        _verify_fiscal_issuer_identity(
            envelope=envelope,
            operation=operation,
            issuer_cnpj=issuer_cnpj,
            municipality_ibge=self._municipality,
        )
        provider = self._resolver.resolve_provider_id(
            scope=scope,
            document_kind=FiscalDocumentKind.NFSE,
            jurisdiction=jurisdiction,
            operation=_ACTIONS[operation].value,
        )
        if provider != _MG_WEBISS_PROVIDERS[self._municipality]:
            raise WebissMgContractError("No approved exact WebISS municipal binding")
        material = self._certificate(scope, issuer_cnpj.value)
        validate_a1_for_issuer(
            material.pkcs12_bytes, material.password,
            issuer_cnpj=issuer_cnpj, at=datetime.now(UTC),
        )
        _verify_webiss_signature_with_scoped_a1(
            envelope=envelope, operation=operation, material=material,
        )
        raw = self._exchange(
            envelope.body, envelope.soap_action,
            build_fiscal_tls_context(material), self._timeout,
        )
        return parse_webiss_soap_response(
            raw, operation, evidence=self._schema_evidence,
            municipal_validator=self._schema_validator,
        )


class WebissExtremaHomologationTransport(WebissMgHomologationTransport):
    """Extrema WebISS operation via the single shared municipal transport."""

    def __init__(
        self,
        *,
        provider_resolver: ProviderSelectionResolver,
        resolve_certificate: Callable[[ExecutionScope, str], EphemeralCertificateMaterial],
        municipal_schema_evidence: Webiss2026SchemaEvidence | None = None,
        municipal_schema_validator: XmlSchemaValidator | None = None,
        exchange: Callable[[bytes, str, ssl.SSLContext, float], bytes] | None = None,
        timeout_seconds: float = 15,
    ) -> None:
        super().__init__(
            provider_resolver=provider_resolver,
            resolve_certificate=resolve_certificate,
            municipality_ibge=EXTREMA_IBGE,
            municipal_schema_evidence=municipal_schema_evidence,
            municipal_schema_validator=municipal_schema_validator,
            exchange=exchange,
            timeout_seconds=timeout_seconds,
        )


class WebissUberabaHomologationTransport(WebissMgHomologationTransport):
    """Uberaba WebISS operation via the same signed envelope/TLS boundary."""

    def __init__(
        self,
        *,
        provider_resolver: ProviderSelectionResolver,
        resolve_certificate: Callable[[ExecutionScope, str], EphemeralCertificateMaterial],
        municipal_schema_evidence: Webiss2026SchemaEvidence | None = None,
        municipal_schema_validator: XmlSchemaValidator | None = None,
        exchange: Callable[[bytes, str, ssl.SSLContext, float], bytes] | None = None,
        timeout_seconds: float = 15,
    ) -> None:
        super().__init__(
            provider_resolver=provider_resolver,
            resolve_certificate=resolve_certificate,
            municipality_ibge=UBERABA_IBGE,
            municipal_schema_evidence=municipal_schema_evidence,
            municipal_schema_validator=municipal_schema_validator,
            exchange=exchange,
            timeout_seconds=timeout_seconds,
        )
