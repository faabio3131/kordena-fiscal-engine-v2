"""Deterministic NFCore v2 plan limits. Requires trusted durable counters.

This does not itself reserve quota or authorize fiscal emission. A caller must
bind these checks inside its existing atomic ledger transaction BEFORE any
external work; missing counters/unknown plan are denied, not estimated.
"""
from __future__ import annotations

from dataclasses import dataclass

from kordena_fiscal.product.commercial_plan_candidate import read_candidate
from kordena_fiscal.product.pricing import CommercialPricingError


@dataclass(frozen=True, slots=True)
class CommercialPlanQuota:
    plan_id: str
    catalog_version: int
    monthly_documents: int | None
    max_cnpjs: int | None
    rpm: int | None
    trial_documents_total: int | None

    def require_cnpj_registration(self, *, distinct_cnpjs: int, new_cnpj: bool) -> None:
        _nonnegative(distinct_cnpjs, "registered CNPJ count")
        if self.max_cnpjs is not None and new_cnpj and distinct_cnpjs >= self.max_cnpjs:
            raise CommercialPricingError("commercial CNPJ limit reached")

    def require_document_reservation(
        self, *, used_documents: int, in_flight_reservations: int
    ) -> None:
        _nonnegative(used_documents, "used document count")
        _nonnegative(in_flight_reservations, "pending document reservations")
        maximum = self.trial_documents_total
        if maximum is None:
            maximum = self.monthly_documents
        if maximum is not None and used_documents + in_flight_reservations >= maximum:
            raise CommercialPricingError("commercial document quota reached")

    def require_request_reservation(
        self, *, observed_last_60_seconds: int, in_flight_reservations: int
    ) -> None:
        _nonnegative(observed_last_60_seconds, "RPM usage")
        _nonnegative(in_flight_reservations, "RPM pending reservations")
        if self.rpm is not None and observed_last_60_seconds + in_flight_reservations >= self.rpm:
            raise CommercialPricingError("commercial RPM limit reached")


def _nonnegative(value: int, label: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise CommercialPricingError(f"{label} must be a trustworthy nonnegative integer")


def resolve_plan_quota(*, plan_id: str, catalog_version: int, status: str) -> CommercialPlanQuota:
    """No default plan, no site-selected limit, no unknown subscription fallback."""
    catalog = read_candidate()
    if (catalog_version != catalog["version"] or
            status not in {"trial", "active", "grace"}):
        raise CommercialPricingError("commercial plan snapshot not authorized")
    plans = catalog["plans"]
    assert isinstance(plans, dict)
    item = plans.get(plan_id)
    if not isinstance(item, dict):
        raise CommercialPricingError("unknown commercial plan")
    trial = catalog["trial"]
    assert isinstance(trial, dict)
    return CommercialPlanQuota(
        plan_id=plan_id,
        catalog_version=catalog_version,
        monthly_documents=item["included_documents"],
        max_cnpjs=item["max_cnpjs"],
        rpm=item["api_rate_limit_rpm"],
        trial_documents_total=(
            int(trial["production_docs_limit"]) if status == "trial" else None
        ),
    )
