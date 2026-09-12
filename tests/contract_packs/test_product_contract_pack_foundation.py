from datetime import UTC, datetime
from decimal import Decimal

import pytest

from kordena_fiscal.compliance import FiscalActionCapability
from kordena_fiscal.contract_packs import (
    DeclarativeProductFiscalContractPack,
    ProductContractPackDescriptor,
    ProductContractPackNotFoundError,
    ProductContractPackRegistrationError,
    ProductContractPackRegistry,
    ProductOperationContractError,
    ProductUseCaseDescriptor,
    ProductUseCaseNotFoundError,
)
from kordena_fiscal.domain import (
    ExecutionScope,
    FiscalDocumentKind,
    FiscalEnvironment,
    FiscalValidationError,
    Money,
    SourceReference,
)
from kordena_fiscal.operations import (
    FiscalOperationKind,
    FiscalOperationSnapshot,
    FiscalOperationTotals,
)
from kordena_fiscal.verticals import (
    SERVICE_VERTICAL,
    VerticalModuleNotFoundError,
    VerticalModuleRegistry,
)


def _use_case(**overrides: object) -> ProductUseCaseDescriptor:
    values: dict[str, object] = {
        "use_case_id": "service-billing",
        "operation_kinds": frozenset({FiscalOperationKind.SERVICE}),
        "document_kinds": frozenset({FiscalDocumentKind.NFSE}),
        "fiscal_actions": frozenset(
            {
                FiscalActionCapability.ISSUE,
                FiscalActionCapability.QUERY,
                FiscalActionCapability.CANCEL,
            }
        ),
        "vertical_module_id": "service",
        "required_vertical_capabilities": frozenset({"operation.service"}),
        "outbound_event_types": ("fm.fiscal.operation.requested.v1",),
        "inbound_event_types": ("fm.fiscal.document.authorized.v1",),
    }
    values.update(overrides)
    return ProductUseCaseDescriptor(**values)  # type: ignore[arg-type]


def _pack(
    *,
    pack_id: str = "example-pack",
    host_namespace: str = "example-product",
) -> DeclarativeProductFiscalContractPack:
    return DeclarativeProductFiscalContractPack(
        ProductContractPackDescriptor(
            pack_id=pack_id,
            host_namespace=host_namespace,
            use_cases=(_use_case(),),
        )
    )


def _operation(
    *,
    host_namespace: str = "example-product",
    kind: FiscalOperationKind = FiscalOperationKind.SERVICE,
) -> FiscalOperationSnapshot:
    amount = Money(Decimal("100.00"))
    return FiscalOperationSnapshot(
        scope=ExecutionScope(
            tenant_id="tenant-1",
            unit_id="unit-1",
            environment=FiscalEnvironment.HOMOLOGATION,
            correlation_id="corr-1",
            host_namespace=host_namespace,
        ),
        operation_reference=SourceReference(source_type="synthetic", source_id="op-1"),
        operation_kind=kind,
        occurred_at=datetime(2026, 9, 12, 1, 0, tzinfo=UTC),
        totals=FiscalOperationTotals.from_net_amount(amount),
    )


def test_descriptor_resolves_explicit_use_case_and_matrix() -> None:
    descriptor = _pack().descriptor

    use_case = descriptor.require_use_case("service-billing")

    assert use_case.operation_kinds == frozenset({FiscalOperationKind.SERVICE})
    assert use_case.document_kinds == frozenset({FiscalDocumentKind.NFSE})
    assert FiscalActionCapability.ISSUE in use_case.fiscal_actions
    assert use_case.vertical_module_id == "service"
    assert use_case.outbound_event_types == ("fm.fiscal.operation.requested.v1",)


def test_missing_use_case_fails_closed() -> None:
    descriptor = _pack().descriptor

    with pytest.raises(ProductUseCaseNotFoundError, match="not declared"):
        descriptor.require_use_case("unknown")


def test_operation_requires_exact_host_namespace_and_declared_kind() -> None:
    descriptor = _pack().descriptor

    accepted = descriptor.validate_operation(
        use_case_id="service-billing",
        operation=_operation(),
    )
    assert accepted.use_case_id == "service-billing"

    with pytest.raises(ProductOperationContractError, match="host namespace mismatch"):
        descriptor.validate_operation(
            use_case_id="service-billing",
            operation=_operation(host_namespace="other-product"),
        )

    with pytest.raises(ProductOperationContractError, match="operation kind"):
        descriptor.validate_operation(
            use_case_id="service-billing",
            operation=_operation(kind=FiscalOperationKind.SALE),
        )


def test_registry_is_unique_by_pack_and_host_namespace() -> None:
    registry = ProductContractPackRegistry((_pack(),))

    assert registry.require("example-pack").descriptor.host_namespace == "example-product"
    assert registry.require_for_host("example-product").descriptor.pack_id == "example-pack"

    with pytest.raises(ProductContractPackRegistrationError, match="already registered"):
        registry.register(_pack())

    with pytest.raises(ProductContractPackRegistrationError, match="host namespace"):
        registry.register(_pack(pack_id="second-pack"))


def test_registry_missing_product_fails_closed() -> None:
    registry = ProductContractPackRegistry()

    with pytest.raises(ProductContractPackNotFoundError, match="not registered"):
        registry.require("missing")

    with pytest.raises(ProductContractPackNotFoundError, match="not registered for host"):
        registry.require_for_host("missing-host")


def test_vertical_contract_is_explicitly_validated() -> None:
    descriptor = _pack().descriptor
    descriptor.validate_vertical_contracts(VerticalModuleRegistry((SERVICE_VERTICAL,)))

    with pytest.raises(VerticalModuleNotFoundError, match="not registered"):
        descriptor.validate_vertical_contracts(VerticalModuleRegistry())


def test_vertical_capability_cannot_exist_without_module_id() -> None:
    with pytest.raises(FiscalValidationError, match="require vertical_module_id"):
        _use_case(
            vertical_module_id=None,
            required_vertical_capabilities=frozenset({"operation.service"}),
        )


def test_duplicate_use_case_ids_are_rejected() -> None:
    use_case = _use_case()
    with pytest.raises(FiscalValidationError, match="must be unique"):
        ProductContractPackDescriptor(
            pack_id="duplicate-pack",
            host_namespace="duplicate-product",
            use_cases=(use_case, use_case),
        )
