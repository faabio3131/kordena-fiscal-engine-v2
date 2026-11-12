"""São Paulo NFS-e R16 routing via the EXISTING durable Control Plane authority.

The static catalog is advisory only and never authorizes provider transmission.
The canonical DurableProviderBindingResolver performs the actual exact-match
lookup by tenant, unit, environment, kind, issuer jurisdiction and operation.
No second authorization state, persistence, or fiscal gateway is introduced.

Municipal (São Paulo city) routing guard -- Simples Nacional / Emissor Nacional
--------------------------------------------------------------------------------
Official São Paulo City notice updated 13/08/2026 and Resolution CGSN
191/2026 moved the ME/EPP Simples transition from 01/09/2026 to
**01/11/2026**. The legal criterion is the SERVICE COMPETENCE DATE, not
the date of HTTP request or document issuance. Municipal legacy issuance
for retrospective competences through 31/10/2026 remains permissible
subject to the complete municipal provider contract and fiscal validation.
For competences from 01/11/2026, issuance by ME/EPP Simples must use
the National NFS-e issuer regardless of the municipality's own emitter.

This guard covers the corporate Simples classification. It does not certify
the MEI or autonomous professional channel or grant any positive provider
approval. For São Paulo city the autonomous cutoff is 03/08/2026 and
requires a separate scoped taxpayer classification, not inferred here.

Sources:
https://prefeitura.sp.gov.br/web/fazenda/w/usoemissornacional
https://www.gov.br/receitafederal/pt-br/assuntos/noticias/2026/agosto/simples-nacional-nfs-e-nacional-sera-obrigatoria-para-me-e-epp-a-partir-de-1o-de-novembro-de-2026

``ensure_municipal_sp_transport_permitted`` is a structural fail-closed guard,
not a routing decision: it does not pick a provider, does not call the
Emissor Nacional, and is not wired into any production transmission path
today (none exists yet for Nota Paulistana). Any future transport client for
the municipal webservice MUST call it before submitting, so a Simples
Nacional issuer can never be silently routed to a webservice that can no
longer accept new issuance for that regime.
"""
from __future__ import annotations

from datetime import date, datetime

from kordena_fiscal.domain import (
    BrazilianJurisdiction,
    ExecutionScope,
    FiscalDocumentKind,
)
from kordena_fiscal.gateway.provider import (
    ProviderOperation,
    ProviderSelectionResolver,
    UnsupportedProviderError,
)
from kordena_fiscal.tax.regimes import FederalIncomeTaxRegime

# 2026-08-13 updated municipal statement and CGSN Res. 191/2026.
# UTC clock is checked for execution-safety only; competence controls
# the fiscal cutoff for new issuance, including retroactive operations.
SIMPLES_NACIONAL_EMISSOR_NACIONAL_MANDATORY_FROM = date(2026, 11, 1)


class MunicipalTransportNotPermittedError(UnsupportedProviderError):
    """Raised when the legacy São Paulo webservice cannot accept new issuance."""


def ensure_municipal_sp_transport_permitted(
    federal_income_tax_regime: FederalIncomeTaxRegime,
    *,
    issuer_ibge_code: str,
    competence_date: date,
    as_of: datetime,
) -> None:
    """Block an ineligible legacy city NFS-e issue without choosing any provider.

    Fail closed on missing competence or untrusted clocks. This is a negative
    regulatory gate, not proof that municipal transport, A1, and ISS rules
    are otherwise available. Integrations MUST call it before SOAP I/O.
    """
    if (
        type(federal_income_tax_regime) is not FederalIncomeTaxRegime
        or type(competence_date) is not date
        or not isinstance(as_of, datetime)
        or as_of.tzinfo is None
        or as_of.utcoffset() is None
    ):
        raise UnsupportedProviderError(
            "SP municipal legacy requires reviewed regime, competence and timezone-aware clock"
        )
    if issuer_ibge_code != "3550308":
        return
    if (
        federal_income_tax_regime is FederalIncomeTaxRegime.SIMPLES_NACIONAL
        and competence_date >= SIMPLES_NACIONAL_EMISSOR_NACIONAL_MANDATORY_FROM
    ):
        raise MunicipalTransportNotPermittedError(
            "São Paulo city ME/EPP Simples must use National NFS-e "
            "for competences on or after 2026-11-01 (CGSN 191/2026); "
            "retroactive services before this date require reviewed municipal eligibility"
        )


