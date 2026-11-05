"""Official SEFAZ-SP NF-e 4.00 homologation authorization over TLS/mTLS.

Operates only with an authorized, signed model-55 XML envelope and a
scope-bound A1 identity. No synthetic responses or production endpoints.
"""
from __future__ import annotations

import os
import ssl
import tempfile
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import HTTPSHandler, Request, build_opener

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import pkcs12
from lxml import etree

from kordena_fiscal.domain import Cnpj, ExecutionScope, FiscalEnvironment, FiscalValidationError
from kordena_fiscal.signing.nfe_xmldsig import sign_nfe_envi_xml
from kordena_fiscal.vault import EphemeralCertificateMaterial
from kordena_fiscal.vault.a1_preflight import validate_a1_for_issuer

from .authorization import (
    AuthorizationRequest,
    AuthorizationResult,
    AuthorizationStatus,
    GatewayProviderMetadata,
)

NFE_SP_HOMOLOGATION_AUTHORIZATION_URL = (
    "https://homologacao.nfe.fazenda.sp.gov.br/ws/nfeautorizacao4.asmx"
)
SOAP12_NAMESPACE = "http://www.w3.org/2003/05/soap-envelope"
NFE_NAMESPACE = "http://www.portalfiscal.inf.br/nfe"
SERVICE_NAMESPACE = "http://www.portalfiscal.inf.br/nfe/wsdl/NFeAutorizacao4"
XMLDSIG_NAMESPACE = "http://www.w3.org/2000/09/xmldsig#"
_MAX_RESPONSE_BYTES = 2_097_152
_PROVIDER = GatewayProviderMetadata("sefaz-sp-homologacao-nfe4", "1.0")


class OfficialNfeTransportError(FiscalValidationError):
    """Sanitized transport failure, without certificate or response contents."""


def _parse_xml(data: bytes) -> etree._Element:
    if len(data) > _MAX_RESPONSE_BYTES or not data:
        raise OfficialNfeTransportError("XML fiscal ausente ou excede limite")
    try:
        return etree.fromstring(
            data, parser=etree.XMLParser(resolve_entities=False, no_network=True)
        )
    except etree.XMLSyntaxError:
        raise OfficialNfeTransportError("XML fiscal inválido") from None


def _text(element: etree._Element, name: str) -> str | None:
    found = element.find(".//{" + NFE_NAMESPACE + "}" + name)
    return found.text.strip() if found is not None and found.text else None


def _signed_homologation_xml(request: AuthorizationRequest, xml_bytes: bytes) -> etree._Element:
    if request.scope.environment is not FiscalEnvironment.HOMOLOGATION:
        raise OfficialNfeTransportError("Somente homologação (tpAmb=2) permitida")
    root = _parse_xml(xml_bytes)
    if root.tag != "{" + NFE_NAMESPACE + "}enviNFe":
        raise OfficialNfeTransportError("Autorização requer enviNFe 4.00")
    if root.get("versao") != "4.00":
        raise OfficialNfeTransportError("Versão de NF-e não suportada")
    invoices = root.findall("{" + NFE_NAMESPACE + "}NFe")
    if not invoices:
        raise OfficialNfeTransportError("Lote de NF-e vazio")
    for invoice in invoices:
        info = invoice.find("{" + NFE_NAMESPACE + "}infNFe")
        signature = invoice.find("{" + XMLDSIG_NAMESPACE + "}Signature")
        ambient = invoice.find(
            ".//{" + NFE_NAMESPACE + "}ide/{" + NFE_NAMESPACE + "}tpAmb"
        )
        if info is None or info.get("Id") != "NFe" + request.access_key.value:
            raise OfficialNfeTransportError("Chave de acesso não corresponde ao XML")
        if info is None or signature is None or ambient is None or ambient.text != "2":
            raise OfficialNfeTransportError("NF-e exige assinatura XMLDSig e tpAmb=2")
        signed_info = signature.find("{" + XMLDSIG_NAMESPACE + "}SignedInfo")
        sig_value = signature.find("{" + XMLDSIG_NAMESPACE + "}SignatureValue")
        if signed_info is None or sig_value is None or not sig_value.text:
            raise OfficialNfeTransportError("Assinatura XMLDSig incompleta")
    return root


def _soap_envelope(invoice_batch: etree._Element) -> bytes:
    envelope = etree.Element(
        "{" + SOAP12_NAMESPACE + "}Envelope",
        nsmap={"soap12": SOAP12_NAMESPACE},
    )
    body = etree.SubElement(envelope, "{" + SOAP12_NAMESPACE + "}Body")
    data = etree.SubElement(body, "{" + SERVICE_NAMESPACE + "}nfeDadosMsg")
    data.append(invoice_batch)
    return etree.tostring(envelope, encoding="utf-8", xml_declaration=True)


def _tls_context(material: EphemeralCertificateMaterial) -> ssl.SSLContext:
    """Materialize mTLS keypair only inside a private temporary directory."""
    key, cert, chain = pkcs12.load_key_and_certificates(
        material.pkcs12_bytes, material.password
    )
    if key is None or cert is None:
        raise OfficialNfeTransportError("Certificado A1 inválido ou incompleto")
    context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    with tempfile.TemporaryDirectory(prefix="nfcore-mtls-") as directory:
        key_file = Path(directory) / "key.pem"
        cert_file = Path(directory) / "cert.pem"
        key_file.write_bytes(key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ))
        cert_file.write_bytes(cert.public_bytes(serialization.Encoding.PEM) + b"".join(
            item.public_bytes(serialization.Encoding.PEM) for item in (chain or [])
        ))
        os.chmod(key_file, 0o600)
        os.chmod(cert_file, 0o600)
        context.load_cert_chain(str(cert_file), str(key_file))
    return context


