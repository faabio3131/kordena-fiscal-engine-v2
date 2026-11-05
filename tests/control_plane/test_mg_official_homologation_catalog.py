"""Official MG NF-e 55 / NFC-e 65 contract inventory is fail closed."""
from dataclasses import replace

import pytest

from kordena_fiscal.control_plane.commercial import ConfiguredFiscalOperation
from kordena_fiscal.control_plane.mg_official_homologation_catalog import (
    MG_HOMOLOGATION_ENDPOINTS,
    mg_homologation_endpoint,
)
from kordena_fiscal.domain import (
    FiscalDocumentKind,
    FiscalEnvironment,
    FiscalValidationError,
)


def test_all_mg_nfe_nfce_homologation_operations_have_unique_contracts() -> None:
    assert len(MG_HOMOLOGATION_ENDPOINTS) == 10
    assert {
        (entry.document_kind, entry.environment, entry.operation)
        for entry in MG_HOMOLOGATION_ENDPOINTS
    } == {
        (kind, FiscalEnvironment.HOMOLOGATION, operation)
        for kind in (FiscalDocumentKind.NFE, FiscalDocumentKind.NFCE)
        for operation in ConfiguredFiscalOperation
    }
    for entry in MG_HOMOLOGATION_ENDPOINTS:
        assert mg_homologation_endpoint(
            document_kind=entry.document_kind,
            environment=entry.environment,
            operation=entry.operation,
        ) == entry
        assert entry.url.startswith("https://hn")


def test_mg_production_and_nfse_are_not_exposed_by_discovery() -> None:
    for kind in FiscalDocumentKind:
        for environment in FiscalEnvironment:
            if kind in {FiscalDocumentKind.NFE, FiscalDocumentKind.NFCE} and (
                environment is FiscalEnvironment.HOMOLOGATION
            ):
                continue
            with pytest.raises(FiscalValidationError, match="Uncertified"):
                mg_homologation_endpoint(
                    document_kind=kind,
                    environment=environment,
                    operation=ConfiguredFiscalOperation.AUTHORIZE,
                )


def test_mg_contract_rejects_wrong_host_path_and_insecure_url() -> None:
    contract = MG_HOMOLOGATION_ENDPOINTS[0]
    for url in (
        "https://hnfe.fazenda.mg.gov.br.evil.example/nfe2/services/NFeAutorizacao4",
        "http://hnfe.fazenda.mg.gov.br/nfe2/services/NFeAutorizacao4",
        "https://hnfe.fazenda.mg.gov.br/nfe2/services/NFeAutorizacao4?key=x",
        "https://hnfe.fazenda.mg.gov.br:8443/nfe2/services/NFeAutorizacao4",
    ):
        with pytest.raises(FiscalValidationError):
            replace(contract, url=url)
    with pytest.raises(FiscalValidationError):
        replace(contract, environment=FiscalEnvironment.PRODUCTION)
    with pytest.raises(FiscalValidationError):
        replace(contract, document_kind=FiscalDocumentKind.NFSE)


def test_mg_urls_are_not_network_calls_or_provider_bindings() -> None:
    for entry in MG_HOMOLOGATION_ENDPOINTS:
        assert not hasattr(entry, "authorize")
        assert not hasattr(entry, "resolve_provider_id")
        assert not hasattr(entry, "credentials")
        assert not hasattr(entry, "tenant_id")
