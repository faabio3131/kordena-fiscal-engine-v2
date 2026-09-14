from dataclasses import replace
from datetime import UTC, datetime

import pytest

from kordena_fiscal.domain import (
    Cnpj,
    ElectronicInvoiceModel,
    ExecutionScope,
    FiscalEnvironment,
    FiscalValidationError,
)
from kordena_fiscal.lifecycle import (
    FiscalDocumentState,
    FiscalStateMachine,
    FiscalStateSnapshot,
)
from kordena_fiscal.operations import (
    CancellationRequest,
    FakeFiscalOperationsGateway,
    FiscalCancellationService,
    FiscalEventStatus,
    FiscalOperationsClient,
    FiscalOperationsContractError,
    FiscalQueryRequest,
    FiscalQueryStatus,
    InutilizationRequest,
    MutatingFiscalOperationsGateway,
)
from kordena_fiscal.xml import AccessKeyInput, NfeAccessKey, build_access_key


def _instant() -> datetime:
    return datetime(2026, 9, 11, 0, 40, tzinfo=UTC)


def _scope(*, unit: str = "unit-a") -> ExecutionScope:
    return ExecutionScope(
        tenant_id="tenant-a",
        unit_id=unit,
        environment=FiscalEnvironment.HOMOLOGATION,
        correlation_id="corr-fisc-14",
    )


def _access_key() -> NfeAccessKey:
    return build_access_key(
        AccessKeyInput(
            state_ibge_code="35",
            issued_at=_instant(),
            issuer_cnpj=Cnpj("12.345.678/0001-95"),
            model=ElectronicInvoiceModel.NFCE,
            series=3,
            invoice_number=10,
            emission_type=1,
            numeric_code=12345678,
        )
    )


def _authorized_lifecycle() -> FiscalStateSnapshot:
    machine = FiscalStateMachine()
    state = FiscalStateSnapshot.initial("doc-fisc-14", _instant())
    for target in (
        FiscalDocumentState.VALIDATING,
        FiscalDocumentState.READY_TO_SIGN,
        FiscalDocumentState.SIGNING,
        FiscalDocumentState.READY_TO_TRANSMIT,
        FiscalDocumentState.TRANSMITTING,
        FiscalDocumentState.AUTHORIZED,
    ):
        state = machine.transition(
            state,
            target,
            occurred_at=_instant(),
            reason=f"synthetic transition to {target.value}",
            correlation_id="corr-fisc-14",
        )
    return state


def _cancel_request() -> CancellationRequest:
    return CancellationRequest.build(
        scope=_scope(),
        access_key=_access_key(),
        authorization_protocol="SYNTHETIC-AUTH-PROTOCOL",
        justification="Cancelamento fiscal sintetico por teste",
    )


def test_query_returns_authorized_status_and_protocol() -> None:
    gateway = FakeFiscalOperationsGateway(query_status=FiscalQueryStatus.AUTHORIZED)
    client = FiscalOperationsClient(gateway)

    result = client.query(FiscalQueryRequest(scope=_scope(), access_key=_access_key()))

    assert result.status is FiscalQueryStatus.AUTHORIZED
    assert result.protocol_reference == "SYNTHETIC-AUTH-PROTOCOL"
    assert len(gateway.query_calls) == 1


def test_cancellation_acceptance_moves_authorized_document_to_cancelled() -> None:
    gateway = FakeFiscalOperationsGateway(event_status=FiscalEventStatus.ACCEPTED)
    service = FiscalCancellationService(FiscalOperationsClient(gateway))

    outcome = service.cancel(
        lifecycle=_authorized_lifecycle(),
        request=_cancel_request(),
        occurred_at=_instant(),
        correlation_id="corr-cancel-accepted",
    )

    assert outcome.result.status is FiscalEventStatus.ACCEPTED
    assert outcome.result.event_protocol_reference == "SYNTHETIC-CANCEL-PROTOCOL"
    assert outcome.lifecycle.state is FiscalDocumentState.CANCELLED
    assert outcome.lifecycle.history[-2].to_state is FiscalDocumentState.CANCEL_REQUESTED
    assert outcome.lifecycle.history[-1].to_state is FiscalDocumentState.CANCELLED
    assert len(gateway.cancel_calls) == 1


def test_cancellation_rejection_restores_authorized_state() -> None:
    gateway = FakeFiscalOperationsGateway(event_status=FiscalEventStatus.REJECTED)
    service = FiscalCancellationService(FiscalOperationsClient(gateway))

    outcome = service.cancel(
        lifecycle=_authorized_lifecycle(),
        request=_cancel_request(),
        occurred_at=_instant(),
        correlation_id="corr-cancel-rejected",
    )

    assert outcome.result.status is FiscalEventStatus.REJECTED
    assert outcome.result.rejection_code == "SYNTHETIC-REJECTION"
    assert outcome.lifecycle.state is FiscalDocumentState.AUTHORIZED
    assert outcome.lifecycle.history[-1].from_state is FiscalDocumentState.CANCEL_REQUESTED


