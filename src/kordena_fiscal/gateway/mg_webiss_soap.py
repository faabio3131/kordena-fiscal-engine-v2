"""Scoped WebISS MG SOAP 1.1 homologation transport, no alternate fiscal authority.

The public Extrema WebISS WSDL advertises SOAP actions for GerarNfse,
RecepcionarLoteRps and ConsultarLoteRps. This transport reuses the existing
ABRASF 2.03 XML/XSD/XMLDSig preparer and the canonical DURABLE unit binding.
The provider's municipality-specific schema version is not certified here:
do not register this adapter as production-ready until WSDL/XSD parity,
credentials, municipal ISS rules and official responses are proved.
"""
from __future__ import annotations

import ssl
from collections.abc import Callable
from datetime import UTC, date, datetime
from urllib.error import HTTPError, URLError
from urllib.request import HTTPSHandler, Request, build_opener

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
from kordena_fiscal.vault import EphemeralCertificateMaterial
from kordena_fiscal.vault.a1_preflight import validate_a1_for_issuer

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
_ACTIONS = {
    Abrasf203Operation.GENERATE: ConfiguredFiscalOperation.AUTHORIZE,
    Abrasf203Operation.SUBMIT_BATCH: ConfiguredFiscalOperation.AUTHORIZE,
    Abrasf203Operation.QUERY_BATCH: ConfiguredFiscalOperation.QUERY,
    Abrasf203Operation.CANCEL: ConfiguredFiscalOperation.CANCEL,
}


class WebissMgContractError(FiscalValidationError):
    """Sanitized municipal mismatch, response error or ambiguous transport."""


def _validate_request_envelope(
    envelope: Abrasf203Envelope, operation: Abrasf203Operation,
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


def parse_webiss_soap_response(raw: bytes, operation: Abrasf203Operation) -> bytes:
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
    # This is NOT an authorized fiscal document until protocol, issuer,
    # XMLDSig and municipal response codes are verified by the domain layer.
    return xml


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
        self._municipality = municipality_ibge
        self._resolver = provider_resolver
        self._certificate = resolve_certificate
        self._exchange = exchange or _webiss_exchange
        self._timeout = timeout_seconds

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
        _validate_request_envelope(envelope, operation)
        if operation is Abrasf203Operation.CANCEL:
            # A signed municipal cancellation must use the bound issuer/city;
            # SOAPAction alone is never sufficient to authorize a fiscal event.
            soap = etree.fromstring(
                envelope.body,
                parser=etree.XMLParser(resolve_entities=False, no_network=True),
            )
            raw_xml = soap[0][0].findtext("nfseDadosMsg")
            try:
                fiscal = etree.fromstring(
                    str(raw_xml).encode("utf-8"),
                    parser=etree.XMLParser(resolve_entities=False, no_network=True),
                )
            except etree.XMLSyntaxError:
                raise WebissMgContractError("Invalid signed cancellation XML") from None
            ns = {"a": "http://www.abrasf.org.br/nfse.xsd"}
            identifier = fiscal.find(
                "a:Pedido/a:InfPedidoCancelamento/a:IdentificacaoNfse", ns,
            )
            if (
                identifier is None
                or identifier.findtext("a:CodigoMunicipio", "", ns)
                != self._municipality
                or identifier.findtext("a:CpfCnpj/a:Cnpj", "", ns)
                != issuer_cnpj.value
                or fiscal.find(
                    "a:Pedido/{http://www.w3.org/2000/09/xmldsig#}Signature", ns,
                ) is None
            ):
                raise WebissMgContractError(
                    "Municipal cancellation does not match bound issuer and city"
                )
        provider = self._resolver.resolve_provider_id(
            scope=scope,
            document_kind=FiscalDocumentKind.NFSE,
            jurisdiction=jurisdiction,
            operation=_ACTIONS[operation].value,
        )
        if provider != _MG_WEBISS_PROVIDERS[self._municipality]:
            raise WebissMgContractError("No approved exact WebISS municipal binding")
        if not isinstance(issuer_cnpj, Cnpj):
            raise WebissMgContractError("Issuer CNPJ is required")
        material = self._certificate(scope, issuer_cnpj.value)
        validate_a1_for_issuer(
            material.pkcs12_bytes, material.password,
            issuer_cnpj=issuer_cnpj, at=datetime.now(UTC),
        )
        raw = self._exchange(
            envelope.body, envelope.soap_action,
            build_fiscal_tls_context(material), self._timeout,
        )
        return parse_webiss_soap_response(raw, operation)


class WebissExtremaHomologationTransport(WebissMgHomologationTransport):
    """Extrema WebISS operation via the single shared municipal transport."""

    def __init__(
        self,
        *,
        provider_resolver: ProviderSelectionResolver,
        resolve_certificate: Callable[[ExecutionScope, str], EphemeralCertificateMaterial],
        exchange: Callable[[bytes, str, ssl.SSLContext, float], bytes] | None = None,
        timeout_seconds: float = 15,
    ) -> None:
        super().__init__(
            provider_resolver=provider_resolver,
            resolve_certificate=resolve_certificate,
            municipality_ibge=EXTREMA_IBGE,
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
        exchange: Callable[[bytes, str, ssl.SSLContext, float], bytes] | None = None,
        timeout_seconds: float = 15,
    ) -> None:
        super().__init__(
            provider_resolver=provider_resolver,
            resolve_certificate=resolve_certificate,
            municipality_ibge=UBERABA_IBGE,
            exchange=exchange,
            timeout_seconds=timeout_seconds,
        )
