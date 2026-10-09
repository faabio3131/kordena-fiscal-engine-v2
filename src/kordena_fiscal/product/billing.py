"""Commercial plans, entitlements and usage authority for FM Fiscal.

Commercial billing is deliberately separate from fiscal document authority. A suspended
subscription can block new commercial operations without erasing or hiding legitimate fiscal
history that already exists.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum


class CommercialBillingError(ValueError):
    """Raised when a commercial billing invariant is violated."""


class SubscriptionStatus(StrEnum):
    TRIAL = "trial"
    ACTIVE = "active"
    GRACE = "grace"
    SUSPENDED = "suspended"
    CANCELED = "canceled"


@dataclass(frozen=True, slots=True)
class UsageQuota:
    metric_id: str
    limit: int

    def __post_init__(self) -> None:
        normalized = self.metric_id.strip().lower()
        if not normalized:
            raise CommercialBillingError("metric_id must not be blank")
        if not isinstance(self.limit, int) or isinstance(self.limit, bool) or self.limit < 1:
            raise CommercialBillingError("quota limit must be integer >= 1")
        object.__setattr__(self, "metric_id", normalized)


@dataclass(frozen=True, slots=True)
class CommercialPlan:
    plan_id: str
    entitlement_ids: tuple[str, ...]
    quotas: tuple[UsageQuota, ...] = ()

    def __post_init__(self) -> None:
        normalized = self.plan_id.strip().lower()
        if not normalized:
            raise CommercialBillingError("plan_id must not be blank")
        entitlements = tuple(item.strip().lower() for item in self.entitlement_ids)
        if not entitlements or any(not item for item in entitlements):
            raise CommercialBillingError("plan entitlements must be non-empty")
        if len(entitlements) != len(set(entitlements)):
            raise CommercialBillingError("plan entitlements must be unique")
        quota_ids = tuple(quota.metric_id for quota in self.quotas)
        if len(quota_ids) != len(set(quota_ids)):
            raise CommercialBillingError("plan quota metrics must be unique")
        object.__setattr__(self, "plan_id", normalized)
        object.__setattr__(self, "entitlement_ids", entitlements)

    def quota_for(self, metric_id: str) -> UsageQuota | None:
        normalized = metric_id.strip().lower()
        return next((quota for quota in self.quotas if quota.metric_id == normalized), None)


@dataclass(frozen=True, slots=True)
class UsagePeriodCheckpoint:
    start: datetime
    end: datetime
    usage: tuple[tuple[str, int], ...]

    def __post_init__(self) -> None:
        if (
            self.start.tzinfo is None
            or self.end.tzinfo is None
            or self.start.utcoffset() is None
            or self.end.utcoffset() is None
            or self.end <= self.start
        ):
            raise CommercialBillingError("historical usage period is invalid")
        if len(dict(self.usage)) != len(self.usage) or any(
            not key or not isinstance(amount, int) or isinstance(amount, bool) or amount < 0
            for key, amount in self.usage
        ):
            raise CommercialBillingError("historical usage counters are invalid")


@dataclass(frozen=True, slots=True)
class SubscriptionCheckpoint:
    tenant_id: str
    plan: CommercialPlan
    status: SubscriptionStatus
    period_start: datetime
    period_end: datetime
    usage: tuple[tuple[str, int], ...]
    grace_days: int = 0
    previous_periods: tuple[UsagePeriodCheckpoint, ...] = ()


class CommercialSubscription:
    """In-memory authority contract for commercial entitlement decisions."""

    def __init__(
        self,
        *,
        tenant_id: str,
        plan: CommercialPlan,
        status: SubscriptionStatus,
        period_start: datetime,
        period_end: datetime,
        grace_days: int = 0,
        previous_periods: tuple[UsagePeriodCheckpoint, ...] = (),
    ) -> None:
        normalized_tenant = tenant_id.strip().lower()
        if not normalized_tenant:
            raise CommercialBillingError("tenant_id must not be blank")
        if not isinstance(plan, CommercialPlan):
            raise CommercialBillingError("plan must be CommercialPlan")
        if not isinstance(status, SubscriptionStatus):
            raise CommercialBillingError("status must be SubscriptionStatus")
        if period_start.tzinfo is None or period_start.utcoffset() is None:
            raise CommercialBillingError("period_start must be timezone-aware")
        if period_end.tzinfo is None or period_end.utcoffset() is None:
            raise CommercialBillingError("period_end must be timezone-aware")
        if period_end <= period_start:
            raise CommercialBillingError("period_end must be after period_start")
        self.tenant_id = normalized_tenant
        self.plan = plan
        self.status = status
        self.period_start = period_start
        self.period_end = period_end
        if (
            not isinstance(grace_days, int)
            or isinstance(grace_days, bool)
            or grace_days < 0
        ):
            raise CommercialBillingError("grace_days must be integer >= 0")
        self.grace_days = grace_days
        previous_end = None
        for period in previous_periods:
            if not isinstance(period, UsagePeriodCheckpoint) or period.end > period_start:
                raise CommercialBillingError("historical paid periods overlap current period")
            if previous_end is not None and period.start < previous_end:
                raise CommercialBillingError("historical paid periods overlap")
            previous_end = period.end
        self._previous_periods = list(previous_periods)
        self._usage: dict[str, int] = {}

    @property
    def accepts_new_commercial_operations(self) -> bool:
        return self.accepts_operations_at(datetime.now(UTC))

    def accepts_operations_at(self, at: datetime) -> bool:
        if at.tzinfo is None or at.utcoffset() is None:
            raise CommercialBillingError("operation time must be timezone-aware")
        return (
            self.status
            in {
                SubscriptionStatus.TRIAL,
                SubscriptionStatus.ACTIVE,
                SubscriptionStatus.GRACE,
            }
            and self._usage_period_at(at) is not None
        )

    def _usage_period_at(self, at: datetime) -> int | None:
        if self.period_start <= at < self.period_end:
            return -1
        for index, period in enumerate(self._previous_periods):
            if period.start <= at < period.end:
                return index
        if self.status is SubscriptionStatus.GRACE and self.grace_days:
            try:
                grace_end = self.period_end + timedelta(days=self.grace_days)
            except OverflowError:
                grace_end = datetime.max.replace(tzinfo=self.period_end.tzinfo)
            if self.period_end <= at < grace_end:
                return -1
        return None

    @property
    def preserves_existing_fiscal_state(self) -> bool:
        """Commercial suspension never revokes access needed to preserve fiscal legitimacy."""
        return True

    def has_entitlement(self, entitlement_id: str) -> bool:
        normalized = entitlement_id.strip().lower()
        return normalized in self.plan.entitlement_ids

    def require_entitlement(self, entitlement_id: str, *, at: datetime | None = None) -> None:
        if not self.accepts_operations_at(at or datetime.now(UTC)):
            raise CommercialBillingError(
                f"subscription status blocks new commercial operation: {self.status.value}"
            )
        if not self.has_entitlement(entitlement_id):
            raise CommercialBillingError("commercial entitlement is not granted")

    def record_usage(self, metric_id: str, *, amount: int = 1, at: datetime | None = None) -> int:
        operation_at = at or datetime.now(UTC)
        if not self.accepts_operations_at(operation_at):
            raise CommercialBillingError("subscription does not accept new metered usage")
        if not isinstance(amount, int) or isinstance(amount, bool) or amount < 1:
            raise CommercialBillingError("usage amount must be integer >= 1")
        normalized = metric_id.strip().lower()
        if not normalized:
            raise CommercialBillingError("metric_id must not be blank")
        period_index = self._usage_period_at(operation_at)
        assert period_index is not None
        counters = (
            self._usage if period_index == -1 else dict(self._previous_periods[period_index].usage)
        )
        current = counters.get(normalized, 0)
        candidate = current + amount
        quota = self.plan.quota_for(normalized)
        if quota is not None and candidate > quota.limit:
            raise CommercialBillingError("commercial usage quota exceeded")
        counters[normalized] = candidate
        if period_index != -1:
            period = self._previous_periods[period_index]
            self._previous_periods[period_index] = UsagePeriodCheckpoint(
                period.start,
                period.end,
                tuple(sorted(counters.items())),
            )
        return candidate

    def usage(self, metric_id: str) -> int:
        return self._usage.get(metric_id.strip().lower(), 0)

    def transition(self, target: SubscriptionStatus) -> None:
        if not isinstance(target, SubscriptionStatus):
            raise CommercialBillingError("target must be SubscriptionStatus")
        allowed: dict[SubscriptionStatus, set[SubscriptionStatus]] = {
            SubscriptionStatus.TRIAL: {
                SubscriptionStatus.ACTIVE,
                SubscriptionStatus.GRACE,
                SubscriptionStatus.SUSPENDED,
                SubscriptionStatus.CANCELED,
            },
            SubscriptionStatus.ACTIVE: {
                SubscriptionStatus.GRACE,
                SubscriptionStatus.SUSPENDED,
                SubscriptionStatus.CANCELED,
            },
            SubscriptionStatus.GRACE: {
                SubscriptionStatus.ACTIVE,
                SubscriptionStatus.SUSPENDED,
                SubscriptionStatus.CANCELED,
            },
            SubscriptionStatus.SUSPENDED: {
                SubscriptionStatus.ACTIVE,
                SubscriptionStatus.CANCELED,
            },
            SubscriptionStatus.CANCELED: set(),
        }
        if target is self.status:
            return
        if target not in allowed[self.status]:
            raise CommercialBillingError(
                f"invalid subscription transition: {self.status.value} -> {target.value}"
            )
        self.status = target

    def checkpoint(self) -> SubscriptionCheckpoint:
        return SubscriptionCheckpoint(
            tenant_id=self.tenant_id,
            plan=self.plan,
            status=self.status,
            period_start=self.period_start,
            period_end=self.period_end,
            usage=tuple(sorted(self._usage.items())),
            grace_days=self.grace_days,
            previous_periods=tuple(self._previous_periods),
        )

    @classmethod
    def restore(cls, checkpoint: SubscriptionCheckpoint) -> CommercialSubscription:
        subscription = cls(
            tenant_id=checkpoint.tenant_id,
            plan=checkpoint.plan,
            status=checkpoint.status,
            period_start=checkpoint.period_start,
            period_end=checkpoint.period_end,
            grace_days=checkpoint.grace_days,
            previous_periods=checkpoint.previous_periods,
        )
        subscription._usage = dict(checkpoint.usage)
        return subscription
