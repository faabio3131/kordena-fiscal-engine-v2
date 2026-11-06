"""Approved cognitive token budgets, resolved exclusively from canonical subscriptions.

These are token allowances, not model prices. Provider usage is recorded by the
cognitive ledger; fiscal rules and commercial subscription status remain outside
the model's authority.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum

INPUT_QUOTA_METRIC = "cognitive.input_tokens"
OUTPUT_QUOTA_METRIC = "cognitive.output_tokens"


class TokenQuotaPlan(StrEnum):
    TRIAL = "trial"
    STARTER = "starter"
    PRO = "pro"
    BUSINESS = "business"
    ENTERPRISE = "enterprise"


@dataclass(frozen=True, slots=True)
class TokenAllowance:
    input_tokens: int
    output_tokens: int

    def __post_init__(self) -> None:
        if self.input_tokens < 0 or self.output_tokens < 0:
            raise ValueError("token allowance cannot be negative")


# Existing approved ceilings from the 2026-11-01 three-tier policy are
# conservatively mapped onto Starter/Pro/Business (v2). Enterprise defaults
# to Business ceiling pending its explicit signed quota-policy version;
# "unlimited documents" NEVER implies unlimited IA tokens or billing.
# Actual allowance is still read from canonical subscription quotas_json,
# cannot be inferred from marketing or plan ID alone.
APPROVED_TOKEN_ALLOWANCES: dict[TokenQuotaPlan, TokenAllowance] = {
    TokenQuotaPlan.TRIAL: TokenAllowance(750_000, 210_000),
    TokenQuotaPlan.STARTER: TokenAllowance(1_000_000, 300_000),
    TokenQuotaPlan.PRO: TokenAllowance(3_000_000, 900_000),
    TokenQuotaPlan.BUSINESS: TokenAllowance(8_000_000, 2_400_000),
    TokenQuotaPlan.ENTERPRISE: TokenAllowance(8_000_000, 2_400_000),
}

# Backward-compatible read-side caps for EXISTING paid subscriptions.
# New catalog v2 does not publish these legacy IDs, so they cannot be sold
# to new customers. Removing this compatibility before durable migration
# would silently deny already persisted subscriptions and break reservation.
LEGACY_PAID_ALLOWANCES: dict[str, TokenAllowance] = {
    "essencial": TokenAllowance(1_000_000, 300_000),
    "crescimento": TokenAllowance(3_000_000, 900_000),
    "escala": TokenAllowance(8_000_000, 2_400_000),
}


def allowance_for_subscription(*, plan_id: str, status: str) -> TokenAllowance | None:
    """A trial is a subscription status; never grant trial to a paid/unknown account."""
    state = status.strip().lower()
    if state == "trial":
        return APPROVED_TOKEN_ALLOWANCES[TokenQuotaPlan.TRIAL]
    if state not in {"active", "grace"}:
        return None
    normalized_id = plan_id.strip().lower()
    if normalized_id in LEGACY_PAID_ALLOWANCES:
        return LEGACY_PAID_ALLOWANCES[normalized_id]
    try:
        plan = TokenQuotaPlan(normalized_id)
    except ValueError:
        return None
    if plan is TokenQuotaPlan.TRIAL:
        return None
    return APPROVED_TOKEN_ALLOWANCES[plan]


def configured_allowance(
    *, plan_id: str, status: str, quotas_json: str
) -> TokenAllowance | None:
    """Read the *canonical subscription snapshot*, capped by owner approval.

    No grant is synthesized for a subscription with missing, malformed or
    unapproved commercial quotas. The pricing administration authority owns
    publishing the snapshot; this code can only enforce it.
    """
    ceiling = allowance_for_subscription(plan_id=plan_id, status=status)
    if ceiling is None:
        return None
    try:
        entries = json.loads(quotas_json)
    except (ValueError, TypeError):
        return None
    if not isinstance(entries, list):
        return None
    seen: dict[str, int] = {}
    for item in entries:
        if not isinstance(item, dict):
            return None
        metric_id, limit = item.get("metric_id"), item.get("limit")
        if (
            not isinstance(metric_id, str)
            or not isinstance(limit, int)
            or isinstance(limit, bool)
            or limit < 1
            or metric_id in seen
        ):
            return None
        seen[metric_id] = limit
    input_limit = seen.get(INPUT_QUOTA_METRIC)
    output_limit = seen.get(OUTPUT_QUOTA_METRIC)
    if input_limit is None or output_limit is None:
        return None
    if input_limit > ceiling.input_tokens or output_limit > ceiling.output_tokens:
        return None
    return TokenAllowance(input_limit, output_limit)
