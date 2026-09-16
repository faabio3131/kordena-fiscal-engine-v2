from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from kordena_fiscal.control_plane.commercial_models import HomologationEvidenceRecord
from kordena_fiscal.control_plane.models import AdminPrincipal, ControlPlanePermission
from kordena_fiscal.domain import (
    BrazilianJurisdiction,
    ExecutionScope,
    FiscalDocumentKind,
    FiscalEnvironment,
    FiscalValidationError,
)
from kordena_fiscal.gateway.production_activation import (
    FiscalProductionActivationRequiredError,
    FiscalProductionActivationService,
    FiscalProductionApprovalError,
    GovernedProviderGatewayService,
    HumanProductionApproval,
    OfficialHomologationProof,
    ProductionActivationKey,
    ProductionExecutionAuthority,
)
from kordena_fiscal.gateway.provider import (
    ProviderOperation,
    ProviderRequest,
    ProviderResponse,
    ProviderResponseStatus,
)

NOW = datetime(2026, 9, 15, 21, 0, tzinfo=UTC)
SP = BrazilianJurisdiction("SP")


class FixedClock:
    def __init__(self, instant: datetime) -> None:
        self.instant = instant

    def now(self) -> datetime:
        return self.instant


class RecordingGateway:
    def __init__(self) -> None:
        self.calls: list[tuple[ProviderRequest, str | None]] = []

    def execute(
        self,
        request: ProviderRequest,
        *,
        provider_id: str | None = None,
    ) -> ProviderResponse:
        self.calls.append((request, provider_id))
        return ProviderResponse(
            provider_id=provider_id or "provider-selected-in-homologation",
            operation=request.operation,
            status=ProviderResponseStatus.FOUND,
            correlation_id=request.correlation_id,
        )


def _request(
    *,
    environment: FiscalEnvironment = FiscalEnvironment.PRODUCTION,
    tenant_id: str = "tenant-a",
    unit_id: str = "unit-a",
    jurisdiction: BrazilianJurisdiction = SP,
) -> ProviderRequest:
    return ProviderRequest(
        scope=ExecutionScope(
            host_namespace="kordena",
            tenant_id=tenant_id,
            unit_id=unit_id,
            environment=environment,
            correlation_id="corr-web12",
        ),
        document_kind=FiscalDocumentKind.NFE,
        jurisdiction=jurisdiction,
        operation=ProviderOperation.QUERY,
        payload=b"status-query",
        correlation_id="corr-web12",
        workload_id="workload-web12",
    )


def _evidence(
    *,
    external_official: bool = True,
    tenant_id: str = "tenant-a",
    unit_id: str = "unit-a",
    jurisdiction: BrazilianJurisdiction = SP,
) -> HomologationEvidenceRecord:
    return HomologationEvidenceRecord(
        tenant_id=tenant_id,
        unit_id=unit_id,
        environment=FiscalEnvironment.HOMOLOGATION,
        provider_id="provider-a",
        document_kind=FiscalDocumentKind.NFE,
        jurisdiction=jurisdiction,
        operation="query",
        provider_adapter_available=True,
        credentials_reference_configured=True,
        signer_capability=False,
        csc_reference_configured=False,
        transport_configured=True,
        resilience_certified=True,
        contract_tests_certified=True,
        jurisdiction_mapping=True,
        operation_supported=True,
        external_evidence_id="official-evidence-sp-nfe-query" if external_official else None,
        external_official=external_official,
        recorded_at=NOW,
    )


def _actor(*, tenant_id: str = "tenant-a", allowed: bool = True) -> AdminPrincipal:
    permissions: frozenset[ControlPlanePermission] = (
        frozenset({ControlPlanePermission.CAPABILITY_WRITE}) if allowed else frozenset()
    )
    return AdminPrincipal(
        actor_id="fiscal-authority-admin",
        permissions=permissions,
        tenant_ids=frozenset({tenant_id}),
    )


def _approval(proof: OfficialHomologationProof) -> HumanProductionApproval:
    return HumanProductionApproval(
        key=proof.key,
        approved_by="human-director",
        approval_reference="change-control-2026-09-15-001",
        approved_at=NOW,
        correlation_id="corr-web12-approval",
    )


def _active_authority() -> ProductionExecutionAuthority:
    proof = OfficialHomologationProof.from_record(_evidence())
    service = FiscalProductionActivationService(clock=FixedClock(NOW + timedelta(minutes=1)))
    record = service.activate(
        actor=_actor(),
        approval=_approval(proof),
        proof=proof,
        correlation_id="corr-web12-activation",
    )
    return ProductionExecutionAuthority((record,))


def test_internal_or_synthetic_evidence_cannot_activate_production() -> None:
    with pytest.raises(FiscalProductionApprovalError, match="external official"):
        OfficialHomologationProof.from_record(_evidence(external_official=False))


