from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from kordena_fiscal.domain import (
    ExecutionScope,
    FiscalEnvironment,
    FiscalValidationError,
    Money,
    SourceReference,
)
from kordena_fiscal.lifecycle import FiscalDocumentState
from kordena_fiscal.operations import (
    FiscalOperationKind,
    FiscalOperationPayment,
    FiscalOperationSnapshot,
    FiscalOperationTotals,
)
from kordena_fiscal.reconciliation import (
    FiscalReconciliationCandidate,
    FiscalReconciliationEngine,
    HostSettlementSnapshot,
    ReconciliationContractError,
    ReconciliationIssueCode,
    ReconciliationStatus,
)

_NOW = datetime(2026, 9, 11, 17, 0, tzinfo=UTC)


def _scope(host: str = "fm.iron") -> ExecutionScope:
    return ExecutionScope(
        tenant_id="facc-shared",
        unit_id="funit-shared",
        environment=FiscalEnvironment.HOMOLOGATION,
        correlation_id=f"corr-{host}",
        host_namespace=host,
    )


def _operation(
    *,
    kind: FiscalOperationKind = FiscalOperationKind.SUBSCRIPTION,
    host: str = "fm.iron",
    net: str = "100.00",
    payment: str = "100.00",
    settled: bool = True,
) -> FiscalOperationSnapshot:
    net_money = Money(Decimal(net))
    payment_money = Money(Decimal(payment))
    payments: tuple[FiscalOperationPayment, ...] = ()
    if payment_money.amount > 0:
        payments = (FiscalOperationPayment(method="pix", amount=payment_money),)
    return FiscalOperationSnapshot(
        scope=_scope(host),
        operation_reference=SourceReference(kind.value, "operation-77"),
        operation_kind=kind,
        occurred_at=_NOW,
        totals=FiscalOperationTotals.from_net_amount(net_money),
        payments=payments,
        settled_at=_NOW if settled else None,
    )


def _candidate(
    operation: FiscalOperationSnapshot,
    *,
    state: FiscalDocumentState = FiscalDocumentState.AUTHORIZED,
    host: str | None = None,
    net: str = "100.00",
    payment: str = "100.00",
) -> FiscalReconciliationCandidate:
    return FiscalReconciliationCandidate(
        document_id="doc-77",
        scope=operation.scope if host is None else _scope(host),
        source=operation.operation_reference,
        state=state,
        net_amount=Money(Decimal(net)),
        payment_amount=Money(Decimal(payment)),
        change_amount=Money.zero(),
    )


def _codes(result: object) -> set[ReconciliationIssueCode]:
    assert hasattr(result, "issues")
    return {issue.code for issue in result.issues}


def test_subscription_operation_reconciles_without_sale_semantics() -> None:
    operation = _operation(kind=FiscalOperationKind.SUBSCRIPTION)
    candidate = _candidate(operation)

    result = FiscalReconciliationEngine().reconcile_operation(operation, (candidate,))

    assert result.status is ReconciliationStatus.MATCHED
    assert result.operation_reference == operation.operation_reference
    assert result.selected_document_id == "doc-77"
    assert result.issues == ()


@pytest.mark.parametrize(
    "kind",
    [
        FiscalOperationKind.MEMBERSHIP,
        FiscalOperationKind.SERVICE,
        FiscalOperationKind.RECURRING_CHARGE,
        FiscalOperationKind.SAAS_BILLING,
    ],
)
def test_non_sale_operation_families_reconcile(kind: FiscalOperationKind) -> None:
    operation = _operation(kind=kind)

    result = FiscalReconciliationEngine().reconcile_operation(
        operation,
        (_candidate(operation),),
    )

    assert result.status is ReconciliationStatus.MATCHED


def test_generic_reconciliation_uses_operation_neutral_issue_codes() -> None:
    operation = _operation(net="100.00", payment="90.00")
    candidate = _candidate(operation, net="99.00", payment="90.00")

    result = FiscalReconciliationEngine().reconcile_operation(operation, (candidate,))

    assert result.status is ReconciliationStatus.DIVERGENT
    assert ReconciliationIssueCode.OPERATION_PAYMENT_MISMATCH in _codes(result)
    assert ReconciliationIssueCode.OPERATION_FISCAL_TOTAL_MISMATCH in _codes(result)


def test_generic_reconciliation_requires_settled_operation() -> None:
    operation = _operation(settled=False)

    with pytest.raises(FiscalValidationError, match="must be settled"):
        FiscalReconciliationEngine().reconcile_operation(operation, ())


def test_generic_reconciliation_fails_closed_across_host_namespace() -> None:
    operation = _operation(host="fm.kordena")
    spoofed = _candidate(operation, host="fm.iron")

    with pytest.raises(ReconciliationContractError, match="identity scope"):
        FiscalReconciliationEngine().reconcile_operation(operation, (spoofed,))


def test_operation_kind_participates_in_reconciliation_fingerprint() -> None:
    engine = FiscalReconciliationEngine()
    subscription = _operation(kind=FiscalOperationKind.SUBSCRIPTION)
    service = _operation(kind=FiscalOperationKind.SERVICE)

    first = engine.reconcile_operation(subscription, ())
    second = engine.reconcile_operation(service, ())

    assert first.fingerprint != second.fingerprint


def test_legacy_host_settlement_wrapper_preserves_historical_issue_codes() -> None:
    scope = _scope("fm.kordena")
    source = SourceReference("sale", "sale-legacy")
    host = HostSettlementSnapshot(
        scope=scope,
        source=source,
        sale_amount=Money(Decimal("100.00")),
        payment_amount=Money(Decimal("90.00")),
        change_amount=Money.zero(),
        settled_at=_NOW,
    )
    candidate = FiscalReconciliationCandidate(
        document_id="doc-legacy",
        scope=scope,
        source=source,
        state=FiscalDocumentState.AUTHORIZED,
        net_amount=Money(Decimal("99.00")),
        payment_amount=Money(Decimal("90.00")),
        change_amount=Money.zero(),
    )

    result = FiscalReconciliationEngine().reconcile(host, (candidate,))

    assert ReconciliationIssueCode.HOST_PAYMENT_MISMATCH in _codes(result)
    assert ReconciliationIssueCode.SALE_FISCAL_TOTAL_MISMATCH in _codes(result)
    assert ReconciliationIssueCode.OPERATION_PAYMENT_MISMATCH not in _codes(result)
