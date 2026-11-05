"""NFS-e Nacional: deterministic, homologation-only DPS HTTP/mTLS boundary.

This transport accepts already prepared, signed DPS XML; it is NOT the authority
that builds a fiscal document or selects a municipality. ADN is a separate
distribution interface and is deliberately not used for issuance.
"""
from __future__ import annotations

import base64
import gzip
import json
import ssl
from collections.abc import Callable
from urllib.error import HTTPError, URLError
from urllib.request import HTTPSHandler, Request, build_opener

from lxml import etree

from kordena_fiscal.domain import FiscalValidationError
from kordena_fiscal.gateway.nfe_sp_homologation import _tls_context
from kordena_fiscal.signing.nfse_xmldsig import sign_nfse_dps_xml
from kordena_fiscal.vault import EphemeralCertificateMaterial

SEFIN_HOMOLOGATION_NFSE_URL = (
    "https://sefin.producaorestrita.nfse.gov.br/API/SefinNacional/nfse"
)
_MAX_DPS_BYTES = 2_097_152
_MAX_RESPONSE_BYTES = 4_194_304


class OfficialNfseTransportError(FiscalValidationError):
    """Safe, non-secret NFS-e transport failure."""


def build_nfse_dps_request(signed_dps_xml: bytes) -> bytes:
    """Build the public Emissor Nacional API JSON envelope from signed DPS XML."""
    if not signed_dps_xml or len(signed_dps_xml) > _MAX_DPS_BYTES:
        raise OfficialNfseTransportError("DPS ausente ou excede o limite")
    try:
        root = etree.fromstring(
            signed_dps_xml, parser=etree.XMLParser(resolve_entities=False, no_network=True)
        )
    except etree.XMLSyntaxError:
        raise OfficialNfseTransportError("XML da DPS inválido") from None
    if etree.QName(root).localname != "DPS":
        raise OfficialNfseTransportError("Envelope exige raiz DPS")
    infos = [
        child for child in root if etree.QName(child).localname == "infDPS"
    ]
    if len(infos) != 1:
        raise OfficialNfseTransportError("infDPS obrigatória")
    if not infos[0].get("Id"):
        raise OfficialNfseTransportError("Identificador de infDPS obrigatório")
    environments = [
        child for child in root.iter() if etree.QName(child).localname == "tpAmb"
    ]
    if len(environments) != 1 or environments[0].text != "2":
        raise OfficialNfseTransportError("DPS exige tpAmb=2")
    signatures = [
        child for child in root
        if etree.QName(child).localname == "Signature"
        and etree.QName(child).namespace == "http://www.w3.org/2000/09/xmldsig#"
    ]
    if len(signatures) != 1:
        raise OfficialNfseTransportError("DPS exige assinatura XMLDSig")
    return json.dumps(
        {"dpsXmlGZipB64": base64.b64encode(gzip.compress(signed_dps_xml, mtime=0)).decode("ascii")},
        separators=(",", ":"),
    ).encode("ascii")


def parse_nfse_homologation_response(raw: bytes) -> dict[str, str]:
    """Expose only references and canonical XML; never reflect provider internals."""
    if not raw or len(raw) > _MAX_RESPONSE_BYTES:
        raise OfficialNfseTransportError("Resposta da NFS-e Nacional ausente ou excede limite")
    try:
        payload = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        raise OfficialNfseTransportError("Resposta inválida da NFS-e Nacional") from None
    if not isinstance(payload, dict):
        raise OfficialNfseTransportError("Resposta inválida da NFS-e Nacional")
    access_key = payload.get("chaveAcesso")
    encoded = payload.get("nfseXmlGZipB64")
    if isinstance(access_key, str) and access_key and isinstance(encoded, str) and encoded:
        try:
            zipped = base64.b64decode(encoded, validate=True)
            if len(zipped) > _MAX_RESPONSE_BYTES:
                raise ValueError
            # Bound the uncompressed payload to prevent compression bombs.
            with gzip.GzipFile(fileobj=__import__("io").BytesIO(zipped)) as stream:
                document = stream.read(_MAX_RESPONSE_BYTES + 1)
            if len(document) > _MAX_RESPONSE_BYTES:
                raise ValueError
            etree.fromstring(
                document, parser=etree.XMLParser(resolve_entities=False, no_network=True)
            )
        except (ValueError, OSError, etree.XMLSyntaxError):
            raise OfficialNfseTransportError(
                "XML retornado pela NFS-e Nacional é inválido"
            ) from None
        return {"status": "authorized", "chaveAcesso": access_key, "xml": document.decode("utf-8")}
    raise OfficialNfseTransportError(
        "NFS-e Nacional não autorizou a DPS; consulte as rejeições no retorno oficial"
    )


class NfseNationalHomologationTransport:
    """Bound, non-retrying HTTPS POST; ambiguous fiscal submissions need reconciliation."""

    def __init__(
        self,
        *,
        certificate: EphemeralCertificateMaterial,
        timeout_seconds: float = 15.0,
        exchange: Callable[[bytes, ssl.SSLContext, float], bytes] | None = None,
    ) -> None:
        if not isinstance(certificate, EphemeralCertificateMaterial):
            raise OfficialNfseTransportError("Certificado A1 não localizado para o CNPJ")
        if not 0 < timeout_seconds <= 30:
            raise ValueError("Timeout fiscal inválido")
        self._certificate = certificate
        self._timeout = timeout_seconds
        self._exchange = exchange or self._https_exchange

    @staticmethod
    def _https_exchange(body: bytes, context: ssl.SSLContext, timeout: float) -> bytes:
        request = Request(
            SEFIN_HOMOLOGATION_NFSE_URL,
            data=body,
            method="POST",
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        try:
            opener = build_opener(HTTPSHandler(context=context))
            with opener.open(request, timeout=timeout) as response:
                raw = response.read(_MAX_RESPONSE_BYTES + 1)
        except (HTTPError, URLError, TimeoutError, OSError, ssl.SSLError):
            raise OfficialNfseTransportError(
                "Falha de comunicação com a NFS-e Nacional; consulte antes de reenviar"
            ) from None
        if len(raw) > _MAX_RESPONSE_BYTES:
            raise OfficialNfseTransportError("Resposta da NFS-e Nacional excede limite")
        return bytes(raw)

    def submit_signed_dps(self, signed_dps_xml: bytes) -> dict[str, str]:
        """Send only homologation DPS, without changing business authorization."""
        body = build_nfse_dps_request(signed_dps_xml)
        return parse_nfse_homologation_response(
            self._exchange(body, _tls_context(self._certificate), self._timeout)
        )

    def sign_and_submit_dps(self, unsigned_dps_xml: bytes) -> dict[str, str]:
        """Use the same scoped A1 identity for XMLDSig and the mTLS handshake."""
        return self.submit_signed_dps(
            sign_nfse_dps_xml(unsigned_dps_xml, self._certificate)
        )
