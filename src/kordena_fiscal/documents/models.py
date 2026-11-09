"""Provider-neutral canonical fiscal document model."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from kordena_fiscal.domain import (
    Cnpj,
    ExecutionScope,
    FiscalDocumentKind,
    FiscalProductProfile,
    FiscalProfile,
    FiscalValidationError,
    Money,
    SourceReference,
)
from kordena_fiscal.tax import RestaurantSupplyDecision, TaxDecision

from .recipient import FiscalRecipientSnapshot


class PaymentMethodKind(StrEnum):
    """Canonical payment families; provider/SEFAZ codes are adapter concerns."""

    CASH = "cash"
    CREDIT_CARD = "credit_card"
    DEBIT_CARD = "debit_card"
    PIX = "pix"
    VOUCHER = "voucher"
    BOLETO = "boleto"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class FiscalPaymentSnapshot:
    """Immutable payment fact captured from the host operation."""

    method: PaymentMethodKind
    amount: Money
    provider_reference: str | None = None
    card_acquirer_cnpj: str | None = None
    card_brand: str | None = None
    card_authorization: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.method, PaymentMethodKind):
            raise FiscalValidationError("method must be a PaymentMethodKind")
        if not isinstance(self.amount, Money):
            raise FiscalValidationError("payment amount must be Money")
        if self.amount.amount <= 0:
            raise FiscalValidationError("payment amount must be greater than zero")
        card_facts = (self.card_acquirer_cnpj, self.card_brand, self.card_authorization)
        if any(value is not None for value in card_facts):
            if self.method not in {PaymentMethodKind.CREDIT_CARD, PaymentMethodKind.DEBIT_CARD}:
                raise FiscalValidationError("card facts require a card payment")
            if not all(isinstance(value, str) and value for value in card_facts):
                raise FiscalValidationError("integrated card facts must be complete")
            assert self.card_acquirer_cnpj is not None
            assert self.card_brand is not None
            assert self.card_authorization is not None
            Cnpj(self.card_acquirer_cnpj)
            if not re.fullmatch(r"[0-9]{2}", self.card_brand):
                raise FiscalValidationError("card brand must contain two digits")
            if not re.fullmatch(r"[A-Za-z0-9-]{1,128}", self.card_authorization):
                raise FiscalValidationError("invalid card authorization")
        if self.provider_reference is not None:
            normalized = self.provider_reference.strip()
            if not normalized:
                object.__setattr__(self, "provider_reference", None)
            elif len(normalized) > 256:
                raise FiscalValidationError("provider_reference exceeds max length 256")
            else:
                object.__setattr__(self, "provider_reference", normalized)


@dataclass(frozen=True, slots=True)
class FiscalLineSnapshot:
    """One immutable fiscal line with frozen product and tax decision snapshots."""

    line_number: int
    product: FiscalProductProfile
    quantity: Decimal
    unit_price: Money
    gross_amount: Money
    tax_decision: TaxDecision
    discount_amount: Money = Money.zero()
    surcharge_amount: Money = Money.zero()
    restaurant_decision: RestaurantSupplyDecision | None = None
    freight_amount: Money = Money.zero()
    taxable_quantity: Decimal | None = None
    taxable_unit_price: Decimal | None = None

    def __post_init__(self) -> None:
        if self.line_number < 1:
            raise FiscalValidationError("line_number must be >= 1")
        if not isinstance(self.product, FiscalProductProfile):
            raise FiscalValidationError("product must be FiscalProductProfile")
        if not isinstance(self.quantity, Decimal) or not self.quantity.is_finite():
            raise FiscalValidationError("quantity must be a finite Decimal")
        if self.quantity <= 0:
            raise FiscalValidationError("quantity must be greater than zero")
        if (self.taxable_quantity is None) != (self.taxable_unit_price is None):
            raise FiscalValidationError("taxable quantity and unit price must be supplied together")
        for value in (self.taxable_quantity, self.taxable_unit_price):
            if value is not None and (
                not isinstance(value, Decimal) or not value.is_finite() or value < 0
            ):
                raise FiscalValidationError(
                    "taxable conversion values must be non-negative decimals"
                )
        if self.taxable_quantity is not None and self.taxable_quantity == 0:
            raise FiscalValidationError("taxable quantity must be positive")
        monetary_values = (
            self.unit_price,
            self.gross_amount,
            self.discount_amount,
            self.surcharge_amount,
        )
        if not all(isinstance(value, Money) for value in monetary_values):
            raise FiscalValidationError("line monetary values must be Money")
        if any(value.amount < 0 for value in monetary_values):
            raise FiscalValidationError("line monetary values must be non-negative")
        if self.discount_amount.amount > (self.gross_amount.amount + self.surcharge_amount.amount):
            raise FiscalValidationError("discount cannot exceed gross plus surcharge")
        if not isinstance(self.freight_amount, Money) or not (
            0 <= self.freight_amount.amount <= self.surcharge_amount.amount
        ):
            raise FiscalValidationError("freight must be included in line surcharges")
        if not isinstance(self.tax_decision, TaxDecision):
            raise FiscalValidationError("tax_decision must be TaxDecision")
        if self.restaurant_decision is not None and not isinstance(
            self.restaurant_decision,
            RestaurantSupplyDecision,
        ):
            raise FiscalValidationError(
                "restaurant_decision must be RestaurantSupplyDecision when provided"
            )

    @property
    def net_amount(self) -> Money:
        return Money(
            self.gross_amount.amount - self.discount_amount.amount + self.surcharge_amount.amount
        )


@dataclass(frozen=True, slots=True)
class FiscalDocumentTotals:
    """Deterministic totals derived from immutable document snapshots."""

    gross_amount: Money
    discount_amount: Money
    surcharge_amount: Money
    net_amount: Money
    payment_amount: Money
    change_amount: Money


@dataclass(frozen=True, slots=True)
class CanonicalFiscalDocument:
    """Internal fiscal truth independent of XML schema or external provider JSON."""

    document_id: str
    scope: ExecutionScope
    source: SourceReference
    document_kind: FiscalDocumentKind
    issued_at: datetime
    issuer: FiscalProfile
    items: tuple[FiscalLineSnapshot, ...]
    payments: tuple[FiscalPaymentSnapshot, ...] = ()
    change_amount: Money = Money.zero()
    schema_version: int = 1
    recipient: FiscalRecipientSnapshot | None = None

    def __post_init__(self) -> None:
        document_id = self.document_id.strip()
        if not document_id:
            raise FiscalValidationError("document_id must not be blank")
        if len(document_id) > 128:
            raise FiscalValidationError("document_id exceeds max length 128")
        object.__setattr__(self, "document_id", document_id)

        if not isinstance(self.scope, ExecutionScope):
            raise FiscalValidationError("scope must be ExecutionScope")
        if not isinstance(self.source, SourceReference):
            raise FiscalValidationError("source must be SourceReference")
        if not isinstance(self.document_kind, FiscalDocumentKind):
            raise FiscalValidationError("document_kind must be FiscalDocumentKind")
        if self.issued_at.tzinfo is None or self.issued_at.utcoffset() is None:
            raise FiscalValidationError("issued_at must be timezone-aware")
        if not isinstance(self.issuer, FiscalProfile):
            raise FiscalValidationError("issuer must be FiscalProfile")
        if self.issuer.scope.identity_partition_key != self.scope.identity_partition_key:
            raise FiscalValidationError("issuer and document must share the same identity scope")
        if not self.issuer.is_effective_at(self.issued_at):
            raise FiscalValidationError("issuer fiscal profile is not effective at issued_at")
        if not self.items:
            raise FiscalValidationError("canonical fiscal document requires at least one item")
        if not all(isinstance(item, FiscalLineSnapshot) for item in self.items):
            raise FiscalValidationError("items must contain FiscalLineSnapshot values")

        line_numbers = [item.line_number for item in self.items]
        if len(line_numbers) != len(set(line_numbers)):
            raise FiscalValidationError("line_number values must be unique")
        for item in self.items:
            if item.product.scope.identity_partition_key != self.scope.identity_partition_key:
                raise FiscalValidationError(
                    "item product and document must share the same identity scope"
                )
            if not item.product.is_effective_at(self.issued_at):
                raise FiscalValidationError(
                    "item product fiscal profile is not effective at issued_at"
                )

        if not all(isinstance(payment, FiscalPaymentSnapshot) for payment in self.payments):
            raise FiscalValidationError("payments must contain FiscalPaymentSnapshot values")
        if not isinstance(self.change_amount, Money):
            raise FiscalValidationError("change_amount must be Money")
        if self.change_amount.amount < 0:
            raise FiscalValidationError("change_amount must be non-negative")
        payment_total = sum(
            (payment.amount.amount for payment in self.payments),
            Decimal("0"),
        )
        if self.change_amount.amount > payment_total:
            raise FiscalValidationError("change_amount cannot exceed payment amount")
        if self.recipient is not None and not isinstance(self.recipient, FiscalRecipientSnapshot):
            raise FiscalValidationError("recipient must be an immutable fiscal snapshot")
        if self.schema_version < 1:
            raise FiscalValidationError("schema_version must be >= 1")

    @property
    def totals(self) -> FiscalDocumentTotals:
        gross = sum((item.gross_amount.amount for item in self.items), Decimal("0"))
        discounts = sum(
            (item.discount_amount.amount for item in self.items),
            Decimal("0"),
        )
        surcharges = sum(
            (item.surcharge_amount.amount for item in self.items),
            Decimal("0"),
        )
        payments = sum(
            (payment.amount.amount for payment in self.payments),
            Decimal("0"),
        )
        return FiscalDocumentTotals(
            gross_amount=Money(gross),
            discount_amount=Money(discounts),
            surcharge_amount=Money(surcharges),
            net_amount=Money(gross - discounts + surcharges),
            payment_amount=Money(payments),
            change_amount=self.change_amount,
        )