def test_activation_requires_capability_write_and_exact_tenant_scope() -> None:
    proof = OfficialHomologationProof.from_record(_evidence())
    service = FiscalProductionActivationService(clock=FixedClock(NOW))

    with pytest.raises(FiscalProductionApprovalError, match="capability.write"):
        service.activate(
            actor=_actor(allowed=False),
            approval=_approval(proof),
            proof=proof,
            correlation_id="corr-denied-permission",
        )

    with pytest.raises(FiscalProductionApprovalError, match="target tenant"):
        service.activate(
            actor=_actor(tenant_id="tenant-b"),
            approval=_approval(proof),
            proof=proof,
            correlation_id="corr-denied-tenant",
        )


def test_production_gateway_fails_closed_without_explicit_authority_or_provider() -> None:
    delegate = RecordingGateway()
    gateway = GovernedProviderGatewayService(delegate)
    request = _request()

    with pytest.raises(FiscalProductionActivationRequiredError, match="provider_id"):
        gateway.execute(request)
    with pytest.raises(FiscalProductionActivationRequiredError, match="injected authority"):
        gateway.execute(request, provider_id="provider-a")
    assert delegate.calls == []


def test_exact_injected_grant_allows_only_its_production_cell() -> None:
    delegate = RecordingGateway()
    gateway = GovernedProviderGatewayService(
        delegate,
        production_authority=_active_authority(),
    )

    response = gateway.execute(_request(), provider_id="provider-a")
    assert response.status is ProviderResponseStatus.FOUND
    assert gateway.fiscal_production_activated is True
    assert len(delegate.calls) == 1

    for request, provider_id in (
        (_request(tenant_id="tenant-b"), "provider-a"),
        (_request(unit_id="unit-b"), "provider-a"),
        (_request(), "provider-b"),
        (_request(jurisdiction=BrazilianJurisdiction("RJ")), "provider-a"),
    ):
        with pytest.raises(FiscalProductionActivationRequiredError, match="exact active"):
            gateway.execute(request, provider_id=provider_id)
    assert len(delegate.calls) == 1


def test_revocation_kill_switch_overrides_prior_active_record() -> None:
    proof = OfficialHomologationProof.from_record(_evidence())
    service = FiscalProductionActivationService(clock=FixedClock(NOW + timedelta(minutes=1)))
    active = service.activate(
        actor=_actor(),
        approval=_approval(proof),
        proof=proof,
        correlation_id="corr-active",
    )
    service = FiscalProductionActivationService(clock=FixedClock(NOW + timedelta(minutes=2)))
    revoked = service.revoke(
        actor=_actor(),
        current=active,
        correlation_id="corr-revoked",
    )
    authority = ProductionExecutionAuthority((active, revoked))
    gateway = GovernedProviderGatewayService(
        RecordingGateway(),
        production_authority=authority,
    )

    assert authority.production_activated is False
    with pytest.raises(FiscalProductionActivationRequiredError, match="exact active"):
        gateway.execute(_request(), provider_id="provider-a")


def test_homologation_execution_does_not_require_production_authority() -> None:
    delegate = RecordingGateway()
    gateway = GovernedProviderGatewayService(delegate)

    response = gateway.execute(_request(environment=FiscalEnvironment.HOMOLOGATION))

    assert response.status is ProviderResponseStatus.FOUND
    assert len(delegate.calls) == 1


def test_human_approval_and_official_evidence_must_match_exact_cell() -> None:
    sp_proof = OfficialHomologationProof.from_record(_evidence())
    rj_proof = OfficialHomologationProof.from_record(
        _evidence(jurisdiction=BrazilianJurisdiction("RJ"))
    )
    service = FiscalProductionActivationService(clock=FixedClock(NOW))

    with pytest.raises(FiscalProductionApprovalError, match="exact same cell"):
        service.activate(
            actor=_actor(),
            approval=_approval(sp_proof),
            proof=rj_proof,
            correlation_id="corr-mismatch",
        )


def test_invalid_human_decision_never_creates_approval() -> None:
    proof = OfficialHomologationProof.from_record(_evidence())
    with pytest.raises(FiscalProductionApprovalError, match="PRODUCTION_APPROVED"):
        HumanProductionApproval(
            key=proof.key,
            approved_by="human-director",
            approval_reference="change-control-denied",
            approved_at=NOW,
            correlation_id="corr-denied",
            decision="APPROVE_AUTOMATICALLY",
        )


def test_nfse_activation_key_requires_exact_municipality() -> None:
    with pytest.raises(FiscalValidationError, match="municipality_ibge_code"):
        ProductionActivationKey(
            tenant_id="tenant-a",
            unit_id="unit-a",
            provider_id="provider-a",
            document_kind=FiscalDocumentKind.NFSE,
            jurisdiction=BrazilianJurisdiction("SP"),
            operation=ProviderOperation.QUERY,
        )
