from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from kordena_fiscal.application.commercial_portal import CommercialPortalReadService
from kordena_fiscal.control_plane.models import AdminPrincipal, ControlPlanePermission
from kordena_fiscal.control_plane.pricing_admin import CommercialPricingAdministrationService
from kordena_fiscal.product.billing import (
    CommercialPlan,
    CommercialSubscription,
    SubscriptionStatus,
    UsageQuota,
)
from kordena_fiscal.product.commercial_fulfillment import DurableCommercialSubscription
from kordena_fiscal.product.pricing import (
    BillingCadence,
    CommercialPricingConfiguration,
    CommercialPricingRegistry,
    PlanDefinition,
    PriceDefinition,
    TenantPriceOverride,
)

NOW = datetime(2026, 10, 7, 18, 30, tzinfo=UTC)


class MemoryStore:
    def __init__(self, subscription: DurableCommercialSubscription | None) -> None:
        self.subscription = subscription

    def get_subscription_for_tenant(
        self, tenant_id: str
    ) -> DurableCommercialSubscription | None:
        value = self.subscription
        if value is None or value.checkpoint.tenant_id != tenant_id:
            return None
        return value


class MemoryUow:
    def __init__(self, store: MemoryStore) -> None:
        self.commercial = store

    def __enter__(self) -> MemoryUow:
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def commit(self) -> None:
        return None


class MemoryFactory:
    def __init__(self, store: MemoryStore) -> None:
        self.store = store

    def __call__(self) -> MemoryUow:
        return MemoryUow(self.store)


def durable_subscription() -> DurableCommercialSubscription:
    subscription = CommercialSubscription(
        tenant_id="tenant-a",
        plan=CommercialPlan(
            plan_id="growth",
            entitlement_ids=("documents.issue", "documents.query"),
            quotas=(UsageQuota("documents", 1000),),
        ),
        status=SubscriptionStatus.ACTIVE,
        period_start=NOW,
        period_end=NOW + timedelta(days=30),
    )
    subscription.record_usage("documents", amount=125, at=NOW)
    return DurableCommercialSubscription(
        subscription_id="subscription-a",
        purchase_id="purchase-a",
        checkpoint=subscription.checkpoint(),
        provider_id="adapter-x",
        external_subscription_id="external-secret-shaped-reference",
        last_event_id="event-a",
        last_event_at=NOW,
    )


def pricing() -> CommercialPricingAdministrationService:
    service = CommercialPricingAdministrationService(CommercialPricingRegistry())
    service.publish(
        actor=AdminPrincipal(
            actor_id="pricing-admin",
            permissions=frozenset({ControlPlanePermission.COMMERCIAL_CONFIG_WRITE}),
            global_scope=True,
        ),
        configuration=CommercialPricingConfiguration(
            configuration_id="test-pricing",
            version=1,
            prices=(
                PriceDefinition(
                    price_id="growth-monthly",
                    currency="BRL",
                    cadence=BillingCadence.MONTHLY,
                    base_amount=Decimal("199.00"),
                    per_document_amount=Decimal("0.10"),
                ),
            ),
            plans=(
                PlanDefinition(
                    plan_id="growth",
                    display_name="Growth",
                    edition_id="growth",
                    price_ids=("growth-monthly",),
                ),
            ),
            tenant_overrides=(
                TenantPriceOverride(
                    override_id="tenant-a-growth",
                    tenant_id="tenant-a",
                    price_id="growth-monthly",
                    base_amount=Decimal("149.00"),
                ),
            ),
        ),
        expected_version=None,
        correlation_id="test-pricing-v1",
        published_at=NOW,
    )
    return service


def test_billing_and_usage_project_only_canonical_tenant_state() -> None:
    reader = CommercialPortalReadService(
        unit_of_work_factory=MemoryFactory(MemoryStore(durable_subscription())),
        pricing=pricing(),
        now=lambda: NOW,
    )

    billing = reader.surface(surface_id="billing", tenant_id="tenant-a")
    assert billing == (
        {
            "subscription_id": "subscription-a",
            "plan_id": "growth",
            "status": "active",
            "entitlement_ids": ["documents.issue", "documents.query"],
            "period_start": NOW.isoformat(),
            "period_end": (NOW + timedelta(days=30)).isoformat(),
            "source": "canonical_subscription",
        },
    )
    rendered = repr(billing).lower()
    assert "adapter-x" not in rendered
    assert "external-secret-shaped-reference" not in rendered

    usage = reader.surface(surface_id="usage", tenant_id="tenant-a")
    assert usage == (
        {
            "metric_id": "documents",
            "used": 125,
            "limit": 1000,
            "remaining": 875,
            "status": "within_quota",
            "period_start": NOW.isoformat(),
            "period_end": (NOW + timedelta(days=30)).isoformat(),
        },
    )
    assert reader.surface(surface_id="billing", tenant_id="tenant-b") == ()


def test_plans_use_published_catalog_and_tenant_override_without_provider_authority() -> None:
    reader = CommercialPortalReadService(
        unit_of_work_factory=MemoryFactory(MemoryStore(durable_subscription())),
        pricing=pricing(),
        now=lambda: NOW,
    )

    rows = reader.surface(surface_id="plans", tenant_id="tenant-a")
    assert rows == (
        {
            "plan_id": "growth",
            "display_name": "Growth",
            "edition_id": "growth",
            "price_id": "growth-monthly",
            "currency": "BRL",
            "cadence": "monthly",
            "base_amount": "149.00",
            "per_document_amount": "0.10",
            "setup_amount": "0.00",
            "current": True,
            "catalog_version": 1,
            "source": "published_pricing_catalog",
        },
    )
    assert "external_price_reference" not in rows[0]
    assert "contract_reference" not in rows[0]


def test_missing_canonical_state_returns_empty_rows_instead_of_fabricating_status() -> None:
    reader = CommercialPortalReadService(
        unit_of_work_factory=MemoryFactory(MemoryStore(None)),
        pricing=CommercialPricingAdministrationService(CommercialPricingRegistry()),
        now=lambda: NOW,
    )
    assert reader.surface(surface_id="billing", tenant_id="tenant-a") == ()
    assert reader.surface(surface_id="usage", tenant_id="tenant-a") == ()
    assert reader.surface(surface_id="plans", tenant_id="tenant-a") == ()
