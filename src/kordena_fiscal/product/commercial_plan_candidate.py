"""Versioned, runtime-gated commercial catalog using existing pricing and quota authorities.

Git publication is not a pricing-admin database publication or commercial release.
Actual invoices must use canonical metered usage, subscription and payment ledgers.
"""

from __future__ import annotations

import json
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from kordena_fiscal.product.pricing import (
    BillingCadence,
    CommercialPricingConfiguration,
    CommercialPricingError,
    PlanDefinition,
    PriceDefinition,
)

_DEFAULT = Path.cwd() / "config" / "commercial" / "plans.json"
_CENT = Decimal("0.01")


def _money(value: object) -> Decimal:
    if not isinstance(value, str):
        raise CommercialPricingError("monetary amount must be a decimal string")
    try:
        amount = Decimal(value)
    except (ValueError, ArithmeticError) as exc:
        raise CommercialPricingError("monetary amount is invalid") from exc
    exponent = amount.as_tuple().exponent
    if not amount.is_finite() or amount < 0 or not isinstance(exponent, int) or exponent < -2:
        raise CommercialPricingError("monetary amount must be finite and in cents")
    return amount


def _positive_int(value: object, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise CommercialPricingError(f"{label} must be integer >= 1")
    return value


def read_candidate(path: Path = _DEFAULT) -> dict[str, object]:
    """Untrusted configuration load; duplicate keys and invalid status denied."""

    def unique_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise CommercialPricingError("duplicate commercial configuration key")
            result[key] = value
        return result

    try:
        data = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_pairs)
    except CommercialPricingError:
        raise
    except (OSError, ValueError, UnicodeError) as exc:
        raise CommercialPricingError("commercial candidate file unavailable or invalid") from exc
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise CommercialPricingError("unsupported commercial candidate schema")
    if data.get("status") != "PUBLISHED_CATALOG_RUNTIME_GATED":
        raise CommercialPricingError("candidate status invalid")
    if data.get("policy") != "consumption_based_total_feature_parity":
        raise CommercialPricingError("candidate policy invalid")
    trial = data.get("trial")
    if not isinstance(trial, dict):
        raise CommercialPricingError("trial settings absent")
    if _positive_int(trial.get("duration_days"), "trial duration") != 14:
        raise CommercialPricingError("trial duration differs from approved proposal")
    if trial.get("requires_credit_card") is not False:
        raise CommercialPricingError("trial requires no credit card")
    if trial.get("production_fiscal_activation_required") is not True:
        raise CommercialPricingError("fiscal activation gate must be preserved")
    if trial.get("external_homologation_required") is not True:
        raise CommercialPricingError("external homologation gate must be preserved")
    if trial.get("homologation_docs_limit") is not None:
        raise CommercialPricingError("homologation limit is not a bypass to provider gates")
    if _positive_int(trial.get("production_docs_limit"), "trial documents") != 50:
        raise CommercialPricingError("trial documents differ from approved proposal")
    publication = data.get("publication")
    if not isinstance(publication, dict) or publication.get("runtime_activated") is not False:
        raise CommercialPricingError("catalog publication cannot self-activate runtime")
    if publication.get("requires_commercial_release_authority") is not True:
        raise CommercialPricingError("release authority cannot be bypassed")
    policy = data.get("commercial_policy")
    if not isinstance(policy, dict) or policy.get("annual_prices_enabled") is not False or policy.get("overage_charging_enabled") is not False:
        raise CommercialPricingError("unapproved prices must remain disabled")
    return data