def test_pending_cancellation_remains_cancel_requested_without_false_success() -> None:
    gateway = FakeFiscalOperationsGateway(event_status=FiscalEventStatus.PENDING)
    service = FiscalCancellationService(FiscalOperationsClient(gateway))

    outcome = service.cancel(
        lifecycle=_authorized_lifecycle(),
        request=_cancel_request(),
        occurred_at=_instant(),
        correlation_id="corr-cancel-pending",
    )

    assert outcome.result.status is FiscalEventStatus.PENDING
    assert outcome.lifecycle.state is FiscalDocumentState.CANCEL_REQUESTED
    assert outcome.result.event_protocol_reference is None


def test_cancellation_requires_authorized_lifecycle() -> None:
    gateway = FakeFiscalOperationsGateway()
    service = FiscalCancellationService(FiscalOperationsClient(gateway))
    draft = FiscalStateSnapshot.initial("doc-draft", _instant())

    with pytest.raises(FiscalValidationError, match="AUTHORIZED"):
        service.cancel(
            lifecycle=draft,
            request=_cancel_request(),
            occurred_at=_instant(),
            correlation_id="corr-invalid-cancel",
        )

    assert gateway.cancel_calls == ()


def test_cancellation_request_id_is_deterministic_and_content_sensitive() -> None:
    first = _cancel_request()
    same = _cancel_request()
    changed = CancellationRequest.build(
        scope=_scope(),
        access_key=_access_key(),
        authorization_protocol="SYNTHETIC-AUTH-PROTOCOL",
        justification="Outra justificativa fiscal valida para teste",
    )

    assert first.request_id == same.request_id
    assert first.request_id != changed.request_id
    assert len(first.request_id) == 64


def test_cancellation_adapter_identity_mismatch_fails_closed() -> None:
    client = FiscalOperationsClient(
        MutatingFiscalOperationsGateway(mutate="cancel_request_id")
    )

    with pytest.raises(FiscalOperationsContractError, match="request_id"):
        client.cancel(_cancel_request())


def test_inutilization_builds_deterministic_request_and_accepts_exact_range() -> None:
    gateway = FakeFiscalOperationsGateway(event_status=FiscalEventStatus.ACCEPTED)
    client = FiscalOperationsClient(gateway)
    request = InutilizationRequest.build(
        scope=_scope(),
        model=ElectronicInvoiceModel.NFCE,
        series=3,
        first_number=11,
        last_number=15,
        justification="Faixa nao utilizada por falha operacional",
    )

    result = client.inutilize(request)

    assert result.status is FiscalEventStatus.ACCEPTED
    assert result.event_protocol_reference == "SYNTHETIC-INUTILIZATION-PROTOCOL"
    assert result.request_id == request.request_id
    assert result.first_number == 11
    assert result.last_number == 15
    assert len(gateway.inutilization_calls) == 1


def test_inutilization_rejects_invalid_range_and_short_justification() -> None:
    with pytest.raises(FiscalValidationError, match="last_number"):
        InutilizationRequest.build(
            scope=_scope(),
            model=ElectronicInvoiceModel.NFCE,
            series=3,
            first_number=20,
            last_number=19,
            justification="Justificativa suficientemente longa",
        )

    with pytest.raises(FiscalValidationError, match="15 characters"):
        InutilizationRequest.build(
            scope=_scope(),
            model=ElectronicInvoiceModel.NFCE,
            series=3,
            first_number=20,
            last_number=20,
            justification="curta",
        )


def test_inutilization_adapter_cannot_mutate_requested_range() -> None:
    client = FiscalOperationsClient(
        MutatingFiscalOperationsGateway(mutate="inutilization_range")
    )
    request = InutilizationRequest.build(
        scope=_scope(),
        model=ElectronicInvoiceModel.NFE,
        series=1,
        first_number=100,
        last_number=105,
        justification="Numeracao inutilizada por teste controlado",
    )

    with pytest.raises(FiscalOperationsContractError, match="does not match"):
        client.inutilize(request)


def test_cross_scope_cancellation_result_is_blocked() -> None:
    client = FiscalOperationsClient(MutatingFiscalOperationsGateway(mutate="cancel_scope"))

    with pytest.raises(FiscalOperationsContractError, match="different scope"):
        client.cancel(_cancel_request())


def test_request_scope_is_not_silently_rewritten() -> None:
    request = _cancel_request()
    changed_scope = replace(request.scope, unit_id="unit-b")

    assert changed_scope != request.scope
    assert request.scope.unit_id == "unit-a"
