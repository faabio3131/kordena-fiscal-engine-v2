"""Pinned official NFe subtree; offline validation reuses the canonical validator.

This package snapshot is NOT a jurisdiction/RTC readiness or homologation approval.
"""
from __future__ import annotations

import hashlib
import json
from importlib.resources import files

from lxml import etree

from kordena_fiscal.xml.access_key import NfeAccessKey
from kordena_fiscal.xml.schema import (
    NfceXmlPayload,
    SchemaIntegrityError,
    SchemaResource,
    SchemaSet,
    XmlSchemaValidationError,
    XmlSchemaValidator,
)

_PACKAGE = "PL_010g_v1.03"
_MANIFEST_SHA256 = "0f0f1a74282c5edee5076a1221fb5172aeea1067183de798eca1b0b8a17690d6"
_NS = "http://www.portalfiscal.inf.br/nfe"


def load_official_nfe_schema() -> SchemaSet:
    """Load locally packaged resources; every byte is pinned, no remote fallback."""
    directory = files("kordena_fiscal.xml").joinpath("official", _PACKAGE)
    try:
        raw = directory.joinpath("manifest.json").read_bytes()
        if hashlib.sha256(raw).hexdigest() != _MANIFEST_SHA256:
            raise SchemaIntegrityError("Official NFe manifest digest mismatch")
        manifest = json.loads(raw)
        resources = tuple(
            SchemaResource(
                name=item["name"],
                content=directory.joinpath(item["name"]).read_bytes(),
                sha256=item["sha256"],
            )
            for item in manifest["resources"]
        )
        return SchemaSet(
            version=manifest["package_id"], root_schema=manifest["root_schema"],
            resources=resources, source_uri=manifest["source_url"],
        )
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise SchemaIntegrityError("Official NFe package unavailable or malformed") from exc


class OfficialNfeEnvelopeValidator:
    """Validate a signed single-invoice envelope using existing NFe XSD authority."""

    def __init__(self) -> None:
        self._validator = XmlSchemaValidator(load_official_nfe_schema())

    def __call__(self, xml: bytes) -> None:
        if not xml or len(xml) > 2_097_152 or b"<!DOCTYPE" in xml.upper():
            raise XmlSchemaValidationError("Invalid NFe envelope")
        try:
            root = etree.fromstring(xml, parser=etree.XMLParser(
                resolve_entities=False, load_dtd=False, no_network=True, huge_tree=False,
            ))
        except etree.XMLSyntaxError:
            raise XmlSchemaValidationError("Invalid NFe envelope XML") from None
        invoices = root.findall(f"{{{_NS}}}NFe")
        if root.tag != f"{{{_NS}}}enviNFe" or root.get("versao") != "4.00":
            raise XmlSchemaValidationError("NFe envelope version mismatch")
        if len(invoices) != 1:
            raise XmlSchemaValidationError("NFe envelope requires one invoice")
        info = invoices[0].find(f"{{{_NS}}}infNFe")
        identifier = info.get("Id", "") if info is not None else ""
        if not identifier.startswith("NFe"):
            raise XmlSchemaValidationError("NFe invoice identity missing")
        self._validator.validate(NfceXmlPayload(
            access_key=NfeAccessKey(identifier[3:]),
            xml=etree.tostring(invoices[0], encoding="utf-8"),
        ))
