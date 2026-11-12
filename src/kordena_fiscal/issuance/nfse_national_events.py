"""Pinned National NFS-e event intents; offline signing only.

A signed event is NOT authorization, cancellation or an instruction to send.
Transmitters must use a separate durable request and the official endpoint
with idempotency, timeout quarantine and authoritative event reconciliation.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum

from cryptography import x509
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from lxml import etree

from kordena_fiscal.domain import ExecutionScope, FiscalEnvironment, FiscalValidationError
from kordena_fiscal.signing.nfse_xmldsig import append_nfse_signature
from kordena_fiscal.vault import EphemeralCertificateMaterial
from kordena_fiscal.xml.nfse_nacional_schema import national_event_validator

_NS = "http://www.sped.fazenda.gov.br/nfse"
_DS = "http://www.w3.org/2000/09/xmldsig#"
_VERSION = "1.01"
_APP = "nfcore-ev-v1"
_MAX_BYTES = 2_097_152


class NationalEventType(str, Enum):
    CANCEL = "101101"
    CANCEL_BY_REPLACEMENT = "105102"


def _valid_access_key(key: str, issuer_cnpj: str) -> bool:
    return (
        isinstance(key, str)
        and len(key) == 50
        and key.isascii()
        and key.isdecimal()
        and key[9:23] == issuer_cnpj
    )


@dataclass(frozen=True, slots=True)
class NationalEventIntent:
    scope: ExecutionScope
    issuer_cnpj: str
    access_key: str
    kind: NationalEventType
    reason_code: str
    reason_text: str
    occurred_at: datetime
    replacement_access_key: str | None = None

    def __post_init__(self) -> None:
        if (
            not isinstance(self.scope, ExecutionScope)
            or self.scope.environment is not FiscalEnvironment.HOMOLOGATION
            or not self.scope.host_namespace
        ):
            raise FiscalValidationError("National event requires exact homologation host scope")
        if (
            not isinstance(self.issuer_cnpj, str)
            or len(self.issuer_cnpj) != 14
            or not self.issuer_cnpj.isascii()
            or not self.issuer_cnpj.isdecimal()
            or not _valid_access_key(self.access_key, self.issuer_cnpj)
        ):
            raise FiscalValidationError("National event invoice key and issuer CNPJ disagree")
        if not isinstance(self.kind, NationalEventType):
            raise FiscalValidationError("Unsupported National NFS-e event kind")
        if self.kind is NationalEventType.CANCEL:
            if self.reason_code not in {"1", "2", "9"}:
                raise FiscalValidationError("Unapproved national cancellation code")
            if self.replacement_access_key is not None:
                raise FiscalValidationError("Cancellation cannot carry a replacement invoice")
        else:
            if self.reason_code not in {"01", "02", "03", "04", "05", "99"}:
                raise FiscalValidationError("Unapproved national replacement reason")
            if not _valid_access_key(self.replacement_access_key, self.issuer_cnpj):
                raise FiscalValidationError("Replacement event requires same-issuer invoice key")
            if self.replacement_access_key == self.access_key:
                raise FiscalValidationError("Replacement cannot reference the original invoice")
        if (
            not isinstance(self.reason_text, str)
            or not 15 <= len(self.reason_text.strip()) <= 255
        ):
            raise FiscalValidationError("National event reason must be 15-255 characters")
        if (
            not isinstance(self.occurred_at, datetime)
            or self.occurred_at.tzinfo is None
            or self.occurred_at.utcoffset() is None
        ):
            raise FiscalValidationError("National event timestamp must be timezone aware")

    @property
    def event_request_id(self) -> str:
        return "PRE" + self.access_key + self.kind.value


def _child(parent: etree._Element, name: str, value: str) -> etree._Element:
    node = etree.SubElement(parent, f"{{{_NS}}}{name}")
    node.text = value
    return node


def build_national_event_intent_xml(intent: NationalEventIntent) -> bytes:
    """Build and XSD-validate an unsigned fiscal intent, without transport."""
    if not isinstance(intent, NationalEventIntent):
        raise FiscalValidationError("National event requires reviewed intent")
    root = etree.Element(f"{{{_NS}}}pedRegEvento", nsmap={None: _NS})  # type: ignore[dict-item]
    root.set("versao", _VERSION)
    info = etree.SubElement(root, f"{{{_NS}}}infPedReg", Id=intent.event_request_id)
    _child(info, "tpAmb", "2")
    _child(info, "verAplic", _APP)
    _child(info, "dhEvento", intent.occurred_at.astimezone(UTC).strftime(
        "%Y-%m-%dT%H:%M:%S+00:00",
    ))
    _child(info, "CNPJAutor", intent.issuer_cnpj)
    _child(info, "chNFSe", intent.access_key)
    if intent.kind is NationalEventType.CANCEL:
        event = etree.SubElement(info, f"{{{_NS}}}e101101")
        _child(event, "xDesc", "Cancelamento de NFS-e")
    else:
        event = etree.SubElement(info, f"{{{_NS}}}e105102")
        _child(event, "xDesc", "Cancelamento de NFS-e por Substituição")
    _child(event, "cMotivo", intent.reason_code)
    _child(event, "xMotivo", intent.reason_text.strip())
    if intent.replacement_access_key is not None:
        _child(event, "chSubstituta", intent.replacement_access_key)
    xml = etree.tostring(root, encoding="utf-8", xml_declaration=False)
    if len(xml) > _MAX_BYTES:
        raise FiscalValidationError("National event XML exceeds limit")
    national_event_validator().validate_document(xml)
    return xml


def build_signed_national_event(
    intent: NationalEventIntent, certificate_material: EphemeralCertificateMaterial,
) -> bytes:
    """Sign only the reviewed infPedReg node and revalidate entire XMLDSig."""
    unsigned = build_national_event_intent_xml(intent)
    if not isinstance(certificate_material, EphemeralCertificateMaterial):
        raise FiscalValidationError("National event requires a trusted A1 material")
    key, cert, _ = pkcs12.load_key_and_certificates(
        certificate_material.pkcs12_bytes, certificate_material.password,
    )
    if not isinstance(key, rsa.RSAPrivateKey) or not isinstance(cert, x509.Certificate):
        raise FiscalValidationError("National event requires an RSA A1 identity")
    parser = etree.XMLParser(resolve_entities=False, no_network=True)
    root = etree.fromstring(unsigned, parser=parser)
    info = root.find(f"{{{_NS}}}infPedReg")
    if info is None or root.find(f"{{{_DS}}}Signature") is not None:
        raise FiscalValidationError("National event XML has invalid signature state")
    append_nfse_signature(root, info, key, cert, legacy_abrasf=True)
    signed = etree.tostring(root, encoding="utf-8", xml_declaration=True)
    national_event_validator().validate_document(signed)
    return signed
