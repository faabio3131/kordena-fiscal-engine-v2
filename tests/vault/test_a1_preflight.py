"""Synthetic certificates only; no user certificate material is stored."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID, ObjectIdentifier

from kordena_fiscal.domain.identifiers import Cnpj, _calculate_cnpj_dv
from kordena_fiscal.signing.contracts import InvalidCertificateMaterialError
from kordena_fiscal.vault.a1_preflight import validate_a1_for_issuer

NOW = datetime(2026, 11, 4, 15, 0, tzinfo=UTC)
ISSUER = Cnpj("11222333000181")
OTHER = Cnpj("112223330002" + _calculate_cnpj_dv("112223330002"))
PASSWORD = b"synthetic-only-password"


def _pfx(*, cnpj: str | None = ISSUER.value,
         before: timedelta = timedelta(days=-1),
         after: timedelta = timedelta(days=30),
         sign: bool = True) -> bytes:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Synthetic test entity")])
    builder = (
        x509.CertificateBuilder()
        .subject_name(name).issuer_name(name)
        .public_key(key.public_key()).serial_number(x509.random_serial_number())
        .not_valid_before(NOW + before).not_valid_after(NOW + after)
        .add_extension(
            x509.KeyUsage(
                digital_signature=sign, content_commitment=False, key_encipherment=False,
                data_encipherment=False, key_agreement=False, key_cert_sign=False,
                crl_sign=False, encipher_only=False, decipher_only=False
            ), critical=True
        )
    )
    if cnpj is not None:
        encoded = cnpj.encode("ascii")
        builder = builder.add_extension(
            x509.SubjectAlternativeName([
                x509.OtherName(ObjectIdentifier("2.16.76.1.3.3"),
                               bytes([0x04, len(encoded)]) + encoded)
            ]), critical=False
        )
    cert = builder.sign(key, hashes.SHA256())
    return pkcs12.serialize_key_and_certificates(
        name=b"test-a1", key=key, cert=cert, cas=None,
        encryption_algorithm=serialization.BestAvailableEncryption(PASSWORD),
    )


def test_valid_a1_issuer_preflight_returns_only_public_metadata() -> None:
    output = validate_a1_for_issuer(_pfx(), PASSWORD, issuer_cnpj=ISSUER, at=NOW)
    assert output.issuer_cnpj == ISSUER.value
    assert len(output.certificate_fingerprint_sha256) == 64
    assert output.expires_at > NOW
    assert "password" not in repr(output).lower()
    assert "private" not in repr(output).lower()


@pytest.mark.parametrize("kwargs", [
    {"cnpj": OTHER.value},
    {"cnpj": None},
    {"after": timedelta(seconds=-1), "before": timedelta(days=-2)},
    {"before": timedelta(days=1)},
    {"sign": False},
])
def test_invalid_issuer_identity_or_validity_is_rejected(kwargs: dict[str, object]) -> None:
    with pytest.raises(InvalidCertificateMaterialError):
        validate_a1_for_issuer(_pfx(**kwargs), PASSWORD, issuer_cnpj=ISSUER, at=NOW)


def test_wrong_password_and_invalid_pfx_are_redacted() -> None:
    for material, password in [(_pfx(), b"secret-wrong"), (b"PRIVATE-SECRET", PASSWORD)]:
        with pytest.raises(InvalidCertificateMaterialError) as error:
            validate_a1_for_issuer(material, password, issuer_cnpj=ISSUER, at=NOW)
        assert "PRIVATE-SECRET" not in str(error.value)
        assert "secret-wrong" not in str(error.value)


def test_cross_tenant_issuer_mismatch_fails_closed() -> None:
    with pytest.raises(InvalidCertificateMaterialError, match="CNPJ"):
        validate_a1_for_issuer(_pfx(), PASSWORD, issuer_cnpj=OTHER, at=NOW)


def test_naive_clock_and_oversized_payload_fail_closed() -> None:
    for payload, at in [(_pfx(), NOW.replace(tzinfo=None)), (b"x" * (2 * 1024 * 1024 + 1), NOW)]:
        with pytest.raises(InvalidCertificateMaterialError):
            validate_a1_for_issuer(payload, PASSWORD, issuer_cnpj=ISSUER, at=at)
