from decimal import Decimal

import pytest

from kordena_fiscal.domain import FiscalValidationError, Money
from kordena_fiscal.tax import (
    CorporateMealContractFacts,
    RestaurantBaseAdjustmentFacts,
    RestaurantEstablishmentKind,
    RestaurantSupplyFacts,
    RestaurantSupplyKind,
    RestaurantTaxClassifier,
    RestaurantTaxTreatment,
)


@pytest.fixture
def classifier() -> RestaurantTaxClassifier:
    return RestaurantTaxClassifier()


def _supply(**overrides: object) -> RestaurantSupplyFacts:
    values: dict[str, object] = {
        "establishment_kind": RestaurantEstablishmentKind.BAR_RESTAURANT,
        "supply_kind": RestaurantSupplyKind.FOOD,
        "prepared_or_manipulated_on_premises": True,
    }
    values.update(overrides)
    return RestaurantSupplyFacts(**values)  # type: ignore[arg-type]


def _money(value: str) -> Money:
    return Money(Decimal(value))


def test_prepared_food_is_in_specific_regime(classifier: RestaurantTaxClassifier) -> None:
    decision = classifier.classify_supply(_supply())

    assert decision.treatment is RestaurantTaxTreatment.SPECIFIC_REGIME
    assert decision.rate_reduction_percent == Decimal("40")
    assert decision.recipient_credit_allowed is False
    assert decision.normative_references


def test_prepared_non_alcoholic_beverage_is_in_specific_regime(
    classifier: RestaurantTaxClassifier,
) -> None:
    decision = classifier.classify_supply(
        _supply(supply_kind=RestaurantSupplyKind.NON_ALCOHOLIC_BEVERAGE)
    )

    assert decision.is_specific_regime is True


def test_alcoholic_beverage_is_excluded_even_if_prepared(
    classifier: RestaurantTaxClassifier,
) -> None:
    decision = classifier.classify_supply(
        _supply(supply_kind=RestaurantSupplyKind.ALCOHOLIC_BEVERAGE)
    )

    assert decision.treatment is RestaurantTaxTreatment.GENERAL_REGIME
    assert decision.reason_code == "alcoholic_beverage_excluded"
    assert decision.rate_reduction_percent is None


def test_third_party_non_prepared_food_is_excluded(
    classifier: RestaurantTaxClassifier,
) -> None:
    decision = classifier.classify_supply(
        _supply(
            acquired_from_third_party=True,
            prepared_or_manipulated_on_premises=False,
        )
    )

    assert decision.treatment is RestaurantTaxTreatment.GENERAL_REGIME
    assert decision.reason_code == "third_party_non_prepared_supply_excluded"


def test_third_party_food_can_enter_regime_after_on_premises_preparation(
    classifier: RestaurantTaxClassifier,
) -> None:
    decision = classifier.classify_supply(
        _supply(
            acquired_from_third_party=True,
            prepared_or_manipulated_on_premises=True,
        )
    )

    assert decision.is_specific_regime is True


def test_industrialized_non_alcoholic_beverage_is_excluded(
    classifier: RestaurantTaxClassifier,
) -> None:
    decision = classifier.classify_supply(
        _supply(
            supply_kind=RestaurantSupplyKind.NON_ALCOHOLIC_BEVERAGE,
            industrialized_non_alcoholic_beverage=True,
        )
    )

    assert decision.treatment is RestaurantTaxTreatment.GENERAL_REGIME
    assert decision.reason_code == "industrialized_non_alcoholic_beverage_excluded"


def test_contracted_corporate_meal_exclusion_requires_all_facts(
    classifier: RestaurantTaxClassifier,
) -> None:
    excluded = classifier.classify_supply(
        _supply(
            corporate_meal=CorporateMealContractFacts(
                recipient_is_legal_entity=True,
                under_contract=True,
                matches_excluded_nbs_or_provider_cnae=True,
            )
        )
    )
    not_excluded = classifier.classify_supply(
        _supply(
            corporate_meal=CorporateMealContractFacts(
                recipient_is_legal_entity=True,
                under_contract=True,
                matches_excluded_nbs_or_provider_cnae=False,
            )
        )
    )

    assert excluded.reason_code == "contracted_corporate_meal_excluded"
    assert excluded.is_specific_regime is False
    assert not_excluded.is_specific_regime is True


def test_other_supply_kind_stays_outside_specific_regime(
    classifier: RestaurantTaxClassifier,
) -> None:
    decision = classifier.classify_supply(
        _supply(supply_kind=RestaurantSupplyKind.OTHER)
    )

    assert decision.treatment is RestaurantTaxTreatment.GENERAL_REGIME


