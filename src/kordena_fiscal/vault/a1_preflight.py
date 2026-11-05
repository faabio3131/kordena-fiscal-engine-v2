"""Fail-closed local A1 PKCS#12 issuer preflight, never a certificate store.

This checks the private-key/certificate pair, temporal validity, signing capability
and ICP-Brasil SAN CNPJ. It does NOT validate ICP-Brasil trust chains/revocation,
proof of representation, provider credentialing or authorization to issue NF-e.
No secret is logged, returned, cached, or persisted here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Final

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import ObjectIdentifier

from kordena_fiscal.domain.identifiers import Cnpj

_CNPJ_OTHER_NAME: Final = ObjectIdentifier("2.16.76.1.3.3")
_MAX_PKCS12_BYTES: Final = 2 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class A1CertificatePreflight:
    """Non-sensitive evidence only; never carries PFX, password, or private key."""

    certificate_fingerprint_sha256: str
    expires_at: datetime
    issuer_cnpj: str


def _icp_cnpj(other_name: bytes) -> str | None:
    """Unwrap at most two DER string/OCTET layers without heuristic CNPJ extraction."""
    current = other_name
    for _ in range(3):
        if len(current) == 14 and current.isascii():
            candidate = current.decode("ascii")
            return candidate if candidate.isdigit() else None
        if len(current) < 2 or current[0] not in (0x04, 0x0C, 0x13, 0x16):
            return None
        marker = current[1]
        start = 2
        if marker & 0x80:
            count = marker & 0x7F
            if count not in (1, 2) or len(current) < 2 + count:
                return None
            size = int.from_bytes(current[2:2 + count], "big")
            start += count
        else:
            size = marker
        if size != len(current) - start:
            return None
        current = current[start:]
    return None


def validate_a1_for_issuer(
    pkcs12_bytes: bytes,
    password: bytes | None,
    *,
    issuer_cnpj: Cnpj,
    at: datetime,
) -> A1CertificatePreflight:
    """Reject untrusted/mismatched A1 before an authorized vault provision operation.

    This performs structural and issuer checks, not PKI trust/revocation checks.
    """
    from kordena_fiscal.signing.contracts import InvalidCertificateMaterialError
    if (
        not isinstance(pkcs12_bytes, bytes)
        or not pkcs12_bytes
        or len(pkcs12_bytes) > _MAX_PKCS12_BYTES
        or (password is not None and not isinstance(password, bytes))
        or not isinstance(issuer_cnpj, Cnpj)
        or not isinstance(at, datetime)
        or at.tzinfo is None
        or at.utcoffset() is None
    ):
        raise InvalidCertificateMaterialError("A1 preflight input is invalid")
    try:
        key, certificate, _ = pkcs12.load_key_and_certificates(pkcs12_bytes, password)
    except (ValueError, TypeError):
        raise InvalidCertificateMaterialError("A1 certificate material is invalid") from None
    if key is None or certificate is None:
        raise InvalidCertificateMaterialError("A1 signing identity is incomplete")
    if not isinstance(key, (rsa.RSAPrivateKey, ec.EllipticCurvePrivateKey)):
        raise InvalidCertificateMaterialError("A1 signing key algorithm is unsupported")
    try:
        public_from_private = key.public_key().public_bytes(
            serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
        )
        public_from_cert = certificate.public_key().public_bytes(
            serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
        )
        if public_from_private != public_from_cert:
            raise InvalidCertificateMaterialError("A1 signing key does not match certificate")
        if not certificate.not_valid_before_utc <= at < certificate.not_valid_after_utc:
            raise InvalidCertificateMaterialError("A1 certificate is outside validity period")
        usage = certificate.extensions.get_extension_for_class(x509.KeyUsage).value
        if not (usage.digital_signature or usage.content_commitment):
            raise InvalidCertificateMaterialError("A1 certificate does not permit signing")
        san = certificate.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    except x509.ExtensionNotFound:
        raise InvalidCertificateMaterialError(
            "A1 certificate lacks issuer identity or usage"
        ) from None
    except InvalidCertificateMaterialError:
        raise
    except (TypeError, ValueError, AttributeError):
        raise InvalidCertificateMaterialError("A1 certificate metadata is invalid") from None

    cnps = [
        _icp_cnpj(name.value)
        for name in san
        if isinstance(name, x509.OtherName) and name.type_id == _CNPJ_OTHER_NAME
    ]
    if len(cnps) != 1 or cnps[0] != issuer_cnpj.value:
        raise InvalidCertificateMaterialError("A1 certificate CNPJ does not match issuer")
    return A1CertificatePreflight(
        certificate_fingerprint_sha256=certificate.fingerprint(hashes.SHA256()).hex(),
        expires_at=certificate.not_valid_after_utc,
        issuer_cnpj=issuer_cnpj.value,
    )
