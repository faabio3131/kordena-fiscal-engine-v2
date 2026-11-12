"""Offline National cancel/replacement event XML and signature regression."""
from __future__ import annotations

import base64
import gzip
import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import BestAvailableEncryption, pkcs12
from cryptography.x509.oid import NameOID
from lxml import etree

from kordena_fiscal.domain import ExecutionScope, FiscalEnvironment, FiscalValidationError
from kordena_fiscal.gateway.nfse_national_event_envelope import build_national_event_post_body
from kordena_fiscal.issuance.nfse_national_events import (
    NationalEventIntent,
    NationalEventType,
    build_national_event_intent_xml,
    build_signed_national_event,
)
from kordena_fiscal.vault import EphemeralCertificateMaterial
from kordena_fiscal.xml.nfse_nacional_schema import national_event_validator

_NS = "http://www.sped.fazenda.gov.br/nfse"
_DS = "http://www.w3.org/2000/09/xmldsig#"
_CNPJ = "11222333000181"
_KEY = "3106200" + "2" + "1" + _CNPJ + "1" * 27
_OTHER_KEY = "3106200" + "2" + "1" + _CNPJ + "2" * 27


def _intent(kind: NationalEventType = NationalEventType.CANCEL) -> NationalEventIntent:
    return NationalEventIntent(
        scope=ExecutionScope(
            "tenant-bh", "unit-bh", FiscalEnvironment.HOMOLOGATION,
            "corr-national-event", "fm-nfcore",
        ),
        issuer_cnpj=_CNPJ,
        access_key=_KEY,
        kind=kind,
        reason_code="1" if kind is NationalEventType.CANCEL else "99",
        reason_text="Servico sintetico nao realizado; pedido de auditoria.",
        occurred_at=datetime(2026, 11, 12, 12, 0, tzinfo=UTC),
        replacement_access_key=(
            None if kind is NationalEventType.CANCEL else _OTHER_KEY
        ),
    )


def _material() -> EphemeralCertificateMaterial:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Synthetic National Event")])
    now = datetime.now(UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name).issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=30))
        .sign(key, hashes.SHA256())
    )
    p12 = pkcs12.serialize_key_and_certificates(
        b"synthetic-event", key, cert, None,
        BestAvailableEncryption(b"synthetic-only"),
    )
    return EphemeralCertificateMaterial(
        reference_id="ref:synthetic-national-event",
        pkcs12_bytes=p12, password=b"synthetic-only",
    )


@pytest.mark.parametrize("kind", [
    NationalEventType.CANCEL, NationalEventType.CANCEL_BY_REPLACEMENT,
])
def test_national_event_signed_and_schema_valid_without_network(kind: NationalEventType) -> None:
    intent = _intent(kind)
    unsigned = build_national_event_intent_xml(intent)
    national_event_validator().validate_document(unsigned)
    signed = build_signed_national_event(intent, _material())
    national_event_validator().validate_document(signed)
    root = etree.fromstring(signed)
    assert root.tag == f"{{{_NS}}}pedRegEvento"
    assert root.get("versao") == "1.01"
    info = root.find(f"{{{_NS}}}infPedReg")
    assert info is not None
    assert info.get("Id") == "PRE" + _KEY + kind.value
    assert len(info.get("Id")) == 59
    assert info.findtext(f"{{{_NS}}}chNFSe") == _KEY
    assert info.findtext(f"{{{_NS}}}CNPJAutor") == _CNPJ
    if kind is NationalEventType.CANCEL:
        event = info.find(f"{{{_NS}}}e101101")
        assert event is not None
        assert event.findtext(f"{{{_NS}}}cMotivo") == "1"
        assert event.find(f"{{{_NS}}}chSubstituta") is None
    else:
        event = info.find(f"{{{_NS}}}e105102")
        assert event is not None
        assert event.findtext(f"{{{_NS}}}chSubstituta") == _OTHER_KEY
        assert event.findtext(f"{{{_NS}}}cMotivo") == "99"
    signature = root.find(f"{{{_DS}}}Signature")
    assert signature is not None
    assert signature.find(
        f".//{{{_DS}}}Reference"
    ).get("URI") == "#" + intent.event_request_id


@pytest.mark.parametrize("invalid_reason", ["", "curto", "X" * 256])
def test_national_cancellation_rejects_unreviewed_reason(invalid_reason: str) -> None:
    with pytest.raises(FiscalValidationError, match="15-255"):
        replace(_intent(), reason_text=invalid_reason)


def test_national_event_rejects_other_issuer_access_key() -> None:
    foreign = "3106200" + "2" + "1" + "12345678000195" + "0" * 27
    with pytest.raises(FiscalValidationError, match="disagree"):
        replace(_intent(), access_key=foreign)


def test_national_event_rejects_different_replacement_issuer_and_self_reference() -> None:
    intent = _intent(NationalEventType.CANCEL_BY_REPLACEMENT)
    with pytest.raises(FiscalValidationError, match="same-issuer"):
        replace(intent, replacement_access_key=(
            "3106200" + "2" + "1" + "12345678000195" + "0" * 27
        ))
    with pytest.raises(FiscalValidationError, match="original invoice"):
        replace(intent, replacement_access_key=intent.access_key)


def test_national_cancellation_does_not_accept_replacement_or_unapproved_codes() -> None:
    with pytest.raises(FiscalValidationError, match="cannot carry"):
        replace(_intent(), replacement_access_key=_OTHER_KEY)
    with pytest.raises(FiscalValidationError, match="Unapproved national cancellation"):
        replace(_intent(), reason_code="3")
    with pytest.raises(FiscalValidationError, match="replacement reason"):
        replace(_intent(NationalEventType.CANCEL_BY_REPLACEMENT), reason_code="1")


def test_national_event_rejects_production_scope_and_naive_clock() -> None:
    intent = _intent()
    with pytest.raises(FiscalValidationError, match="homologation"):
        replace(intent, scope=replace(
            intent.scope, environment=FiscalEnvironment.PRODUCTION,
        ))
    with pytest.raises(FiscalValidationError, match="timezone aware"):
        replace(intent, occurred_at=datetime(2026, 11, 12, 12, 0))


@pytest.mark.parametrize("kind", [
    NationalEventType.CANCEL, NationalEventType.CANCEL_BY_REPLACEMENT,
])
def test_national_event_transport_message_is_signed_compressed_and_unsent(
    kind: NationalEventType,
) -> None:
    intent = _intent(kind)
    body = json.loads(build_national_event_post_body(intent, _material()))
    assert set(body) == {"pedidoRegistroEventoXmlGZipB64"}
    signed = gzip.decompress(base64.b64decode(body["pedidoRegistroEventoXmlGZipB64"]))
    national_event_validator().validate_document(signed)
    root = etree.fromstring(signed)
    assert root.find(f"{{{_NS}}}infPedReg").get("Id") == intent.event_request_id
    assert root.find(f"{{{_DS}}}Signature") is not None
