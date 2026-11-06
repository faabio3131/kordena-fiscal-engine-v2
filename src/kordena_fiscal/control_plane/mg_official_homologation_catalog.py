"""MG homologation endpoint contracts, read-only NAT-03 discovery input.

Never called directly from this module. Routes are not production bindings.
The canonical provider registry, durable binding, credential checks and
readiness must gate any future transport activation.
"""
from __future__ import annotations

from dataclasses import dataclass

from kordena_fiscal.control_plane.commercial import ConfiguredFiscalOperation
from kordena_fiscal.control_plane.sefaz_endpoint_catalog import SefazService, resolve_sefaz_endpoint
from kordena_fiscal.domain import (
    FiscalDocumentKind,
    FiscalEnvironment,
    FiscalValidationError,
)

_MG_NFE_SOURCE = "https://portalsped.fazenda.mg.gov.br/spedmg/nfe/webservices/"
_MG_NFCE_SOURCE = "https://portalsped.fazenda.mg.gov.br/spedmg/nfce/web-services/"

@dataclass(frozen=True, slots=True)
class OfficialHomologationEndpoint:
    uf: str
    document_kind: FiscalDocumentKind
    environment: FiscalEnvironment
    operation: ConfiguredFiscalOperation
    url: str
    source_url: str
    protocol_version: str = "4.00"

    def __post_init__(self) -> None:
        if self.uf != "MG" or self.document_kind not in {
            FiscalDocumentKind.NFE, FiscalDocumentKind.NFCE,
        }:
            raise FiscalValidationError("Only MG NF-e and NFC-e verified contracts belong here")
        if self.environment is not FiscalEnvironment.HOMOLOGATION:
            raise FiscalValidationError("Production endpoint activation requires a separate gate")
        if not isinstance(self.operation, ConfiguredFiscalOperation):
            raise FiscalValidationError("Unsupported fiscal endpoint operation")
        route = resolve_sefaz_endpoint(
            state_ibge_code="31",
            document_kind=self.document_kind,
            environment=self.environment,
            service=SefazService(self.operation.value),
        )
        if self.url != route.url:
            raise FiscalValidationError("MG official homologation endpoint mismatch")
        if self.protocol_version != "4.00":
            raise FiscalValidationError("MG WS protocol 4.00 required")
        if self.source_url != (
            _MG_NFE_SOURCE
            if self.document_kind is FiscalDocumentKind.NFE
            else _MG_NFCE_SOURCE
        ):
            raise FiscalValidationError("Official documentation source mismatch")


MG_HOMOLOGATION_ENDPOINTS: tuple[OfficialHomologationEndpoint, ...] = tuple(
    OfficialHomologationEndpoint(
        uf="MG",
        document_kind=kind,
        environment=FiscalEnvironment.HOMOLOGATION,
        operation=operation,
        url=resolve_sefaz_endpoint(
            state_ibge_code="31", document_kind=kind, environment=FiscalEnvironment.HOMOLOGATION,
            service=SefazService(operation.value),
        ).url,
        source_url=source,
    )
    for kind, source in (
        (FiscalDocumentKind.NFE, _MG_NFE_SOURCE),
        (FiscalDocumentKind.NFCE, _MG_NFCE_SOURCE),
    )
    for operation in ConfiguredFiscalOperation
)


def mg_homologation_endpoint(
    *,
    document_kind: FiscalDocumentKind,
    environment: FiscalEnvironment,
    operation: ConfiguredFiscalOperation,
) -> OfficialHomologationEndpoint:
    """Return verified reference or fail closed; not a transport activation."""
    found = tuple(
        item for item in MG_HOMOLOGATION_ENDPOINTS
        if (item.document_kind, item.environment, item.operation)
        == (document_kind, environment, operation)
    )
    if len(found) != 1:
        raise FiscalValidationError("Uncertified MG service cannot be selected")
    return found[0]
