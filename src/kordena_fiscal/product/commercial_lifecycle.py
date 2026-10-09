"""Canonical contracted terms and invoice-backed paid periods (T05-B01)."""

from __future__ import annotations

import calendar
from dataclasses import dataclass, replace
from datetime import datetime, timedelta

from kordena_fiscal.product.billing import CommercialPlan, SubscriptionStatus
from kordena_fiscal.product.commercial_fulfillment import CommercialFulfillmentError
from kordena_fiscal.product.pricing import BillingCadence


def period_end(start: datetime, cadence: BillingCadence) -> datetime:
    months = {
        BillingCadence.MONTHLY: 1,
        BillingCadence.QUARTERLY: 3,
        BillingCadence.SEMIANNUAL: 6,
        BillingCadence.ANNUAL: 12,
    }.get(cadence)
    if months is None:
        if cadence is BillingCadence.ONE_TIME:
            return datetime.max.replace(tzinfo=start.tzinfo)
        raise CommercialFulfillmentError("unsupported billing cadence")
    index = start.month - 1 + months
    year, month = start.year + index // 12, index % 12 + 1
    return start.replace(
        year=year, month=month, day=min(start.day, calendar.monthrange(year, month)[1])
    )


@dataclass(frozen=True, slots=True)
class PaidCommercialPeriod:
    invoice_id: str
    paid_at: datetime
    start: datetime
    end: datetime
    renewal: bool = False
    usage: tuple[tuple[str, int], ...] = ()

    def __post_init__(self) -> None:
        if (
            not isinstance(self.invoice_id, str)
            or not self.invoice_id
            or len(self.invoice_id) > 320
        ):
            raise CommercialFulfillmentError("paid invoice identity is invalid")
        if not isinstance(self.renewal, bool):
            raise CommercialFulfillmentError("paid period renewal flag must be boolean")
        for value in (self.paid_at, self.start, self.end):
            if value.tzinfo is None or value.utcoffset() is None:
                raise CommercialFulfillmentError("paid period must be timezone-aware")
        if self.end <= self.start:
            raise CommercialFulfillmentError("paid period end must follow start")
        if len(dict(self.usage)) != len(self.usage) or any(
            not key or not isinstance(value, int) or isinstance(value, bool) or value < 0
            for key, value in self.usage
        ):
            raise CommercialFulfillmentError("paid period usage is invalid")


@dataclass(frozen=True, slots=True)
class CommercialContract:
    purchase_id: str
    plan: CommercialPlan
    cadence: BillingCadence
    grace_days: int
    pricing_configuration_id: str
    pricing_version: int
    periods: tuple[PaidCommercialPeriod, ...]

    def __post_init__(self) -> None:
        if (
            not isinstance(self.purchase_id, str)
            or not self.purchase_id
            or not isinstance(self.plan, CommercialPlan)
            or not isinstance(self.cadence, BillingCadence)
            or not isinstance(self.pricing_configuration_id, str)
            or not self.pricing_configuration_id
            or not isinstance(self.pricing_version, int)
            or isinstance(self.pricing_version, bool)
            or self.pricing_version < 1
        ):
            raise CommercialFulfillmentError("contracted snapshot metadata is invalid")
        if (
            not isinstance(self.grace_days, int)
            or isinstance(self.grace_days, bool)
            or self.grace_days < 0
        ):
            raise CommercialFulfillmentError("contract grace_days must be >= 0")
        if not self.periods or len({p.invoice_id for p in self.periods}) != len(self.periods):
            raise CommercialFulfillmentError("contract requires unique paid invoices")
        for previous, current in zip(self.periods, self.periods[1:], strict=False):
            if current.start < previous.end:
                raise CommercialFulfillmentError("paid periods must not overlap")

    def covers(self, status: SubscriptionStatus | None, at: datetime) -> bool:
        if at.tzinfo is None or at.utcoffset() is None:
            raise CommercialFulfillmentError("commercial operation time must be aware")
        if status not in {
            SubscriptionStatus.ACTIVE,
            SubscriptionStatus.TRIAL,
            SubscriptionStatus.GRACE,
        }:
            return False
        if any(p.start <= at < p.end for p in self.periods):
            return True
        last = self.periods[-1]
        # Only the explicitly configured grace after the latest paid coverage.
        if status is not SubscriptionStatus.GRACE or self.grace_days == 0:
            return False
        try:
            end = last.end + timedelta(days=self.grace_days)
        except OverflowError:
            end = datetime.max.replace(tzinfo=last.end.tzinfo)
        return last.end <= at < end

    def renew(self, invoice_id: str, paid_at: datetime) -> tuple[CommercialContract, bool]:
        existing = next((p for p in self.periods if p.invoice_id == invoice_id), None)
        if existing is not None:
            if not existing.renewal or existing.paid_at != paid_at:
                raise CommercialFulfillmentError("paid invoice conflicts with credited period")
            return self, True
        if self.cadence is BillingCadence.ONE_TIME:
            raise CommercialFulfillmentError("one-time contract cannot renew")
        start = max(self.periods[-1].end, paid_at)
        return replace(
            self,
            periods=(
                *self.periods,
                PaidCommercialPeriod(
                    invoice_id=invoice_id,
                    paid_at=paid_at,
                    start=start,
                    end=period_end(start, self.cadence),
                    renewal=True,
                ),
            ),
        ), False
