from __future__ import annotations

import pytest

from kordena_fiscal.domain import (
    FiscalAccountBinding,
    FiscalAccountId,
    FiscalBindingRegistry,
    FiscalEnvironment,
    FiscalUnitId,
    FiscalValidationError,
    HostNamespace,
    HostScope,
)


def _binding(
    *,
    binding_id: str = "binding-1",
    namespace: str = "fm.kordena",
    external_tenant: str = "tenant-123",
    external_unit: str = "unit-1",
    fiscal_account: str = "facc-001",
    fiscal_unit: str = "funit-001",
) -> FiscalAccountBinding:
    return FiscalAccountBinding(
        binding_id=binding_id,
        host_scope=HostScope(
            namespace=HostNamespace(namespace),
            tenant_id=external_tenant,
            unit_id=external_unit,
        ),
        fiscal_account_id=FiscalAccountId(fiscal_account),
        fiscal_unit_id=FiscalUnitId(fiscal_unit),
    )


def test_host_namespace_is_normalized_to_lowercase() -> None:
    namespace = HostNamespace("  FM.Kordena  ")

    assert namespace.value == "fm.kordena"
    assert str(namespace) == "fm.kordena"


@pytest.mark.parametrize("value", ["", "fm/kordena", ".fm", "fm.", "fm kordena"])
def test_host_namespace_rejects_invalid_values(value: str) -> None:
    with pytest.raises(FiscalValidationError):
        HostNamespace(value)


def test_host_scope_key_qualifies_external_ids_with_namespace() -> None:
    kordena = HostScope(HostNamespace("fm.kordena"), "tenant-1", "unit-1")
    iron = HostScope(HostNamespace("fm.iron"), "tenant-1", "unit-1")

    assert kordena.canonical_key == ("fm.kordena", "tenant-1", "unit-1")
    assert iron.canonical_key == ("fm.iron", "tenant-1", "unit-1")
    assert kordena.canonical_key != iron.canonical_key


def test_binding_resolves_external_scope_to_internal_fiscal_scope() -> None:
    binding = _binding()

    scope = binding.to_execution_scope(
        environment=FiscalEnvironment.HOMOLOGATION,
        correlation_id="corr-001",
    )

    assert scope.tenant_id == "facc-001"
    assert scope.unit_id == "funit-001"
    assert scope.environment is FiscalEnvironment.HOMOLOGATION
    assert scope.correlation_id == "corr-001"
    assert "tenant-123" not in scope.partition_key
    assert "unit-1" not in scope.partition_key


def test_registry_allows_same_external_ids_in_different_host_namespaces() -> None:
    kordena = _binding(
        binding_id="binding-kordena",
        namespace="fm.kordena",
        fiscal_account="facc-kordena",
    )
    iron = _binding(
        binding_id="binding-iron",
        namespace="fm.iron",
        fiscal_account="facc-iron",
    )
    registry = FiscalBindingRegistry((kordena, iron))

    assert registry.resolve(kordena.host_scope).fiscal_account_id.value == "facc-kordena"
    assert registry.resolve(iron.host_scope).fiscal_account_id.value == "facc-iron"


def test_registry_never_falls_back_across_host_namespace() -> None:
    registry = FiscalBindingRegistry((_binding(namespace="fm.kordena"),))
    unknown_host = HostScope(
        namespace=HostNamespace("fm.iron"),
        tenant_id="tenant-123",
        unit_id="unit-1",
    )

    with pytest.raises(FiscalValidationError, match="exact host scope"):
        registry.resolve(unknown_host)


def test_registry_requires_exact_unit_match() -> None:
    registry = FiscalBindingRegistry((_binding(),))
    different_unit = HostScope(
        namespace=HostNamespace("fm.kordena"),
        tenant_id="tenant-123",
        unit_id="unit-2",
    )

    with pytest.raises(FiscalValidationError, match="exact host scope"):
        registry.resolve(different_unit)


def test_registry_rejects_duplicate_binding_for_same_host_scope() -> None:
    first = _binding(binding_id="binding-1")
    second = _binding(binding_id="binding-2", fiscal_account="facc-002")

    with pytest.raises(FiscalValidationError, match="duplicate fiscal binding"):
        FiscalBindingRegistry((first, second))


def test_registry_rejects_duplicate_binding_id() -> None:
    first = _binding(binding_id="binding-1", namespace="fm.kordena")
    second = _binding(binding_id="binding-1", namespace="fm.iron")

    with pytest.raises(FiscalValidationError, match="duplicate binding_id"):
        FiscalBindingRegistry((first, second))
