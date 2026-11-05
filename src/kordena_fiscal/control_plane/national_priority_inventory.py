"""Read-only, non-authoritative priority-state fiscal capability inventory.

NAT-01: sources and pilot municipalities are discovery metadata, NEVER routing
permissions, readiness flags, provider bindings, issuance credentials or approvals.
The existing DurableProviderBindingResolver remains the single provider authority.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from urllib.parse import urlsplit

from kordena_fiscal.domain import (
    BrazilianJurisdiction,
    FiscalDocumentKind,
    FiscalValidationError,
)

_IBGE_UF_PREFIX: dict[str, str] = {
    "MG": "31", "RJ": "33", "PR": "41", "MT": "51", "MS": "50",
}


class NfseIssuerChannel(StrEnum):
    """Research classification, never a provider configuration or availability."""

    NATIONAL = "national"
    MUNICIPAL_HYBRID_REVIEW = "municipal_hybrid_review"


class IntegrationEvidence(StrEnum):
    """Conservative catalog states; never imply actual fiscal availability."""

    RESEARCH_REQUIRED = "research_required"
    OFFICIAL_CONTRACT_IDENTIFIED = "official_contract_identified"


@dataclass(frozen=True, slots=True)
class PriorityStatePilot:
    uf: str
    municipality: str
    municipality_ibge: str
    nfe_authorizer: str
    nfe_source: str
    nfce_source: str
    nfse_source: str
    nfse_channel: NfseIssuerChannel
    nfse_evidence: IntegrationEvidence = IntegrationEvidence.RESEARCH_REQUIRED

    def __post_init__(self) -> None:
        if self.uf not in _IBGE_UF_PREFIX:
            raise FiscalValidationError("UF not in approved NAT priority scope")
        if not self.municipality.strip():
            raise FiscalValidationError("Pilot city is required")
        if not self.municipality_ibge.startswith(_IBGE_UF_PREFIX[self.uf]):
            raise FiscalValidationError("Pilot municipality IBGE disagrees with UF")
        BrazilianJurisdiction(self.uf, self.municipality_ibge)
        if not isinstance(self.nfse_channel, NfseIssuerChannel):
            raise FiscalValidationError("Unknown NFS-e issuer channel")
        if self.nfe_authorizer not in {"SEFAZ_UF", "SVRS"}:
            raise FiscalValidationError("Authorizer family not recognized")
        for source in (self.nfe_source, self.nfce_source, self.nfse_source):
            url = urlsplit(source)
            if url.scheme != "https" or not url.hostname or url.username or url.password:
                raise FiscalValidationError("Official source must be a public HTTPS URL")

    def source_for(self, kind: FiscalDocumentKind) -> str:
        return {
            FiscalDocumentKind.NFE: self.nfe_source,
            FiscalDocumentKind.NFCE: self.nfce_source,
            FiscalDocumentKind.NFSE: self.nfse_source,
        }[kind]


# These official PUBLIC DOCUMENTATION links are provenance only, NOT endpoints.
# No transport may consume a URL from this inventory for an HTTP call.
NAT_PRIORITY_PILOTS: tuple[PriorityStatePilot, ...] = (
    PriorityStatePilot(
        uf="MG", municipality="Belo Horizonte", municipality_ibge="3106200",
        nfe_authorizer="SEFAZ_UF",
        nfe_source="https://portalsped.fazenda.mg.gov.br/spedmg/nfe/webservices/",
        nfce_source="https://portalsped.fazenda.mg.gov.br/spedmg/nfce/web-services/",
        nfse_source="https://prefeitura.pbh.gov.br/fazenda/bhiss/avisos",
        nfse_channel=NfseIssuerChannel.NATIONAL,
    ),
    PriorityStatePilot(
        uf="RJ", municipality="Rio de Janeiro", municipality_ibge="3304557",
        nfe_authorizer="SVRS",
        nfe_source="https://www.nfe.fazenda.gov.br/portal/webServices.aspx",
        nfce_source="https://www.nfe.fazenda.gov.br/portal/webServices.aspx",
        nfse_source="https://fazenda.prefeitura.rio/noticias/emissao-do-iss-na-prefeitura-do-rio-tera-mudanca-a-partir-de-1o-de-janeiro-de-2026/",
        nfse_channel=NfseIssuerChannel.NATIONAL,
    ),
    PriorityStatePilot(
        uf="PR", municipality="Curitiba", municipality_ibge="4106902",
        nfe_authorizer="SEFAZ_UF",
        nfe_source="https://sped.fazenda.pr.gov.br/NFe/Pagina/Servicos-web-services-disponiveis",
        nfce_source="https://sped.fazenda.pr.gov.br/NFCe/Pagina/Web-Services-NFC-e",
        nfse_source="https://lp.curitiba.pr.gov.br/notanacional/",
        nfse_channel=NfseIssuerChannel.NATIONAL,
    ),
    PriorityStatePilot(
        uf="MT", municipality="Cuiabá", municipality_ibge="5103403",
        nfe_authorizer="SEFAZ_UF",
        nfe_source="https://www.nfe.fazenda.gov.br/portal/webServices.aspx",
        nfce_source="https://www.sefaz.mt.gov.br/portal/nfce/",
        nfse_source="https://www.cuiaba.mt.gov.br/noticias/cuiaba-prorroga-prazo-para-emissao-de-nfs-e-pelo-emissor-nacional",
        nfse_channel=NfseIssuerChannel.NATIONAL,
    ),
    PriorityStatePilot(
        uf="MS", municipality="Campo Grande", municipality_ibge="5002704",
        nfe_authorizer="SEFAZ_UF",
        nfe_source="https://www.sefaz.ms.gov.br/documentos-fiscais-eletronicos/nf-e/",
        nfce_source="https://www.sefaz.ms.gov.br/documentos-fiscais-eletronicos/nfc-e/",
        nfse_source="https://www.campogrande.ms.gov.br/cgnoticias/noticia/novo-sistema-de-nota-fiscal-trara-mais-agilidade-seguranca-e-estabilidade/",
        nfse_channel=NfseIssuerChannel.MUNICIPAL_HYBRID_REVIEW,
    ),
)


def priority_pilot(uf: str) -> PriorityStatePilot:
    """Return metadata or fail closed; never select a provider implicitly."""
    for pilot in NAT_PRIORITY_PILOTS:
        if pilot.uf == uf:
            return pilot
    raise FiscalValidationError("No approved priority-state research inventory for UF")
