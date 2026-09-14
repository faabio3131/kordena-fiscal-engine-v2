"""Backward-compatible restaurant imports.

V2-09 moved restaurant-sector implementation to the optional
``kordena_fiscal.verticals.restaurant`` module. This shim preserves the historical
``kordena_fiscal.tax.restaurant`` surface for Kordena and other existing callers.
"""

from kordena_fiscal.verticals.restaurant import (
    CorporateMealContractFacts,
    RestaurantBaseAdjustmentDecision,
    RestaurantBaseAdjustmentFacts,
    RestaurantEstablishmentKind,
    RestaurantSupplyDecision,
    RestaurantSupplyFacts,
    RestaurantSupplyKind,
    RestaurantTaxClassifier,
    RestaurantTaxTreatment,
)

__all__ = [
    "CorporateMealContractFacts",
    "RestaurantBaseAdjustmentDecision",
    "RestaurantBaseAdjustmentFacts",
    "RestaurantEstablishmentKind",
    "RestaurantSupplyDecision",
    "RestaurantSupplyFacts",
    "RestaurantSupplyKind",
    "RestaurantTaxClassifier",
    "RestaurantTaxTreatment",
]
