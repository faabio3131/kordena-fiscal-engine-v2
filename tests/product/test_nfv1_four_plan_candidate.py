from __future__ import annotations

import json
from decimal import Decimal

import pytest

from kordena_fiscal.product.commercial_plan_candidate import (
    build_canonical_candidate,
    estimate_monthly_charge,
    read_candidate,
)
from kordena_fiscal.product.pricing import CommercialPricingError


def test_four_plans_are_versioned_and_release_gated() -> None:
    candidate = build_canonical_candidate()
    assert len(candidate.plans) == 4
    assert len(candidate.prices) == 8
    assert all(plan.enabled for plan in candidate.plans)
    assert candidate.version == 2
    assert read_candidate()["publication"]["runtime_activated"] is False
    assert {p.edition_id for p in candidate.plans} == {"nfcore-total-feature-parity"}
    # Included docs/RPM are NOT hard period quotas: overage is allowed
    # as commercial policy; rate limiting belongs to the runtime.
    assert all(not p.periodic_quotas for p in candidate.plans)


def test_trial_is_not_fiscal_activation() -> None:
    trial = read_candidate()["trial"]
    assert trial["duration_days"] == 14
    assert trial["requires_credit_card"] is False
    assert trial["production_docs_limit"] == 50
    assert trial["production_fiscal_activation_required"] is True


def test_monthly_quote_uses_canonical_prices_not_new_billing_engine() -> None:
    quote = estimate_monthly_charge("starter", 1100)
    assert quote["included_documents"] == 1000
    assert quote["excess_documents"] == 100
    assert quote["monthly_equivalent_total"] == Decimal("124.00")
    assert quote["status"] == "ESTIMATE_ONLY_NOT_INVOICE"
    assert estimate_monthly_charge("starter", 1100, annual_contract=True)[
        "monthly_equivalent_total"
    ] == Decimal("104.00")


@pytest.mark.parametrize("count", [-1, True, 1.5])
def test_invalid_usage_rejected(count: object) -> None:
    with pytest.raises(CommercialPricingError):
        estimate_monthly_charge("starter", count)  # type: ignore[arg-type]


def test_duplicate_json_key_fail_closed(tmp_path) -> None:
    path = tmp_path / "config.json"
    path.write_text('{"schema_version":1,"schema_version":1}', encoding="utf-8")
    with pytest.raises(CommercialPricingError, match="duplicate"):
        read_candidate(path)


def test_bypass_of_fiscal_gate_denied(tmp_path) -> None:
    source = read_candidate()
    source["trial"]["production_fiscal_activation_required"] = False
    path = tmp_path / "candidate.json"
    path.write_text(json.dumps(source), encoding="utf-8")
    with pytest.raises(CommercialPricingError, match="gate"):
        build_canonical_candidate(path)


def test_exact_commercial_site_limits_and_enterprise_unlimited() -> None:
    catalog = read_candidate()
    assert catalog["status"] == "PUBLISHED_CATALOG_RUNTIME_GATED"
    expected = {
        "starter": ("99.00", 1000, 1, 120),
        "pro": ("249.00", 5000, 3, 600),
        "business": ("590.00", 25000, 15, 2400),
        "enterprise": ("1490.00", None, None, None),
    }
    for plan_id, (price, docs, cnpjs, rpm) in expected.items():
        plan = catalog["plans"][plan_id]
        assert (plan["monthly_price_brl"], plan["included_documents"],
                plan["max_cnpjs"], plan["api_rate_limit_rpm"]) == (price, docs, cnpjs, rpm)
    quote = estimate_monthly_charge("enterprise", 2_000_000)
    assert quote["excess_documents"] == 0
    assert quote["included_documents"] is None


def test_commercial_catalog_cannot_activate_itself(tmp_path) -> None:
    document = read_candidate()
    document["publication"]["runtime_activated"] = True
    path = tmp_path / "malicious.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(CommercialPricingError, match="cannot self-activate"):
        read_candidate(path)
