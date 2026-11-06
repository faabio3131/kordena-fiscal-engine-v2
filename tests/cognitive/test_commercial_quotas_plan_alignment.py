"""Cognitive token-quota plan ids must match the canonical catalog's plan ids.

Regression target: config/commercial/plans.json and every real
CommercialPurchaseRecord/subscription row have always used
starter/pro/business/enterprise as plan_id. TokenQuotaPlan previously only
recognized essencial/crescimento/escala, so allowance_for_subscription()
rejected every real paid subscription outright -- configured_allowance()
always returned None for them, which meant DurableTokenQuotaStore.reserve()
raised QuotaDenied("canonical subscription has no authorized cognitive
quotas") for 100% of real paying customers. This file locks in the fix
(plan ids renamed to match the catalog) and the backward-compat shim that
keeps already-persisted legacy-named rows readable without a data migration.
"""

from __future__ import annotations

import json

import pytest

from kordena_fiscal.cognitive.commercial_quotas import (
    APPROVED_TOKEN_ALLOWANCES,
    INPUT_QUOTA_METRIC,
    OUTPUT_QUOTA_METRIC,
    TokenQuotaPlan,
    allowance_for_subscription,
    configured_allowance,
)


@pytest.mark.parametrize(
    ("plan_id", "input_tokens", "output_tokens"),
    [
        ("starter", 1_000_000, 300_000),
        ("pro", 3_000_000, 900_000),
        ("business", 8_000_000, 2_400_000),
        ("enterprise", 8_000_000, 2_400_000),
    ],
)
def test_real_catalog_plan_ids_now_resolve_to_an_approved_ceiling(
    plan_id: str, input_tokens: int, output_tokens: int
) -> None:
    """Before the fix this returned None for every one of these ids."""
    ceiling = allowance_for_subscription(plan_id=plan_id, status="active")
    assert ceiling is not None
    assert (ceiling.input_tokens, ceiling.output_tokens) == (input_tokens, output_tokens)
    assert configured_allowance(
        plan_id=plan_id,
        status="active",
        quotas_json=json.dumps(
            [
                {"metric_id": INPUT_QUOTA_METRIC, "limit": input_tokens},
                {"metric_id": OUTPUT_QUOTA_METRIC, "limit": output_tokens},
            ]
        ),
    ) is not None


@pytest.mark.parametrize(
    ("legacy", "renamed"),
    [("essencial", "starter"), ("crescimento", "pro"), ("escala", "business")],
)
def test_legacy_persisted_plan_ids_still_resolve_without_migration(
    legacy: str, renamed: str
) -> None:
    """Read-side compatibility: an already-persisted row on the old name must
    keep working exactly like the renamed id -- this is NOT a sellable id,
    only a read fallback for rows that predate the rename.
    """
    legacy_ceiling = allowance_for_subscription(plan_id=legacy, status="active")
    renamed_ceiling = allowance_for_subscription(plan_id=renamed, status="active")
    assert legacy_ceiling == renamed_ceiling
    assert legacy_ceiling is not None


def test_legacy_plan_ids_are_not_members_of_the_sellable_enum() -> None:
    with pytest.raises(ValueError):
        TokenQuotaPlan("essencial")
    with pytest.raises(ValueError):
        TokenQuotaPlan("crescimento")
    with pytest.raises(ValueError):
        TokenQuotaPlan("escala")


def test_enterprise_ceiling_is_explicitly_provisional_not_silently_unlimited() -> None:
    # Enterprise shares Business's ceiling until the owner approves its own
    # value -- it must never be treated as "no cap" just because the
    # published document franchise for Enterprise has no hard per-period cap.
    assert (
        APPROVED_TOKEN_ALLOWANCES[TokenQuotaPlan.ENTERPRISE]
        == APPROVED_TOKEN_ALLOWANCES[TokenQuotaPlan.BUSINESS]
    )


@pytest.mark.parametrize("plan_id", ["free", "unknown", "", "trial"])
def test_unknown_or_non_sellable_ids_never_fall_back_to_any_allowance(plan_id: str) -> None:
    assert allowance_for_subscription(plan_id=plan_id, status="active") is None
