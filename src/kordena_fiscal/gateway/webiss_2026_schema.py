"""Municipal WebISS 2.02 RTC schema authority for MG, deliberately fail-closed.

ABRASF 2.03 is NOT a WebISS 2.02/IBSCBS compatibility schema. The official
municipal WebISS RTC package must be captured verbatim, SHA-256 pinned in this
repository, code-reviewed and tested before municipal XML can be transmitted.
Never download or trust tenant-supplied XSDs on the fiscal execution path.

Authoritative municipal announcement:
https://extremamg.webiss.com.br/ (Manuais -> Nota Fiscal de Servicos Eletronica)
Independent implementation evidence:
https://documentacao.senior.com.br/documentoseletronicos/notasdaversao/5-8-16/
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from kordena_fiscal.domain import FiscalValidationError
from kordena_fiscal.xml.schema import (
    SchemaResource,
    SchemaSet,
    XmlSchemaValidationError,
    XmlSchemaValidator,
)

WEBISS_RTC_LAYOUT_VERSION = "2.02"
WEBISS_MG_IBGE = frozenset({"3125101", "3170107"})

# No municipal XSD has yet been obtained from the official WebISS 2026 portal.
# Do not fill this map with the ABRASF 2.03 package, copied XSDs, a guessed
# IBSCBS extension or a third-party integration template. A non-empty pin
# requires the municipality-specific original, reviewed code and golden tests.
PINNED_WEBISS_MG_2026_SCHEMA_DIGESTS: Mapping[str, str] = {}


class WebissMunicipalSchemaUnverified(FiscalValidationError):
    """Municipal 2026 schema not certified; network access must be denied."""


@dataclass(frozen=True, slots=True)
class Webiss2026SchemaEvidence:
    municipality_ibge: str
    schema_package_sha256: str
    schema_version: str = WEBISS_RTC_LAYOUT_VERSION

    def __post_init__(self) -> None:
        if self.municipality_ibge not in WEBISS_MG_IBGE:
            raise WebissMunicipalSchemaUnverified("Unsupported WebISS MG municipality")
        if self.schema_version != WEBISS_RTC_LAYOUT_VERSION:
            raise WebissMunicipalSchemaUnverified(
                "WebISS MG requires the municipal RTC 2.02 schema, not ABRASF 2.03"
            )
        digest = PINNED_WEBISS_MG_2026_SCHEMA_DIGESTS.get(self.municipality_ibge)
        if digest is None or self.schema_package_sha256 != digest:
            raise WebissMunicipalSchemaUnverified(
                "Official WebISS RTC 2026 XSD package is not pinned and certified"
            )


def validate_webiss_official_xml(
    *,
    evidence: Webiss2026SchemaEvidence,
    validator: XmlSchemaValidator,
    xml: bytes,
) -> None:
    """Enforce the exact municipality-reviewed XSD over each SOAP inner payload."""
    if not isinstance(evidence, Webiss2026SchemaEvidence):
        raise WebissMunicipalSchemaUnverified("Missing official municipal schema evidence")
    if not isinstance(validator, XmlSchemaValidator):
        raise WebissMunicipalSchemaUnverified("Missing pinned municipal XSD validator")
    try:
        checked = validator.validate_document(xml)
    except XmlSchemaValidationError as exc:
        raise WebissMunicipalSchemaUnverified(
            "WebISS 2026 XML is incompatible with the pinned municipal schema"
        ) from exc
    if checked.schema_package_sha256 != evidence.schema_package_sha256:
        raise WebissMunicipalSchemaUnverified(
            "WebISS municipal schema package hash mismatch"
        )

def build_pinned_webiss_municipal_schema(
    *,
    municipality_ibge: str,
    root_schema: str,
    resources: tuple[SchemaResource, ...],
    source_uri: str,
) -> tuple[Webiss2026SchemaEvidence, XmlSchemaValidator]:
    """Load a reviewed WebISS RTC package, offline and matched by SHA-256.

    The XSD/manifest must be reviewed and version-controlled before runtime.
    No host/network, tenant upload or dynamic fetch is permitted here. An
    unknown or unpinned municipal package always fails closed.
    """
    if municipality_ibge not in WEBISS_MG_IBGE:
        raise WebissMunicipalSchemaUnverified("Unknown municipal schema jurisdiction")
    official_hosts = {
        "3125101": "https://extremamg.webiss.com.br/",
        "3170107": "https://uberabamg.webiss.com.br/",
    }
    if source_uri != official_hosts[municipality_ibge]:
        raise WebissMunicipalSchemaUnverified(
            "WebISS XSD provenance must match its municipal official portal"
        )
    expected_digest = PINNED_WEBISS_MG_2026_SCHEMA_DIGESTS.get(municipality_ibge)
    if expected_digest is None:
        raise WebissMunicipalSchemaUnverified(
            "Official WebISS RTC 2026 XSD package is not yet verified"
        )
    schema_set = SchemaSet(
        version=WEBISS_RTC_LAYOUT_VERSION,
        root_schema=root_schema,
        resources=resources,
        source_uri=source_uri,
    )
    if schema_set.package_sha256 != expected_digest:
        raise WebissMunicipalSchemaUnverified(
            "Municipal schema package differs from reviewed SHA-256"
        )
    validator = XmlSchemaValidator(schema_set)
    return (
        Webiss2026SchemaEvidence(municipality_ibge, expected_digest),
        validator,
    )
