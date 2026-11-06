"""Unittest adapter over the canonical commercial, cognitive and normative modules.

No parallel BillingEngine, model provider implementation or authenticity claim.
"""

from __future__ import annotations

import hashlib
import unittest
from datetime import date
from decimal import Decimal

from kordena_fiscal.cognitive.contracts import Capability
from kordena_fiscal.cognitive.routing_policy import (
    AdvisoryTier,
    suggest_advisory_tier,
)
from kordena_fiscal.compliance.normative_sentinel import assess_pinned_normative_bytes
from kordena_fiscal.compliance.rtc import RegulatoryArtifactKind, RegulatoryArtifactPin
from kordena_fiscal.product.commercial_plan_candidate import (
    build_canonical_candidate,
    estimate_monthly_charge,
)


class TestCanonicalCommercialCognitiveArchitecture(unittest.TestCase):
    def test_four_consumption_plans_are_not_published(self) -> None:
        catalog = build_canonical_candidate()
        self.assertEqual(
            {plan.plan_id for plan in catalog.plans},
            {"starter", "pro", "business", "enterprise"},
        )
        self.assertTrue(all(plan.enabled for plan in catalog.plans))
        self.assertEqual(catalog.version, 2)
        self.assertEqual(
            estimate_monthly_charge("starter", 400)["monthly_equivalent_total"],
            Decimal("99.00"),
        )

    def test_multi_ai_routing_is_non_authoritative(self) -> None:
        basic = suggest_advisory_tier(
            capability=Capability.EXPLAIN_REJECTION,
            risk="low",
            evidence_complete=True,
        )
        complex_case = suggest_advisory_tier(
            capability=Capability.ANSWER_ACCOUNTANT_QUESTION,
            risk="high",
            evidence_complete=True,
        )
        self.assertEqual(basic.tier, AdvisoryTier.FAST_ECONOMIC)
        self.assertEqual(complex_case.tier, AdvisoryTier.DEEP_REASONING)
        self.assertFalse(complex_case.authoritative)

    def test_normative_hash_cannot_claim_official_authenticity(self) -> None:
        raw = b"synthetic normative fixture"
        pin = RegulatoryArtifactPin(
            artifact_id="SYNTHETIC-ONLY",
            kind=RegulatoryArtifactKind.CLASSIFICATION_TABLE,
            version="test",
            published_on=date(2026, 11, 3),
            source_reference="https://example.org/synthetic",
            checksum_sha256=hashlib.sha256(raw).hexdigest(),
        )
        assessment = assess_pinned_normative_bytes(pin, raw)
        self.assertTrue(assessment.integrity_verified)
        self.assertFalse(assessment.official_provenance_verified)
        self.assertFalse(assessment.fiscal_production_approved)


if __name__ == "__main__":
    unittest.main()