# Candidate migration/UX catalog: NOT approved municipal provider bindings.
# Source: executive research candidates; current municipal contracts require
# independent official verification before creating any durable provider binding.
SP_MUNICIPAL_CANDIDATES: dict[str, tuple[str, tuple[str, ...]]] = {
    "3505708": ("Barueri", ("barueri-proprio",)),
    "3550308": ("São Paulo", ("nota-paulistana", "nfse-nacional")),
    "3509502": ("Campinas", ("dsf", "nfse-nacional")),
    "3552205": ("Sorocaba", ("dsf", "nfse-nacional")),
    "3518800": ("Guarulhos", ("ginfes", "nfse-nacional")),
    "3548500": ("Santos", ("ginfes", "nfse-nacional")),
    "3548807": ("São Caetano do Sul", ("ginfes", "nfse-nacional")),
    "3525904": ("Jundiaí", ("ginfes", "nfse-nacional")),
    "3552502": ("Suzano", ("ginfes", "nfse-nacional")),
    "3547304": ("Santana de Parnaíba", ("smarapd", "municipal-proprio")),
    "3534401": ("Osasco", ("sigiss", "betha", "e-receita", "nfse-nacional")),
    "3522505": ("Itapevi", ("sigiss", "betha", "e-receita", "nfse-nacional")),
    "3525003": ("Jandira", ("sigiss", "betha", "e-receita", "nfse-nacional")),
    "3528502": ("Mairiporã", ("sigiss", "betha", "e-receita", "nfse-nacional")),
    "3503901": ("Arujá", ("sigiss", "betha", "e-receita", "nfse-nacional")),
    "3527306": ("Louveira", ("sigiss", "betha", "e-receita", "nfse-nacional")),
    "3556206": ("Valinhos", ("sigiss", "betha", "e-receita", "nfse-nacional")),
    "3523909": ("Itu", ("sigiss", "betha", "e-receita", "nfse-nacional")),
    "3545209": ("Salto", ("sigiss", "betha", "e-receita", "nfse-nacional")),
    "3531803": ("Monte Mor", ("sigiss", "betha", "e-receita", "nfse-nacional")),
    "3518701": ("Guarujá", ("sigiss", "betha", "e-receita", "nfse-nacional")),
    "3551009": ("São Vicente", ("sigiss", "betha", "e-receita", "nfse-nacional")),
}



class GovernedSpMunicipalProviderResolver:
    """Validate SP issuer IBGE, then delegate to the canonical durable resolver.

    Construction should receive Control Plane's DurableProviderBindingResolver,
    which reads persisted approved bindings and fails closed if unconfigured.
    The caller should inject this adapter into existing ProviderGatewayService
    through its provider_selector parameter; that service still validates the
    configured ProviderRegistry, provider readiness and runtime credentials.
    """

    def __init__(self, *, canonical_resolver: ProviderSelectionResolver) -> None:
        if not callable(getattr(canonical_resolver, "resolve_provider_id", None)):
            raise TypeError("Canonical provider resolver is required")
        self._canonical = canonical_resolver

    def resolve_provider_id(
        self,
        *,
        scope: ExecutionScope,
        document_kind: FiscalDocumentKind,
        jurisdiction: BrazilianJurisdiction,
        operation: str,
    ) -> str:
        if document_kind is not FiscalDocumentKind.NFSE:
            raise UnsupportedProviderError("Municipal router supports NFS-e only")
        if jurisdiction.state_code != "SP":
            raise UnsupportedProviderError("Municipal router is limited to SP")
        issuer_ibge = jurisdiction.municipality_ibge_code
        # R16: the catalog lists onboarding candidates, but must NEVER be a
        # hard-coded allowlist. A future SP city with a duly approved durable
        # provider binding must work without modifying or deploying this code.
        if issuer_ibge is None or not issuer_ibge.startswith("35"):
            raise UnsupportedProviderError("Issuer municipality requires an SP IBGE code")
        if scope.host_namespace is None:
            raise UnsupportedProviderError("A trusted host namespace is required")
        try:
            ProviderOperation(operation)
        except ValueError:
            raise UnsupportedProviderError("Unsupported fiscal operation") from None
        # NO default provider. All authorization belongs to the existing
        # scope-bound, persisted Control Plane configuration resolver.
        return self._canonical.resolve_provider_id(
            scope=scope,
            document_kind=document_kind,
            jurisdiction=jurisdiction,
            operation=operation,
        )