def test_gratuity_is_eligible_only_when_passed_segregated_and_within_15_percent(
    classifier: RestaurantTaxClassifier,
) -> None:
    decision = classifier.evaluate_base_adjustments(
        RestaurantBaseAdjustmentFacts(
            total_operation_amount=_money("120.00"),
            food_beverage_supply_amount=_money("100.00"),
            specific_regime_supply_amount=_money("80.00"),
            gratuity_amount=_money("15.00"),
            gratuity_fully_passed_to_employees=True,
            gratuity_segregated_in_fiscal_document=True,
        )
    )

    assert decision.gratuity_exclusion_eligible is True
    assert decision.specific_supply_ratio == Decimal("80.00") / Decimal("120.00")


def test_gratuity_above_15_percent_is_not_eligible(
    classifier: RestaurantTaxClassifier,
) -> None:
    decision = classifier.evaluate_base_adjustments(
        RestaurantBaseAdjustmentFacts(
            total_operation_amount=_money("120.00"),
            food_beverage_supply_amount=_money("100.00"),
            specific_regime_supply_amount=_money("100.00"),
            gratuity_amount=_money("15.01"),
            gratuity_fully_passed_to_employees=True,
            gratuity_segregated_in_fiscal_document=True,
        )
    )

    assert decision.gratuity_exclusion_eligible is False
    assert "gratuity_exceeds_fifteen_percent_limit" in decision.reasons


def test_gratuity_not_fully_passed_is_not_eligible(
    classifier: RestaurantTaxClassifier,
) -> None:
    decision = classifier.evaluate_base_adjustments(
        RestaurantBaseAdjustmentFacts(
            total_operation_amount=_money("100.00"),
            food_beverage_supply_amount=_money("100.00"),
            specific_regime_supply_amount=_money("100.00"),
            gratuity_amount=_money("10.00"),
            gratuity_fully_passed_to_employees=False,
            gratuity_segregated_in_fiscal_document=True,
        )
    )

    assert decision.gratuity_exclusion_eligible is False
    assert "gratuity_not_fully_passed_to_employees" in decision.reasons


def test_platform_amount_requires_fiscal_document_segregation(
    classifier: RestaurantTaxClassifier,
) -> None:
    eligible = classifier.evaluate_base_adjustments(
        RestaurantBaseAdjustmentFacts(
            total_operation_amount=_money("100.00"),
            food_beverage_supply_amount=_money("100.00"),
            specific_regime_supply_amount=_money("100.00"),
            platform_amount_not_passed_to_establishment=_money("12.00"),
            platform_amount_segregated_in_fiscal_document=True,
        )
    )
    blocked = classifier.evaluate_base_adjustments(
        RestaurantBaseAdjustmentFacts(
            total_operation_amount=_money("100.00"),
            food_beverage_supply_amount=_money("100.00"),
            specific_regime_supply_amount=_money("100.00"),
            platform_amount_not_passed_to_establishment=_money("12.00"),
            platform_amount_segregated_in_fiscal_document=False,
        )
    )

    assert eligible.platform_exclusion_eligible is True
    assert blocked.platform_exclusion_eligible is False
    assert "platform_amount_not_segregated_in_fiscal_document" in blocked.reasons


def test_missing_specific_general_segregation_invalidates_specific_document_treatment(
    classifier: RestaurantTaxClassifier,
) -> None:
    decision = classifier.evaluate_base_adjustments(
        RestaurantBaseAdjustmentFacts(
            total_operation_amount=_money("100.00"),
            food_beverage_supply_amount=_money("100.00"),
            specific_regime_supply_amount=_money("80.00"),
            gratuity_amount=_money("10.00"),
            gratuity_fully_passed_to_employees=True,
            gratuity_segregated_in_fiscal_document=True,
            platform_amount_not_passed_to_establishment=_money("5.00"),
            platform_amount_segregated_in_fiscal_document=True,
            specific_and_general_values_segregated=False,
        )
    )

    assert decision.specific_regime_documentation_valid is False
    assert decision.gratuity_exclusion_eligible is False
    assert decision.platform_exclusion_eligible is False
    assert "specific_and_general_values_not_segregated" in decision.reasons


def test_operation_amount_invariants_fail_closed() -> None:
    with pytest.raises(FiscalValidationError, match="greater than zero"):
        RestaurantBaseAdjustmentFacts(
            total_operation_amount=_money("0"),
            food_beverage_supply_amount=_money("0"),
            specific_regime_supply_amount=_money("0"),
        )

    with pytest.raises(FiscalValidationError, match="cannot exceed total"):
        RestaurantBaseAdjustmentFacts(
            total_operation_amount=_money("100"),
            food_beverage_supply_amount=_money("101"),
            specific_regime_supply_amount=_money("100"),
        )

    with pytest.raises(FiscalValidationError, match="cannot exceed food_beverage"):
        RestaurantBaseAdjustmentFacts(
            total_operation_amount=_money("100"),
            food_beverage_supply_amount=_money("80"),
            specific_regime_supply_amount=_money("81"),
        )


def test_industrialized_flag_requires_non_alcoholic_beverage_kind() -> None:
    with pytest.raises(FiscalValidationError, match="requires non-alcoholic"):
        _supply(industrialized_non_alcoholic_beverage=True)
