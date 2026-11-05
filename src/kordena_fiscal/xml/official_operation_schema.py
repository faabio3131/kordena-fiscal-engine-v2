"""Explicit offline lifecycle snapshot using the canonical schema authority."""
from __future__ import annotations

import hashlib
import json
from importlib.resources import files

from kordena_fiscal.xml.schema import (
    SchemaIntegrityError,
    SchemaResource,
    SchemaSet,
    XmlSchemaValidator,
)

_SNAPSHOT = "MG_LIFECYCLE_20261105"
_MANIFEST = "41a818efb4e6ba37eeead3c271957b02ac995dee14425b7809e9591c641ac718"
ROOTS = {
    "NFeConsultaProtocolo4": "nfe/consSitNFe_v4.00.xsd",
    "NFeRecepcaoEvento4": "event/envEvento_v1.00.xsd",
    "NFeInutilizacao4": "nfe/inutNFe_v4.00.xsd",
    "NFeAutorizacao4": "nfe/enviNFe_v4.00.xsd",
    "NFeStatusServico4": "nfe/consStatServ_v4.00.xsd",
    "NFeRetAutorizacao4": "nfe/consReciNFe_v4.00.xsd",
}


def load_operation_schema(service: str) -> SchemaSet:
    if service not in ROOTS:
        raise SchemaIntegrityError("Unknown official schema operation")
    directory = files("kordena_fiscal.xml").joinpath("official", _SNAPSHOT)
    try:
        raw = directory.joinpath("manifest.json").read_bytes()
        if hashlib.sha256(raw).hexdigest() != _MANIFEST:
            raise SchemaIntegrityError("Lifecycle manifest digest mismatch")
        data = json.loads(raw)
        resources = tuple(
            SchemaResource(
                name=item["name"], sha256=item["sha256"],
                content=directory.joinpath(*item["name"].split("/")).read_bytes(),
            )
            for item in data["resources"]
        )
        return SchemaSet(
            version=_SNAPSHOT, root_schema=ROOTS[service], resources=resources,
            source_uri="https://www.nfe.fazenda.gov.br/portal/",
        )
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise SchemaIntegrityError("Lifecycle schema unavailable or malformed") from exc


class OfficialOperationXmlValidator:
    """Compile each selected operation once; no filesystem/network lookup during validation."""

    def __init__(self, services: tuple[str, ...]) -> None:
        self._validators = {
            service: XmlSchemaValidator(load_operation_schema(service)) for service in services
        }

    def __call__(self, service: str, xml: bytes) -> None:
        validator = self._validators.get(service)
        if validator is None:
            raise SchemaIntegrityError("Unconfigured lifecycle schema operation")
        validator.validate_document(xml)
