"""Explicit provider catalog for the HOMOLOGATION-only Controlled Pilot gate.

This catalog declares exactly which (document kind, jurisdiction, operation)
combinations each already-built, already-wired homologation gateway supports.
It performs no provider calls and grants no fiscal authority by itself; it is
consumed only by ``DurableHomologationEnvironmentReadinessService`` to decide
whether a given pilot cell is internally ready. Real capability (certificate,
provider binding, unit enablement) still comes from self-service portal
configuration (Empresas/Unidades/Certificados/Provedores) and governed admin
activation of the pilot kill-switch — never from editing this file per client.

Extending coverage to a new UF/municipality is a deliberate, reviewed code
change to this catalog (new jurisdiction entries), not a per-client change;
no code change is required to onboard a new client within an already-covered
jurisdiction.
"""

from __future__ import annotations

from kordena_fiscal.domain import BrazilianJurisdiction, FiscalDocumentKind, FiscalEnvironment
from kordena_fiscal.gateway.provider import ProviderDescriptor, ProviderOperation

# sefaz-sp-homologacao-nfe4: real SEFAZ-SP homologation gateway (NF-e model 55
# and NFC-e model 65), see gateway/nfe_sp_homologation.py and
# gateway/nfe_sp_operations_homologation.py. Authorize/query/cancel/inutilize
# are implemented against the real, pinned official SEFAZ-SP WSDL endpoints.
SEFAZ_SP_HOMOLOGATION_PROVIDER_ID = "sefaz-sp-homologacao-nfe4"

# nfse-nacional-producao-restrita: real NFS-e Nacional "produção restrita"
# (official homologation-equivalent) gateway, see
# gateway/nfse_nacional_homologation.py. Fail-closed outside HOMOLOGATION.
NFSE_NACIONAL_HOMOLOGATION_PROVIDER_ID = "nfse-nacional-producao-restrita"

# Municipalities already scoped for the SP pilot track (see
# docs/checkpoints/NFCORE_SP_THREE_CITIES_PILOT_2026-11-04.md). Adding a new
# municipality is a reviewed catalog change, never a per-client code change.
_SP_PILOT_MUNICIPALITIES: tuple[str, ...] = (
    "3509205",  # Cajamar
    "3548708",  # São Bernardo do Campo
    "3550308",  # São Paulo
)


def build_controlled_pilot_provider_catalog() -> tuple[ProviderDescriptor, ...]:
    """Return the real, evidence-backed provider catalog for Controlled Pilots."""

    sp_nfe_nfce = ProviderDescriptor(
        provider_id=SEFAZ_SP_HOMOLOGATION_PROVIDER_ID,
        document_kinds=frozenset({FiscalDocumentKind.NFE, FiscalDocumentKind.NFCE}),
        jurisdictions=(BrazilianJurisdiction(state_code="SP"),),
        environments=frozenset({FiscalEnvironment.HOMOLOGATION}),
        operations=frozenset(
            {
                ProviderOperation.AUTHORIZE,
                ProviderOperation.QUERY,
                ProviderOperation.CANCEL,
                ProviderOperation.INUTILIZE,
            }
        ),
    )
    nfse_nacional = ProviderDescriptor(
        provider_id=NFSE_NACIONAL_HOMOLOGATION_PROVIDER_ID,
        document_kinds=frozenset({FiscalDocumentKind.NFSE}),
        jurisdictions=tuple(
            BrazilianJurisdiction(state_code="SP", municipality_ibge_code=code)
            for code in _SP_PILOT_MUNICIPALITIES
        ),
        environments=frozenset({FiscalEnvironment.HOMOLOGATION}),
        operations=frozenset({ProviderOperation.AUTHORIZE, ProviderOperation.QUERY}),
    )
    return (sp_nfe_nfce, nfse_nacional)


__all__ = [
    "NFSE_NACIONAL_HOMOLOGATION_PROVIDER_ID",
    "SEFAZ_SP_HOMOLOGATION_PROVIDER_ID",
    "build_controlled_pilot_provider_catalog",
]
