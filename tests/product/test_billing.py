from datetime import UTC, datetime, timedelta

import pytest

from kordena_fiscal.product.billing import (
    CommercialBillingError,
    CommercialPlan,
    CommercialSubscription,
    SubscriptionStatus,
    UsageQuota,
)


def subscription(status: SubscriptionStatus = SubscriptionStatus.TRIAL) -> CommercialSubscription:
    start = datetime(2026, 9, 1, tzinfo=UTC)
    return CommercialSubscription(
        tenant_id="tenant-demo",
        plan=CommercialPlan(
            "growth",
            ("documents.issue", "documents.query", "usage.documents"),
            (UsageQuota("usage.documents", 3),),
        ),
        status=status,
        period_start=start,
        period_end=start + timedelta(days=30),
    )


def test_trial_active_and_grace_accept_new_commercial_operations() -> None:
    for status in (
        SubscriptionStatus.TRIAL,
        SubscriptionStatus.ACTIVE,
        SubscriptionStatus.GRACE,
    ):
        assert subscription(status).accepts_new_commercial_operations is True


def test_suspension_blocks_new_usage_but_preserves_existing_fiscal_state() -> None:
    item = subscription(SubscriptionStatus.SUSPENDED)
    assert item.preserves_existing_fiscal_state is True
    with pytest.raises(CommercialBillingError, match="does not accept"):
        item.record_usage("usage.documents")
    with pytest.raises(CommercialBillingError, match="blocks"):
        item.require_entitlement("documents.query")


def test_quota_is_enforced_fail_closed() -> None:
    item = subscription()
    assert item.record_usage("usage.documents", amount=2) == 2
    assert item.record_usage("usage.documents") == 3
    with pytest.raises(CommercialBillingError, match="quota exceeded"):
        item.record_usage("usage.documents")
    assert item.usage("usage.documents") == 3


def test_entitlement_is_separate_from_fiscal_readiness() -> None:
    item = subscription()
    item.require_entitlement("documents.issue")
    assert not hasattr(item, "production_approved")
    assert not hasattr(item.plan, "fiscal_readiness")


def test_missing_entitlement_fails_closed() -> None:
    with pytest.raises(CommercialBillingError, match="not granted"):
        subscription().require_entitlement("support.premium")


def test_grace_suspend_and_reactivate_transitions() -> None:
    item = subscription(SubscriptionStatus.ACTIVE)
    item.transition(SubscriptionStatus.GRACE)
    item.transition(SubscriptionStatus.SUSPENDED)
    item.transition(SubscriptionStatus.ACTIVE)
    assert item.status is SubscriptionStatus.ACTIVE


def test_canceled_subscription_cannot_reactivate() -> None:
    item = subscription(SubscriptionStatus.ACTIVE)
    item.transition(SubscriptionStatus.CANCELED)
    with pytest.raises(CommercialBillingError, match="invalid subscription transition"):
        item.transition(SubscriptionStatus.ACTIVE)


def test_checkpoint_restore_preserves_usage_and_status() -> None:
    item = subscription(SubscriptionStatus.ACTIVE)
    item.record_usage("usage.documents", amount=2)
    restored = CommercialSubscription.restore(item.checkpoint())
    assert restored.status is SubscriptionStatus.ACTIVE
    assert restored.usage("usage.documents") == 2


def test_invalid_period_and_quota_are_rejected() -> None:
    start = datetime(2026, 9, 1, tzinfo=UTC)
    plan = CommercialPlan("foundation", ("documents.query",))
    with pytest.raises(CommercialBillingError, match="after period_start"):
        CommercialSubscription(
            tenant_id="tenant",
            plan=plan,
            status=SubscriptionStatus.TRIAL,
            period_start=start,
            period_end=start,
        )
    with pytest.raises(CommercialBillingError, match="integer >= 1"):
        UsageQuota("usage.documents", 0)
