"""Exact endpoint discovery and isolation from provider selection."""
from urllib.parse import urlsplit

import pytest

from kordena_fiscal.control_plane.sefaz_endpoint_catalog import SefazService, resolve_sefaz_endpoint
from kordena_fiscal.domain import (
    BrazilianJurisdiction,
    FiscalDocumentKind,
    FiscalEnvironment,
    FiscalValidationError,
)


@pytest.mark.parametrize("ibge,uf,authorizer,city", [
    ("35", "SP", "SP", "3550308"), ("31", "MG", "MG", "3106200"),
    ("33", "RJ", "SVRS", "3304557"), ("41", "PR", "PR", "4106902"),
    ("51", "MT", "MT", "5103403"), ("50", "MS", "MS", "5002704"),
])
@pytest.mark.parametrize("family", [FiscalDocumentKind.NFE, FiscalDocumentKind.NFCE])
def test_complete_priority_matrix_is_exact(ibge, uf, authorizer, city, family):
    for service in SefazService:
        endpoints = [
            resolve_sefaz_endpoint(
                state_ibge_code=ibge, document_kind=family, environment=environment,
                service=service, jurisdiction=BrazilianJurisdiction(uf, city),
            )
            for environment in FiscalEnvironment
        ]
        assert endpoints[0].url != endpoints[1].url
        for endpoint, environment in zip(endpoints, FiscalEnvironment, strict=True):
            assert (endpoint.uf, endpoint.authorizer) == (uf, authorizer)
            assert endpoint.protocol_version == "4.00"
            assert (endpoint.document_kind, endpoint.environment, endpoint.service) == (
                family, environment, service,
            )
            assert urlsplit(endpoint.url).scheme == "https"


@pytest.mark.parametrize("ibge,kind,jurisdiction", [
    ("33", FiscalDocumentKind.NFE, BrazilianJurisdiction("SP", "3550308")),
    ("33", FiscalDocumentKind.NFE, BrazilianJurisdiction("RJ", "3550308")),
    ("33", FiscalDocumentKind.NFSE, BrazilianJurisdiction("RJ", "3304557")),
    ("43", FiscalDocumentKind.NFE, None),
    ("3304557", FiscalDocumentKind.NFE, None),
])
def test_invalid_coordinates_do_not_fallback(ibge, kind, jurisdiction):
    with pytest.raises(FiscalValidationError):
        resolve_sefaz_endpoint(
            state_ibge_code=ibge, document_kind=kind, environment=FiscalEnvironment.HOMOLOGATION,
            service=SefazService.AUTHORIZE, jurisdiction=jurisdiction,
        )


@pytest.mark.parametrize("ibge,family,service,tail", [
    ("33", FiscalDocumentKind.NFE, SefazService.QUERY, "/ws/NfeConsulta/NfeConsulta4.asmx"),
    ("51", FiscalDocumentKind.NFCE, SefazService.CANCEL, "/nfcews/services/RecepcaoEvento4"),
    ("35", FiscalDocumentKind.NFE, SefazService.RECEIPT, "/ws/nferetautorizacao4.asmx"),
    ("50", FiscalDocumentKind.NFCE, SefazService.RECEIPT, "/ws/NFeRetAutorizacao4"),
])
def test_service_paths_retain_authorizer_specific_spelling(ibge, family, service, tail):
    route = resolve_sefaz_endpoint(
        state_ibge_code=ibge, document_kind=family, environment=FiscalEnvironment.HOMOLOGATION,
        service=service,
    )
    assert urlsplit(route.url).path == tail