def build_canonical_candidate(
    path: Path = _DEFAULT,
) -> CommercialPricingConfiguration:
    """Adapt approved proposal to the EXISTING pricing configuration model."""
    data = read_candidate(path)
    raw_plans = data.get("plans")
    if not isinstance(raw_plans, dict) or set(raw_plans) != {
        "starter",
        "pro",
        "business",
        "enterprise",
    }:
        raise CommercialPricingError("four approved plan IDs required")
    prices: list[PriceDefinition] = []
    plans: list[PlanDefinition] = []
    for key, item in raw_plans.items():
        if not isinstance(item, dict) or not isinstance(item.get("name"), str):
            raise CommercialPricingError("plan entry invalid")
        if key == "enterprise":
            if item.get("included_documents") is not None:
                raise CommercialPricingError("enterprise volume must be uncapped")
        else:
            _positive_int(item.get("included_documents"), "included documents")
        _money(item.get("overage_unit_price_brl"))
        cnpj_limit = item.get("max_cnpjs")
        if cnpj_limit is not None:
            _positive_int(cnpj_limit, "CNPJ quota")
        rpm = item.get("api_rate_limit_rpm")
        if rpm is not None:
            _positive_int(rpm, "RPM quota")
        features = item.get("features")
        if not isinstance(features, dict) or features.get("all_features_enabled") is not True:
            raise CommercialPricingError("feature parity violation")
        if (cnpj_limit is None or rpm is None) and key != "enterprise":
            raise CommercialPricingError("unbounded quota not allowed outside enterprise")
        monthly = _money(item.get("monthly_price_brl"))
        annual_monthly = _money(item.get("annual_monthly_price_brl"))
        for cadence, base in (
            (BillingCadence.MONTHLY, monthly),
            (BillingCadence.ANNUAL, annual_monthly * 12),
        ):
            prices.append(
                PriceDefinition(
                    price_id=f"nfcore-{key}-{cadence.value}-candidate",
                    currency="BRL",
                    cadence=cadence,
                    base_amount=base,
                    per_document_amount=Decimal("0.00"),
                    enabled=cadence is BillingCadence.MONTHLY,
                )
            )
        # Included volume and per-minute throttling are NOT period-hard quotas:
        # publishing UsageQuota documents=300 would silently disable overage
        # after document 300, and RPM is not a monthly quota.
        # Dedicated durable metering/rate-limiter integration must enforce them.
        plans.append(
            PlanDefinition(
                plan_id=key,
                display_name=item["name"],
                edition_id="nfcore-total-feature-parity",
                price_ids=(
                    f"nfcore-{key}-monthly-candidate",
                    f"nfcore-{key}-annual-candidate",
                ),
                trial_days=14,
                tags=("catalog-v2", "activation-requires-pricing-admin-and-release"),
                enabled=True,
                periodic_quotas=(),
            )
        )
    return CommercialPricingConfiguration(
        configuration_id="nfcore-four-plans-approved-2026-11-06",
        version=2,
        prices=tuple(prices),
        plans=tuple(plans),
    )


def estimate_monthly_charge(
    plan_key: str,
    docs_emitted: int,
    *,
    annual_contract: bool = False,
    path: Path = _DEFAULT,
) -> dict[str, object]:
    """Non-binding quote; NOT an invoice, charge, quota reservation or payment."""
    if not isinstance(docs_emitted, int) or isinstance(docs_emitted, bool) or docs_emitted < 0:
        raise CommercialPricingError("document count must be nonnegative integer")
    config = build_canonical_candidate(path)
    plan = next((p for p in config.plans if p.plan_id == plan_key), None)
    if plan is None:
        raise CommercialPricingError("unknown plan")
    cadence = BillingCadence.ANNUAL if annual_contract else BillingCadence.MONTHLY
    price = next(p for p in config.prices if p.price_id in plan.price_ids and p.cadence == cadence)
    if not price.enabled:
        raise CommercialPricingError("cadence not currently approved")
    raw_plans = read_candidate(path)["plans"]
    assert isinstance(raw_plans, dict)
    raw_plan = raw_plans[plan_key]
    assert isinstance(raw_plan, dict)
    included_raw = raw_plan["included_documents"]
    included = None if included_raw is None and plan_key == "enterprise" else _positive_int(included_raw, "included documents")
    excess = 0 if included is None else max(0, docs_emitted - included)
    if excess:
        raise CommercialPricingError("document quota exceeded; overage billing is not approved")
    base = price.base_amount / 12 if annual_contract else price.base_amount
    charge = (Decimal(excess) * price.per_document_amount).quantize(_CENT, rounding=ROUND_HALF_UP)
    return {
        "plan": plan.plan_id,
        "status": "ESTIMATE_ONLY_NOT_INVOICE",
        "monthly_equivalent_base": base,
        "documents": docs_emitted,
        "included_documents": included,
        "excess_documents": excess,
        "overage_estimate": charge,
        "monthly_equivalent_total": (base + charge).quantize(_CENT),
    }
