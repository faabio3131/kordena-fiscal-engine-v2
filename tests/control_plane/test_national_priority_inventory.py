"""Priority national pilot inventory is data-only and deny-by-default."""
from dataclasses import FrozenInstanceError, replace

import pytest

from kordena_fiscal.control_plane.national_priority_inventory import (
    NAT_PRIORITY_PILOTS,
    IntegrationEvidence,
    NfseIssuerChannel,
    PriorityStatePilot,
    priority_pilot,
)
from kordena_fiscal.domain import FiscalDocumentKind, FiscalValidationError


def test_all_five_priority_states_are_present_in_exact_director_order() -> None:
    assert tuple(pilot.uf for pilot in NAT_PRIORITY_PILOTS) == (
        "MG", "RJ", "PR", "MT", "MS",
    )
    assert tuple(pilot.municipality_ibge for pilot in NAT_PRIORITY_PILOTS) == (
        "3106200", "3304557", "4106902", "5103403", "5002704",
    )
    assert len({pilot.uf for pilot in NAT_PRIORITY_PILOTS}) == 5


@pytest.mark.parametrize("kind", list(FiscalDocumentKind))
def test_each_document_has_public_source_but_no_issuance_claim(
    kind: FiscalDocumentKind,
) -> None:
    for pilot in NAT_PRIORITY_PILOTS:
        assert pilot.source_for(kind).startswith("https://")
        assert pilot.nfse_evidence is IntegrationEvidence.RESEARCH_REQUIRED
        assert not hasattr(pilot, "provider_binding_id")
        assert not hasattr(pilot, "authorized_for_production")


def test_rj_nfe_uses_svrs_while_other_first_wave_states_use_own_authorizer() -> None:
    assert priority_pilot("RJ").nfe_authorizer == "SVRS"
    assert all(
        priority_pilot(uf).nfe_authorizer == "SEFAZ_UF"
        for uf in ("MG", "PR", "MT", "MS")
    )


def test_no_default_provider_for_unknown_or_case_changed_state() -> None:
    for uf in ("SP", "BA", "mg", "", "XX"):
        with pytest.raises(FiscalValidationError):
            priority_pilot(uf)


def test_catalog_entries_are_immutable() -> None:
    with pytest.raises(FrozenInstanceError):
        priority_pilot("MG").municipality = "Outra cidade"  # type: ignore[misc]


def test_reject_mismatched_ibge_and_non_https_sources() -> None:
    pilot = priority_pilot("MG")
    with pytest.raises(FiscalValidationError, match="IBGE"):
        replace(pilot, municipality_ibge="3304557")
    with pytest.raises(FiscalValidationError, match="HTTPS"):
        replace(pilot, nfe_source="http://internal.local/fiscal")
    with pytest.raises(FiscalValidationError, match="HTTPS"):
        replace(pilot, nfce_source="https://user:password@example.com/service")
    with pytest.raises(FiscalValidationError, match="Authorizer"):
        replace(pilot, nfe_authorizer="SVRS_FALLBACK")


def test_no_duplicate_generic_provider_selection_is_added() -> None:
    # The inventory stores public research sources only. Fiscal execution
    # still resolves through DurableProviderBindingResolver and readiness.
    assert isinstance(priority_pilot("MG"), PriorityStatePilot)
    assert not hasattr(priority_pilot("MG"), "resolve_provider_id")


def test_official_nfse_capital_channel_is_research_only() -> None:
    assert [priority_pilot(uf).nfse_channel for uf in ("MG", "RJ", "PR", "MT")] == [
        NfseIssuerChannel.NATIONAL,
    ] * 4
    assert priority_pilot("MS").nfse_channel is NfseIssuerChannel.MUNICIPAL_HYBRID_REVIEW
    for pilot in NAT_PRIORITY_PILOTS:
        assert pilot.nfse_evidence is IntegrationEvidence.RESEARCH_REQUIRED
        assert not hasattr(pilot, "fiscal_issuance_enabled")


def test_unrecognized_nfse_channel_fails_closed() -> None:
    with pytest.raises(FiscalValidationError, match="NFS-e"):
        replace(priority_pilot("MG"), nfse_channel="national")  # type: ignore[arg-type]
