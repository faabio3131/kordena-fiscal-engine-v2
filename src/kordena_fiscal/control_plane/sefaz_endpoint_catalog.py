"""Pinned SEFAZ endpoint discovery for the priority UFs.

Discovery is separate from provider binding and transmission approval.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from urllib.parse import urlsplit

from kordena_fiscal.domain import (
    BrazilianJurisdiction,
    FiscalDocumentKind,
    FiscalEnvironment,
    FiscalValidationError,
)

from ._sefaz_endpoint_data import ENDPOINT_GROUPS, SOURCE_URLS

_UF_BY_IBGE = {"31": "MG", "33": "RJ", "35": "SP", "41": "PR", "50": "MS", "51": "MT"}


class SefazService(StrEnum):
    AUTHORIZE = "authorize"
    RECEIPT = "receipt"
    QUERY = "query"
    CANCEL = "cancel"
    INUTILIZE = "inutilize"
    STATUS = "status"


@dataclass(frozen=True, slots=True)
class SefazEndpoint:
    uf: str
    authorizer: str
    document_kind: FiscalDocumentKind
    environment: FiscalEnvironment
    service: SefazService
    url: str
    source_url: str
    protocol_version: str = "4.00"


def _index_endpoints() -> MappingProxyType[
    tuple[str, FiscalDocumentKind, FiscalEnvironment, SefazService], SefazEndpoint
]:
    routes = {}
    for uf, kind, environment, authorizer, source, urls in ENDPOINT_GROUPS:
        document_kind = FiscalDocumentKind(kind)
        fiscal_environment = FiscalEnvironment(environment)
        for operation, url in urls.items():
            service = SefazService(operation)
            parts = urlsplit(url)
            if (
                parts.scheme != "https" or not parts.hostname or not parts.path
                or parts.username is not None or parts.password is not None
                or parts.port not in (None, 443) or parts.query or parts.fragment
            ):
                raise ValueError("Invalid pinned SEFAZ URL")
            key = uf, document_kind, fiscal_environment, service
            if key in routes:
                raise ValueError("Duplicate pinned SEFAZ route")
            routes[key] = SefazEndpoint(
                uf, authorizer, document_kind, fiscal_environment, service, url,
                SOURCE_URLS[source],
            )
    return MappingProxyType(routes)


_ROUTES = _index_endpoints()


def resolve_sefaz_endpoint(
    *,
    state_ibge_code: str,
    document_kind: FiscalDocumentKind,
    environment: FiscalEnvironment,
    service: SefazService,
    jurisdiction: BrazilianJurisdiction | None = None,
) -> SefazEndpoint:
    """Resolve a published state endpoint without granting execution authority."""
    uf = _UF_BY_IBGE.get(state_ibge_code)
    if (
        uf is None or not isinstance(document_kind, FiscalDocumentKind)
        or not isinstance(environment, FiscalEnvironment) or not isinstance(service, SefazService)
    ):
        raise FiscalValidationError("Unsupported SEFAZ route coordinates")
    if jurisdiction is not None:
        if not isinstance(jurisdiction, BrazilianJurisdiction):
            raise FiscalValidationError("Invalid fiscal jurisdiction")
        municipality = jurisdiction.municipality_ibge_code
        if jurisdiction.state_code != uf or (
            municipality is not None
            and (not municipality.isascii() or not municipality.startswith(state_ibge_code))
        ):
            raise FiscalValidationError("SEFAZ route disagrees with fiscal jurisdiction")
    route = _ROUTES.get((uf, document_kind, environment, service))
    if route is None:
        raise FiscalValidationError("No published SEFAZ route for these coordinates")
    return route
