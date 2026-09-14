from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass

import pytest

from kordena_fiscal.domain import FiscalValidationError
from kordena_fiscal.verticals import (
    FITNESS_VERTICAL,
    SAAS_VERTICAL,
    SERVICE_VERTICAL,
    CapabilityVerticalModule,
    VerticalCapabilityError,
    VerticalModuleDescriptor,
    VerticalModuleNotFoundError,
    VerticalModuleRegistry,
    VerticalRegistrationError,
    neutral_vertical_modules,
)
from kordena_fiscal.verticals.restaurant import (
    RESTAURANT_VERTICAL_DESCRIPTOR,
    RestaurantEstablishmentKind,
    RestaurantSupplyFacts,
    RestaurantSupplyKind,
    RestaurantTaxTreatment,
    RestaurantVerticalModule,
)


def test_registry_is_explicit_and_unknown_vertical_fails_closed() -> None:
    registry = VerticalModuleRegistry()

    assert registry.module_ids == ()
    assert registry.get("restaurant") is None
    with pytest.raises(VerticalModuleNotFoundError, match="not registered"):
        registry.require("restaurant")


def test_registry_rejects_duplicate_module_identity() -> None:
    registry = VerticalModuleRegistry([SERVICE_VERTICAL])

    with pytest.raises(VerticalRegistrationError, match="already registered"):
        registry.register(SERVICE_VERTICAL)


def test_capability_resolution_is_explicit_per_vertical() -> None:
    registry = VerticalModuleRegistry(neutral_vertical_modules())

    assert registry.require_capability("fitness", "operation.membership") is FITNESS_VERTICAL
    recurring = registry.modules_for("operation.recurring")
    assert tuple(module.descriptor.module_id for module in recurring) == ("fitness", "saas")

    with pytest.raises(VerticalCapabilityError, match="does not declare capability"):
        registry.require_capability("service", "operation.membership")


def test_service_fitness_and_saas_are_neutral_declarative_modules() -> None:
    assert SERVICE_VERTICAL.descriptor.capabilities == frozenset({"operation.service"})
    assert FITNESS_VERTICAL.descriptor.supports("operation.recurring") is True
    assert SAAS_VERTICAL.descriptor.supports("operation.subscription") is True
    assert isinstance(SERVICE_VERTICAL, CapabilityVerticalModule)


def test_neutral_vertical_import_does_not_eagerly_load_restaurant_classifier() -> None:
    script = """
import sys
from kordena_fiscal.verticals import FITNESS_VERTICAL, SAAS_VERTICAL, SERVICE_VERTICAL
assert FITNESS_VERTICAL.descriptor.module_id == 'fitness'
assert SAAS_VERTICAL.descriptor.module_id == 'saas'
assert SERVICE_VERTICAL.descriptor.module_id == 'service'
assert 'kordena_fiscal.verticals.restaurant' not in sys.modules
assert 'kordena_fiscal.tax.restaurant' not in sys.modules
"""
    subprocess.run([sys.executable, "-c", script], check=True)


def test_future_vertical_can_register_without_core_fork() -> None:
    @dataclass(frozen=True, slots=True)
    class SyntheticVertical:
        descriptor: VerticalModuleDescriptor

    synthetic = SyntheticVertical(
        VerticalModuleDescriptor(
            module_id="future-commerce",
            version="2026.1",
            capabilities=frozenset({"operation.marketplace"}),
        )
    )
    registry = VerticalModuleRegistry([synthetic])

    resolved = registry.require_capability("future-commerce", "operation.marketplace")
    assert resolved is synthetic


def test_restaurant_is_an_explicit_vertical_module() -> None:
    module = RestaurantVerticalModule()
    registry = VerticalModuleRegistry([module])

    resolved = registry.require_capability(
        "restaurant",
        "tax.restaurant.supply-classification",
    )
    assert resolved is module
    assert module.descriptor is RESTAURANT_VERTICAL_DESCRIPTOR

    decision = module.classify_supply(
        RestaurantSupplyFacts(
            establishment_kind=RestaurantEstablishmentKind.BAR_RESTAURANT,
            supply_kind=RestaurantSupplyKind.FOOD,
            prepared_or_manipulated_on_premises=True,
        )
    )
    assert decision.treatment is RestaurantTaxTreatment.SPECIFIC_REGIME


def test_legacy_tax_surface_points_to_the_vertical_implementation() -> None:
    from kordena_fiscal.tax import RestaurantTaxClassifier as LegacyClassifier
    from kordena_fiscal.verticals.restaurant import RestaurantTaxClassifier

    assert LegacyClassifier is RestaurantTaxClassifier


def test_vertical_descriptor_validation_fails_closed() -> None:
    with pytest.raises(FiscalValidationError, match="module_id"):
        VerticalModuleDescriptor(
            module_id="Restaurant Module",
            capabilities=frozenset({"operation.service"}),
        )

    with pytest.raises(FiscalValidationError, match="at least one capability"):
        VerticalModuleDescriptor(module_id="empty", capabilities=frozenset())
