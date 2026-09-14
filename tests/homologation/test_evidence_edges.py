from __future__ import annotations

from kordena_fiscal.domain import BrazilianJurisdiction, FiscalDocumentKind, FiscalEnvironment
from kordena_fiscal.gateway import ProviderOperation
from kordena_fiscal.homologation import (
    HomologationEvidence,
    HomologationGateKey,
    HomologationGateNotConfiguredError,
    TechnicalGateState,
    TechnicalHomologationMatrix,
    TechnicalHomologationRule,
)


def _key(environment: FiscalEnvironment) -> HomologationGateKey:
    return HomologationGateKey(
        provider_id="provider-evidence",
        document_kind=FiscalDocumentKind.NFE,
        jurisdiction=BrazilianJurisdiction("SP"),
        environment=environment,
        operation=ProviderOperation.AUTHORIZE,
    )


def _evidence(*, signer: bool) -> HomologationEvidence:
    return HomologationEvidence(
        provider_adapter_available=True,
        credentials_reference_configured=True,
        signer_capability=signer,
        csc_reference_configured=False,
        transport_configured=True,
        resilience_certified=True,
        contract_tests_certified=True,
        jurisdiction_mapping=True,
        operation_supported=True,
    )


def test_missing_signer_capability_keeps_authorization_contract_only() -> None:
    rule = TechnicalHomologationRule(
        key=_key(FiscalEnvironment.HOMOLOGATION),
        evidence=_evidence(signer=False),
        requires_signer=True,
    )

    assert rule.technical_state is TechnicalGateState.CONTRACT_READY
    assert rule.missing_evidence == ("signer_capability",)


def test_environment_is_part_of_exact_gate_identity() -> None:
    homologation = TechnicalHomologationRule(
        key=_key(FiscalEnvironment.HOMOLOGATION),
        evidence=_evidence(signer=True),
        requires_signer=True,
    )
    matrix = TechnicalHomologationMatrix((homologation,))

    try:
        matrix.resolve(_key(FiscalEnvironment.PRODUCTION))
    except HomologationGateNotConfiguredError:
        pass
    else:
        raise AssertionError("production must not reuse homologation technical evidence")
