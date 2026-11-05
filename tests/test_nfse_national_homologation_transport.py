"""Offline envelope and cryptographic tests; no fiscal endpoint is contacted."""
from __future__ import annotations

import base64
import gzip
import hashlib
import json
from datetime import UTC, datetime, timedelta

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.serialization import BestAvailableEncryption, pkcs12
from cryptography.x509.oid import NameOID
from lxml import etree

from kordena_fiscal.domain import FiscalValidationError
from kordena_fiscal.gateway.nfse_national_homologation import (
    OfficialNfseTransportError,
    build_nfse_dps_request,
    parse_nfse_homologation_response,
)
from kordena_fiscal.signing.nfse_xmldsig import sign_nfse_dps_xml
from kordena_fiscal.vault import EphemeralCertificateMaterial

_NS = "http://www.sped.fazenda.gov.br/nfse"
_DS = "http://www.w3.org/2000/09/xmldsig#"


def _unsigned_dps(environment: str = "2") -> bytes:
    root = etree.Element(f"{{{_NS}}}DPS", nsmap={None: _NS})
    info = etree.SubElement(root, f"{{{_NS}}}infDPS", Id="DPS1234567890")
    etree.SubElement(info, f"{{{_NS}}}tpAmb").text = environment
    return etree.tostring(root, encoding="utf-8")


def _ephemeral_certificate() -> tuple[EphemeralCertificateMaterial, rsa.RSAPrivateKey]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "NFCore Offline Test")])
    now = datetime.now(UTC)
    cert = (
        x509.CertificateBuilder().subject_name(name).issuer_name(name)
        .public_key(key.public_key()).serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=1))
        .sign(key, hashes.SHA256())
    )
    blob = pkcs12.serialize_key_and_certificates(
        b"nfcore-test", key, cert, None, BestAvailableEncryption(b"unit-test")
    )
    return EphemeralCertificateMaterial(
        reference_id="ref:nfcore-offline", pkcs12_bytes=blob, password=b"unit-test"
    ), key


def test_dps_signature_is_verifiable_and_envelope_is_gzipped() -> None:
    identity, key = _ephemeral_certificate()
    signed = sign_nfse_dps_xml(_unsigned_dps(), identity)
    root = etree.fromstring(signed)
    info = root.xpath("./*[local-name()='infDPS']")[0]
    signature = root.find(f"{{{_DS}}}Signature")
    assert signature is not None
    signed_info = signature.find(f"{{{_DS}}}SignedInfo")
    assert signed_info is not None
    signature_value = signature.findtext(f"{{{_DS}}}SignatureValue")
    assert signature_value
    key.public_key().verify(
        base64.b64decode(signature_value),
        etree.tostring(signed_info, method="c14n", exclusive=False, with_comments=False),
        padding.PKCS1v15(), hashes.SHA256(),
    )
    digest = signature.findtext(f".//{{{_DS}}}DigestValue")
    assert digest == base64.b64encode(
        hashlib.sha256(
            etree.tostring(info, method="c14n", exclusive=False, with_comments=False)
        ).digest()
    ).decode("ascii")
    payload = json.loads(build_nfse_dps_request(signed))
    assert gzip.decompress(base64.b64decode(payload["dpsXmlGZipB64"])) == signed


def test_nfse_rejects_production_dps_before_signing() -> None:
    identity, _ = _ephemeral_certificate()
    with pytest.raises(FiscalValidationError, match="tpAmb=2"):
        sign_nfse_dps_xml(_unsigned_dps("1"), identity)


def test_nfse_rejects_missing_xml_signature() -> None:
    with pytest.raises(OfficialNfseTransportError, match="XMLDSig"):
        build_nfse_dps_request(_unsigned_dps())


def test_nfse_parses_offline_authorization_receipt() -> None:
    xml = b"<NFSe xmlns='http://www.sped.fazenda.gov.br/nfse'/>"
    response = json.dumps({
        "chaveAcesso": "35000000000000000000000000000000000000000000000000",
        "nfseXmlGZipB64": base64.b64encode(gzip.compress(xml)).decode("ascii"),
    }).encode("utf-8")
    parsed = parse_nfse_homologation_response(response)
    assert parsed["status"] == "authorized"
    assert parsed["xml"] == xml.decode()


def test_nfse_rejects_invalid_response_without_secret_echo() -> None:
    with pytest.raises(OfficialNfseTransportError):
        parse_nfse_homologation_response(b'{"secret":"never echo"}')
