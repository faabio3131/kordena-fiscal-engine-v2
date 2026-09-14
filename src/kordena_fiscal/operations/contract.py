"""Host-neutral fiscal operation contract.

The contract represents an economic/fiscal fact before any document-specific or
provider-specific transformation. It must not import private models from any SaaS
consumer.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from kordena_fiscal.domain import (
    ExecutionScope,
    FiscalValidationError,
    Money,
    SourceReference,
)
from kordena_fiscal.domain.primitives import _required_text


class FiscalOperationKind(StrEnum):
    """Canonical origin families supported by the universal fiscal boundary."""

    SALE = "sale"
    MEMBERSHIP = "membership"
    SUBSCRIPTION = "subscription"
    SERVICE = "service"
    RECURRING_CHARGE = "recurring_charge"
    SAAS_BILLING = "saas_billing"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class FiscalOperationPayment:
    """Provider-neutral payment fact associated with a fiscal operation."""

    method: str
    amount: Money
    reference: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "method",
            _required_text(self.method, "payment_method", max_length=64).lower(),
        )
        if not isinstance(self.amount, Money):
            raise FiscalValidationError("payment amount must be Money")
        if self.amount.amount <= 0:
            raise FiscalValidationError("payment amount must be greater than zero")
        if self.reference is not None:
            normalized = self.reference.strip()
            if len(normalized) > 256:
                raise FiscalValidationError("payment reference exceeds max length 256")
            object.__setattr__(self, "reference", normalized or None)


@dataclass(frozen=True, slots=True)
class FiscalOperationTotals:
    """Neutral economic totals captured before fiscal-document generation."""

    gross_amount: Money
    discount_amount: Money
    surcharge_amount: Money
    net_amount: Money

    def __post_init__(self) -> None:
        values = (
            self.gross_amount,
            self.discount_amount,
            self.surcharge_amount,
            self.net_amount,
        )
        if not all(isinstance(value, Money) for value in values):
            raise FiscalValidationError("operation totals must be Money")
        if any(value.amount < 0 for value in values):
            raise FiscalValidationError("operation totals must be non-negative")
        if self.discount_amount.amount > (
            self.gross_amount.amount + self.surcharge_amount.amount
        ):
            raise FiscalValidationError("discount cannot exceed gross plus surcharge")
        expected_net = (
            self.gross_amount.amount
            - self.discount_amount.amount
            + self.surcharge_amount.amount
        )
        if self.net_amount.amount != expected_net:
            raise FiscalValidationError(
                "net_amount must equal gross_amount - discount_amount + surcharge_amount"
            )

    @classmethod
    def from_net_amount(cls, amount: Money) -> FiscalOperationTotals:
        """Compatibility constructor for legacy snapshots that expose only net total."""

        if not isinstance(amount, Money):
            raise FiscalValidationError("amount must be Money")
        return cls(
            gross_amount=amount,
            discount_amount=Money.zero(),
            surcharge_amount=Money.zero(),
            net_amount=amount,
        )


@dataclass(frozen=True, slots=True)
class FiscalOperationSnapshot:
    """Immutable universal operation snapshot accepted by FM Fiscal."""

    scope: ExecutionScope
    operation_reference: SourceReference
    operation_kind: FiscalOperationKind
    occurred_at: datetime
    totals: FiscalOperationTotals
    payments: tuple[FiscalOperationPayment, ...] = ()
    settled_at: datetime | None = None
    change_amount: Money = Money.zero()

    def __post_init__(self) -> None:
        if not isinstance(self.scope, ExecutionScope):
            raise FiscalValidationError("scope must be ExecutionScope")
        if not isinstance(self.operation_reference, SourceReference):
            raise FiscalValidationError("operation_reference must be SourceReference")
        if not isinstance(self.operation_kind, FiscalOperationKind):
            raise FiscalValidationError("operation_kind must be FiscalOperationKind")
        _require_aware(self.occurred_at, "occurred_at")
        if not isinstance(self.totals, FiscalOperationTotals):
            raise FiscalValidationError("totals must be FiscalOperationTotals")
        if not isinstance(self.payments, tuple) or not all(
            isinstance(payment, FiscalOperationPayment) for payment in self.payments
        ):
            raise FiscalValidationError(
                "payments must be a tuple of FiscalOperationPayment"
            )
        if self.settled_at is not None:
            _require_aware(self.settled_at, "settled_at")
            if self.settled_at < self.occurred_at:
                raise FiscalValidationError("settled_at cannot be before occurred_at")
        if not isinstance(self.change_amount, Money):
            raise FiscalValidationError("change_amount must be Money")
        if self.change_amount.amount < 0:
            raise FiscalValidationError("change_amount must be non-negative")
        if self.change_amount.amount > self.payment_amount.amount:
            raise FiscalValidationError("change_amount cannot exceed payment amount")

    @property
    def payment_amount(self) -> Money:
        total = sum(
            (payment.amount.amount for payment in self.payments),
            Decimal("0"),
        )
        return Money(total)

    @property
    def settled_payment_amount(self) -> Money:
        return self.payment_amount - self.change_amount

    @property
    def is_settled(self) -> bool:
        return self.settled_at is not None


def _require_aware(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise FiscalValidationError(f"{field_name} must be timezone-aware")
    return value
