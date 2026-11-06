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


def test_four_plans_are_unpublished_and_share_same_edition() -> None:
    candidate = build_canonical_candidate()
    assert len(candidate.plans) == 4
    assert len(candidate.prices) == 8
    assert all(not plan.enabled for plan in candidate.plans)
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
    quote = estimate_monthly_charge("starter", 1400)
    assert quote["excess_documents"] == 400
    assert quote["monthly_equivalent_total"] == Decimal("199.00")
    assert quote["status"] == "ESTIMATE_ONLY_NOT_INVOICE"
    assert estimate_monthly_charge("starter", 1400, annual_contract=True)[
        "monthly_equivalent_total"
    ] == Decimal("179.00")


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