class SefazSpHomologationGateway:
    """Real NF-e 4.00 SOAP 1.2 authorization (official SP homologation only)."""

    def __init__(
        self,
        *,
        resolve_certificate: Callable[[ExecutionScope, str], EphemeralCertificateMaterial],
        timeout_seconds: float = 15.0,
        exchange: Callable[[bytes, ssl.SSLContext, float], bytes] | None = None,
    ) -> None:
        if not callable(resolve_certificate) or not 0 < timeout_seconds <= 60:
            raise ValueError("Invalid fiscal transport configuration")
        self._resolve_certificate = resolve_certificate
        self._timeout = timeout_seconds
        self._exchange = exchange or self._https_exchange

    @staticmethod
    def _https_exchange(payload: bytes, context: ssl.SSLContext, timeout: float) -> bytes:
        req = Request(
            NFE_SP_HOMOLOGATION_AUTHORIZATION_URL,
            data=payload,
            method="POST",
            headers={
                "Content-Type": (
                    "application/soap+xml; charset=utf-8; "
                    'action="http://www.portalfiscal.inf.br/nfe/wsdl/NFeAutorizacao4/nfeAutorizacaoLote"'
                ),
                "Accept": "application/soap+xml",
            },
        )
        opener = build_opener(HTTPSHandler(context=context))
        try:
            with opener.open(req, timeout=timeout) as response:
                raw = response.read(_MAX_RESPONSE_BYTES + 1)
            if len(raw) > _MAX_RESPONSE_BYTES:
                raise OfficialNfeTransportError("Resposta fiscal excede limite")
            return bytes(raw)
        except (HTTPError, URLError, TimeoutError, OSError, ssl.SSLError):
            raise OfficialNfeTransportError(
                "Comunicação com a SEFAZ-SP indisponível; verifique o resultado antes de reenviar"
            ) from None

    def authorize(self, request: AuthorizationRequest) -> AuthorizationResult:
        if not isinstance(request, AuthorizationRequest):
            raise OfficialNfeTransportError("Solicitação de autorização fiscal inválida")
        material = self._resolve_certificate(
            request.scope, request.access_key.issuer_identifier
        )
        if not isinstance(material, EphemeralCertificateMaterial):
            raise OfficialNfeTransportError("Certificado A1 não cadastrado para o CNPJ emitente")
        validate_a1_for_issuer(
            material.pkcs12_bytes,
            material.password,
            issuer_cnpj=Cnpj(request.access_key.issuer_identifier),
            at=datetime.now(UTC),
        )
        unsigned = _parse_xml(request.signed_xml)
        signed_bytes = request.signed_xml
        if unsigned.find(".//{" + XMLDSIG_NAMESPACE + "}Signature") is None:
            signed_bytes = sign_nfe_envi_xml(request.signed_xml, material)
        xml = _signed_homologation_xml(request, signed_bytes)
        context = _tls_context(material)
        response = _parse_xml(
            self._exchange(_soap_envelope(xml), context, self._timeout)
        )
        if response.find(".//{" + SOAP12_NAMESPACE + "}Fault") is not None:
            raise OfficialNfeTransportError("SEFAZ-SP retornou falha SOAP")
        result = response.find(".//{" + NFE_NAMESPACE + "}retEnviNFe")
        if result is None or _text(result, "tpAmb") != "2":
            raise OfficialNfeTransportError("Resposta da SEFAZ-SP sem homologação válida")
        code = _text(result, "cStat")
        reason = _text(result, "xMotivo")
        if not code:
            raise OfficialNfeTransportError("Resposta de autorização sem código de status")
        receipt = _text(result, "nRec")
        if code in {"103", "104", "105"}:
            protocol = result.find(".//{" + NFE_NAMESPACE + "}infProt")
            authorization_code = _text(protocol, "cStat") if protocol is not None else None
            protocol_no = _text(protocol, "nProt") if protocol is not None else None
            if authorization_code == "100" and protocol_no:
                return AuthorizationResult(
                    status=AuthorizationStatus.AUTHORIZED,
                    scope=request.scope,
                    access_key=request.access_key,
                    idempotency_key=request.idempotency_key,
                    request_fingerprint=request.request_fingerprint,
                    provider=_PROVIDER,
                    provider_request_id=receipt,
                    protocol_reference=protocol_no,
                )
            if code in {"103", "105"}:
                status = AuthorizationStatus.PENDING
            elif authorization_code and authorization_code not in {"100", "105"}:
                status = AuthorizationStatus.REJECTED
                code = authorization_code
                reason = _text(protocol, "xMotivo") if protocol is not None else reason
            else:
                status = AuthorizationStatus.PENDING
        else:
            status = AuthorizationStatus.REJECTED
        return AuthorizationResult(
            status=status,
            scope=request.scope,
            access_key=request.access_key,
            idempotency_key=request.idempotency_key,
            request_fingerprint=request.request_fingerprint,
            provider=_PROVIDER,
            provider_request_id=receipt,
            rejection_code=code if status is AuthorizationStatus.REJECTED else None,
            rejection_message=(reason or "Rejeição fiscal")[:512]
            if status is AuthorizationStatus.REJECTED else None,
        )
