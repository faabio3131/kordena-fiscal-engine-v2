"""Read-only canonical commercial projections for the human Portal.

This service exposes canonical subscription, usage and published pricing state without
creating a second billing authority. External providers remain adapters; tenant
authority comes from the authenticated session at the web boundary.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from typing import Protocol

from kordena_fiscal.control_plane.pricing_admin import CommercialPricingAdministrationService
from kordena_fiscal.product.commercial_fulfillment import (
    CanonicalCommercialUnitOfWorkFactory,
    DurableCommercialSubscription,
)
from kordena_fiscal.product.pricing import CommercialPricingError


class CommercialPortalReadError(RuntimeError):
    """Raised when canonical commercial state cannot be projected safely."""


class CommercialPortalReader(Protocol):
    def surface(
        self,
        *,
        surface_id: str,
        tenant_id: str,
    ) -> Sequence[Mapping[str, object]]: ...


class CommercialPortalReadService:
    """Project billing/plans/usage from canonical NFCore commercial authorities."""

    _SURFACES = frozenset({"billing", "plans", "usage"})

    def __init__(
        self,
        *,
        unit_of_work_factory: CanonicalCommercialUnitOfWorkFactory,
        pricing: CommercialPricingAdministrationService,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._pricing = pricing
        self._now = now or (lambda: datetime.now(UTC))

    def surface(
        self,
        *,
        surface_id: str,
        tenant_id: str,
    ) -> Sequence[Mapping[str, object]]:
        if surface_id not in self._SURFACES:
            raise ValueError("unsupported commercial portal surface")
        normalized_tenant = tenant_id.strip().lower()
        if not normalized_tenant:
            raise ValueError("tenant_id must not be blank")

        with self._unit_of_work_factory() as uow:
            subscription = uow.commercial.get_subscription_for_tenant(normalized_tenant)

        if surface_id == "billing":
            return self._billing_rows(subscription)
        if surface_id == "usage":
            return self._usage_rows(subscription)
        return self._plan_rows(normalized_tenant, subscription)

    @staticmethod
    def _billing_rows(
        subscription: DurableCommercialSubscription | None,
    ) -> tuple[Mapping[str, object], ...]:
        if subscription is None:
            return ()
        checkpoint = subscription.checkpoint
        return (
            {
                "subscription_id": subscription.subscription_id,
                "plan_id": checkpoint.plan.plan_id,
                "status": checkpoint.status.value,
                "entitlement_ids": sorted(checkpoint.plan.entitlement_ids),
                "period_start": checkpoint.period_start.isoformat(),
                "period_end": checkpoint.period_end.isoformat(),
                "source": "canonical_subscription",
            },
        )

    @staticmethod
    def _usage_rows(
        subscription: DurableCommercialSubscription | None,
    ) -> tuple[Mapping[str, object], ...]:
        if subscription is None:
            return ()
        checkpoint = subscription.checkpoint
        usage = dict(checkpoint.usage)
        quotas = {quota.metric_id: quota.limit for quota in checkpoint.plan.quotas}
        metric_ids = sorted(set(usage) | set(quotas))
        rows: list[Mapping[str, object]] = []
        for metric_id in metric_ids:
            used = usage.get(metric_id, 0)
            limit = quotas.get(metric_id)
            remaining = None if limit is None else max(limit - used, 0)
            rows.append(
                {
                    "metric_id": metric_id,
                    "used": used,
                    "limit": limit,
                    "remaining": remaining,
                    "status": (
                        "unmetered"
                        if limit is None
                        else "quota_reached"
                        if used >= limit
                        else "within_quota"
                    ),
                    "period_start": checkpoint.period_start.isoformat(),
                    "period_end": checkpoint.period_end.isoformat(),
                }
            )
        return tuple(rows)

    def _plan_rows(
        self,
        tenant_id: str,
        subscription: DurableCommercialSubscription | None,
    ) -> tuple[Mapping[str, object], ...]:
        catalog = self._pricing.current
        if catalog is None:
            return ()

        instant = self._now()
        if instant.tzinfo is None or instant.utcoffset() is None:
            raise CommercialPortalReadError("commercial projection clock must be timezone-aware")

        current_plan_id = (
            None if subscription is None else subscription.checkpoint.plan.plan_id
        )
        rows: list[Mapping[str, object]] = []
        for plan in sorted(catalog.plans, key=lambda item: item.plan_id):
            if not plan.enabled:
                continue
            for price_id in plan.price_ids:
                if not catalog.price(price_id).enabled:
                    continue
                try:
                    resolved = catalog.resolve_price(
                        price_id,
                        at=instant,
                        tenant_id=tenant_id,
                    )
                except CommercialPricingError as exc:
                    raise CommercialPortalReadError(
                        "published pricing cannot be projected safely"
                    ) from exc
                rows.append(
                    {
                        "plan_id": plan.plan_id,
                        "display_name": plan.display_name,
                        "edition_id": plan.edition_id,
                        "price_id": resolved.price_id,
                        "currency": resolved.currency,
                        "cadence": resolved.cadence.value,
                        "base_amount": str(resolved.base_amount),
                        "per_document_amount": str(resolved.per_document_amount),
                        "setup_amount": str(resolved.setup_amount),
                        "current": plan.plan_id == current_plan_id,
                        "catalog_version": catalog.version,
                        "source": "published_pricing_catalog",
                    }
                )
        return tuple(rows)
