"""Four-plan IA quota policy — live data is subscription snapshot, not site prices."""

import json

import pytest

from kordena_fiscal.cognitive.commercial_quotas import (
    APPROVED_TOKEN_ALLOWANCES, TokenQuotaPlan, allowance_for_subscription,
    configured_allowance,
)


@pytest.mark.parametrize("plan_id,input_tokens,output_tokens", [
    ("starter", 1_000_000, 300_000),
    ("pro", 3_000_000, 900_000),
    ("business", 8_000_000, 2_400_000),
    ("enterprise", 8_000_000, 2_400_000),
])
def test_four_plans_have_conservative_approved_caps(
    plan_id: str, input_tokens: int, output_tokens: int,
) -> None:
    ceiling = allowance_for_subscription(plan_id=plan_id, status="active")
    assert ceiling is not None
    assert (ceiling.input_tokens, ceiling.output_tokens) == (input_tokens, output_tokens)
    assert configured_allowance(
        plan_id=plan_id, status="active",
        quotas_json=json.dumps([
            {"metric_id": "cognitive.input_tokens", "limit": input_tokens},
            {"metric_id": "cognitive.output_tokens", "limit": output_tokens},
        ]),
    ) == ceiling


def test_trial_is_fourteen_day_commercial_status_not_paid_entitlement() -> None:
    assert allowance_for_subscription(plan_id="starter", status="trial") == APPROVED_TOKEN_ALLOWANCES[TokenQuotaPlan.TRIAL]
    assert allowance_for_subscription(plan_id="enterprise", status="expired") is None


@pytest.mark.parametrize("plan_id", ["essencial", "crescimento", "escala", "free", "unknown", "trial"])
def test_legacy_and_unknown_paid_ids_never_fall_back_to_unlimited(plan_id: str) -> None:
    assert allowance_for_subscription(plan_id=plan_id, status="active") is None


@pytest.mark.parametrize("snapshot", [
    "[]", "{}", "null", "not-json",
    '[{"metric_id":"cognitive.input_tokens","limit":999999999}]',
    '[{"metric_id":"cognitive.input_tokens","limit":1000},{"metric_id":"cognitive.output_tokens","limit":999999999}]',
    '[{"metric_id":"cognitive.input_tokens","limit":true},{"metric_id":"cognitive.output_tokens","limit":100}]',
])
def test_denies_missing_or_unapproved_snapshot_without_model_call(snapshot: str) -> None:
    assert configured_allowance(plan_id="starter", status="active", quotas_json=snapshot) is None


def test_valid_subscription_snapshot_may_be_stricter_than_ceiling() -> None:
    allowance = configured_allowance(
        plan_id="enterprise", status="grace",
        quotas_json=json.dumps([
            {"metric_id": "cognitive.input_tokens", "limit": 500},
            {"metric_id": "cognitive.output_tokens", "limit": 50},
        ]),
    )
    assert allowance is not None
    assert (allowance.input_tokens, allowance.output_tokens) == (500, 50)
