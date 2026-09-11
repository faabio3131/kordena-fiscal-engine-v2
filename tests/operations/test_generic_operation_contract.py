from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from kordena_fiscal.domain import (
    ExecutionScope,
    FiscalEnvironment,
    FiscalValidationError,
    Money,
    SourceReference,
)
from kordena_fiscal.operations import (
    FiscalOperationKind,
    FiscalOperationPayment,
    FiscalOperationSnapshot,
    FiscalOperationTotals,
)

_NOW = datetime(2026, 9, 11, 16, 0, tzinfo=UTC)


def _scope() -> ExecutionScope:
    return ExecutionScope(
        tenant_id="facc-001",
        unit_id="funit-001",
        environment=FiscalEnvironment.HOMOLOGATION,
        correlation_id="corr-operation-001",
        host_namespace="fm.iron",
    )


def _totals(net: str = "100.00") -> FiscalOperationTotals:
    amount = Money(Decimal(net))
    return FiscalOperationTotals.from_net_amount(amount)


def _operation(
    *,
    kind: FiscalOperationKind = FiscalOperationKind.SUBSCRIPTION,
    occurred_at: datetime = _NOW,
    settled_at: datetime | None = _NOW,
) -> FiscalOperationSnapshot:
    return FiscalOperationSnapshot(
        scope=_scope(),
        operation_reference=SourceReference(kind.value, "operation-001"),
        operation_kind=kind,
        occurred_at=occurred_at,
        totals=_totals(),
        payments=(
            FiscalOperationPayment(
                method="pix",
                amount=Money(Decimal("100.00")),
                reference="payment-001",
            ),
        ),
        settled_at=settled_at,
    )


@pytest.mark.parametrize(
    "kind",
    [
        FiscalOperationKind.SALE,
        FiscalOperationKind.MEMBERSHIP,
        FiscalOperationKind.SUBSCRIPTION,
        FiscalOperationKind.SERVICE,
        FiscalOperationKind.RECURRING_CHARGE,
        FiscalOperationKind.SAAS_BILLING,
        FiscalOperationKind.OTHER,
    ],
)
def test_universal_contract_supports_all_operation_families(
    kind: FiscalOperationKind,
) -> None:
    operation = _operation(kind=kind)

    assert operation.operation_kind is kind
    assert operation.operation_reference.source_type == kind.value
    assert operation.is_settled is True
    assert operation.payment_amount.amount == Decimal("100.00")
    assert operation.settled_payment_amount.amount == Decimal("100.00")


def test_totals_require_exact_economic_identity() -> None:
    with pytest.raises(FiscalValidationError, match="net_amount"):
        FiscalOperationTotals(
            gross_amount=Money(Decimal("100.00")),
            discount_amount=Money(Decimal("10.00")),
            surcharge_amount=Money(Decimal("5.00")),
            net_amount=Money(Decimal("100.00")),
        )


def test_totals_preserve_discount_and_surcharge_without_hidden_rounding() -> None:
    totals = FiscalOperationTotals(
        gross_amount=Money(Decimal("100.1234")),
        discount_amount=Money(Decimal("10.1000")),
        surcharge_amount=Money(Decimal("2.0001")),
        net_amount=Money(Decimal("92.0235")),
    )

    assert totals.net_amount.amount == Decimal("92.0235")


def test_payment_normalizes_method_and_reference() -> None:
    payment = FiscalOperationPayment(
        method=" PIX ",
        amount=Money(Decimal("50.00")),
        reference=" payment-42 ",
    )

    assert payment.method == "pix"
    assert payment.reference == "payment-42"


def test_operation_rejects_settlement_before_occurrence() -> None:
    with pytest.raises(FiscalValidationError, match="before occurred_at"):
        _operation(
            occurred_at=_NOW,
            settled_at=_NOW - timedelta(seconds=1),
        )


def test_operation_rejects_change_above_payment_total() -> None:
    with pytest.raises(FiscalValidationError, match="change_amount"):
        FiscalOperationSnapshot(
            scope=_scope(),
            operation_reference=SourceReference("sale", "operation-change"),
            operation_kind=FiscalOperationKind.SALE,
            occurred_at=_NOW,
            totals=_totals("10.00"),
            payments=(
                FiscalOperationPayment(
                    method="cash",
                    amount=Money(Decimal("10.00")),
                ),
            ),
            settled_at=_NOW,
            change_amount=Money(Decimal("11.00")),
        )


def test_unsettled_operation_is_valid_contract_state() -> None:
    operation = _operation(settled_at=None)

    assert operation.is_settled is False
    assert operation.settled_at is None
