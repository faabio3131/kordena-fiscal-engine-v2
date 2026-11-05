"""São Paulo NFS-e R16 routing via the EXISTING durable Control Plane authority.

The static catalog is advisory only and never authorizes provider transmission.
The canonical DurableProviderBindingResolver performs the actual exact-match
lookup by tenant, unit, environment, kind, issuer jurisdiction and operation.
No second authorization state, persistence, or fiscal gateway is introduced.
"""
from __future__ import annotations

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
