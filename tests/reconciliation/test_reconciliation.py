from datetime import UTC, datetime
from decimal import Decimal

import pytest

from kordena_fiscal.domain import (
    ExecutionScope,
    FiscalEnvironment,
    Money,
    SourceReference,
)
from kordena_fiscal.lifecycle import FiscalDocumentState
from kordena_fiscal.reconciliation import (
    FiscalReconciliationCandidate,
    FiscalReconciliationEngine,
    HostSettlementSnapshot,
    ReconciliationContractError,
    ReconciliationIssueCode,
    ReconciliationStatus,
)


def _scope(*, unit: str = "unit-a") -> ExecutionScope:
    return ExecutionScope(
        tenant_id="tenant-a",
        unit_id=unit,
        environment=FiscalEnvironment.HOMOLOGATION,
        correlation_id="corr-reconciliation-1",
    )


def _source(*, source_id: str = "sale-77") -> SourceReference:
    return SourceReference(source_type="sale", source_id=source_id)


def _money(value: str) -> Money:
    return Money(Decimal(value))


def _host(
    *,
    sale: str = "100.00",
    payment: str = "100.00",
    change: str = "0.00",
) -> HostSettlementSnapshot:
    return HostSettlementSnapshot(
        scope=_scope(),
        source=_source(),
        sale_amount=_money(sale),
        payment_amount=_money(payment),
        change_amount=_money(change),
        settled_at=datetime(2026, 9, 11, 10, 0, tzinfo=UTC),
    )


def _candidate(
    document_id: str,
    state: FiscalDocumentState,
    *,
    scope: ExecutionScope | None = None,
    source: SourceReference | None = None,
    net: str = "100.00",
    payment: str = "100.00",
    change: str = "0.00",
) -> FiscalReconciliationCandidate:
    return FiscalReconciliationCandidate(
        document_id=document_id,
        scope=scope or _scope(),
        source=source or _source(),
        state=state,
        net_amount=_money(net),
        payment_amount=_money(payment),
        change_amount=_money(change),
    )


def _codes(result: object) -> set[ReconciliationIssueCode]:
    assert hasattr(result, "issues")
    return {issue.code for issue in result.issues}


def test_authorized_document_matching_host_settlement_is_reconciled() -> None:
    engine = FiscalReconciliationEngine()
    authorized = _candidate("doc-authorized", FiscalDocumentState.AUTHORIZED)
    rejected = _candidate("doc-rejected", FiscalDocumentState.REJECTED)

    result = engine.reconcile(_host(), (rejected, authorized))
    replay = engine.reconcile(_host(), (authorized, rejected))

    assert result.status is ReconciliationStatus.MATCHED
    assert result.selected_document_id == "doc-authorized"
    assert result.issues == ()
    assert result.fingerprint == replay.fingerprint


def test_host_payment_mismatch_is_divergent_even_with_authorized_document() -> None:
    result = FiscalReconciliationEngine().reconcile(
        _host(payment="90.00"),
        (_candidate("doc-1", FiscalDocumentState.AUTHORIZED),),
    )

    assert result.status is ReconciliationStatus.DIVERGENT
    assert ReconciliationIssueCode.HOST_PAYMENT_MISMATCH in _codes(result)
    assert ReconciliationIssueCode.PAYMENT_SNAPSHOT_MISMATCH in _codes(result)


def test_fiscal_totals_and_payment_snapshot_divergences_are_explicit() -> None:
    result = FiscalReconciliationEngine().reconcile(
        _host(payment="120.00", change="20.00"),
        (
            _candidate(
                "doc-1",
                FiscalDocumentState.AUTHORIZED,
                net="99.00",
                payment="100.00",
                change="0.00",
            ),
        ),
    )

    assert result.status is ReconciliationStatus.DIVERGENT
    assert ReconciliationIssueCode.SALE_FISCAL_TOTAL_MISMATCH in _codes(result)
    assert ReconciliationIssueCode.FISCAL_PAYMENT_MISMATCH in _codes(result)
    assert ReconciliationIssueCode.PAYMENT_SNAPSHOT_MISMATCH in _codes(result)


def test_pending_fiscal_attempt_does_not_become_false_success() -> None:
    result = FiscalReconciliationEngine().reconcile(
        _host(),
        (_candidate("doc-1", FiscalDocumentState.TRANSMITTING),),
    )

    assert result.status is ReconciliationStatus.PENDING
    assert _codes(result) == {ReconciliationIssueCode.FISCAL_PROCESSING_PENDING}


def test_cancelled_fiscal_document_for_settled_sale_is_divergent() -> None:
    result = FiscalReconciliationEngine().reconcile(
        _host(),
        (_candidate("doc-1", FiscalDocumentState.CANCELLED),),
    )

    assert result.status is ReconciliationStatus.DIVERGENT
    assert _codes(result) == {
        ReconciliationIssueCode.CLOSED_SALE_WITH_CANCELLED_FISCAL
    }


def test_duplicate_authorized_documents_are_blocked() -> None:
    result = FiscalReconciliationEngine().reconcile(
        _host(),
        (
            _candidate("doc-1", FiscalDocumentState.AUTHORIZED),
            _candidate("doc-2", FiscalDocumentState.AUTHORIZED),
        ),
    )

    assert result.status is ReconciliationStatus.DIVERGENT
    assert _codes(result) == {
        ReconciliationIssueCode.DUPLICATE_AUTHORIZED_FISCAL_DOCUMENT
    }
    assert result.selected_document_id is None


def test_parallel_pending_attempt_alongside_authorized_is_divergent() -> None:
    result = FiscalReconciliationEngine().reconcile(
        _host(),
        (
            _candidate("doc-authorized", FiscalDocumentState.AUTHORIZED),
            _candidate("doc-pending", FiscalDocumentState.READY_TO_TRANSMIT),
        ),
    )

    assert result.status is ReconciliationStatus.DIVERGENT
    assert ReconciliationIssueCode.PARALLEL_FISCAL_ATTEMPT in _codes(result)


def test_missing_authorized_document_is_divergent() -> None:
    result = FiscalReconciliationEngine().reconcile(
        _host(),
        (_candidate("doc-rejected", FiscalDocumentState.REJECTED),),
    )

    assert result.status is ReconciliationStatus.DIVERGENT
    assert _codes(result) == {
        ReconciliationIssueCode.MISSING_AUTHORIZED_FISCAL_DOCUMENT
    }


def test_cross_scope_and_wrong_source_fail_closed() -> None:
    engine = FiscalReconciliationEngine()

    with pytest.raises(ReconciliationContractError, match="crosses"):
        engine.reconcile(
            _host(),
            (
                _candidate(
                    "doc-1",
                    FiscalDocumentState.AUTHORIZED,
                    scope=_scope(unit="unit-b"),
                ),
            ),
        )

    with pytest.raises(ReconciliationContractError, match="does not reference"):
        engine.reconcile(
            _host(),
            (
                _candidate(
                    "doc-2",
                    FiscalDocumentState.AUTHORIZED,
                    source=_source(source_id="sale-other"),
                ),
            ),
        )


def test_duplicate_candidate_identity_is_contract_error() -> None:
    engine = FiscalReconciliationEngine()
    first = _candidate("doc-1", FiscalDocumentState.REJECTED)
    second = _candidate("doc-1", FiscalDocumentState.ERROR)

    with pytest.raises(ReconciliationContractError, match="duplicate candidate"):
        engine.reconcile(_host(), (first, second))
