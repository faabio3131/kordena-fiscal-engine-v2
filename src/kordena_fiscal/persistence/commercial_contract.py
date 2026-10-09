"""Strict JSON codec for versioned canonical contracted terms, never raw events."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime

from kordena_fiscal.product.billing import CommercialPlan, UsageQuota
from kordena_fiscal.product.commercial_fulfillment import CommercialFulfillmentError
from kordena_fiscal.product.commercial_lifecycle import CommercialContract, PaidCommercialPeriod
from kordena_fiscal.product.pricing import BillingCadence


def encode_contract(contract: CommercialContract) -> str:
    return json.dumps(
        asdict(contract), default=lambda v: v.isoformat(), separators=(",", ":"), sort_keys=True
    )


def decode_contract(raw: str) -> CommercialContract:
    try:
        value = json.loads(raw)
        plan = value["plan"]
        return CommercialContract(
            purchase_id=value["purchase_id"],
            plan=CommercialPlan(
                plan["plan_id"],
                tuple(plan["entitlement_ids"]),
                tuple(UsageQuota(**q) for q in plan["quotas"]),
            ),
            cadence=BillingCadence(value["cadence"]),
            grace_days=value["grace_days"],
            pricing_configuration_id=value["pricing_configuration_id"],
            pricing_version=value["pricing_version"],
            periods=tuple(
                PaidCommercialPeriod(
                    invoice_id=p["invoice_id"],
                    paid_at=datetime.fromisoformat(p["paid_at"]),
                    start=datetime.fromisoformat(p["start"]),
                    end=datetime.fromisoformat(p["end"]),
                    renewal=p["renewal"],
                    usage=tuple((k, v) for k, v in p["usage"]),
                )
                for p in value["periods"]
            ),
        )
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        raise CommercialFulfillmentError("persisted commercial contract is invalid") from exc
