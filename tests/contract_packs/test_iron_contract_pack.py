from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from kordena_fiscal.compliance import FiscalActionCapability
from kordena_fiscal.contract_packs import (
    IRON_FISCAL_CONTRACT_PACK,
    IRON_HOST_NAMESPACE,
    IRON_MEMBERSHIP_BILLING,
    IRON_RECURRING_MEMBERSHIP_BILLING,
    IRON_SERVICE_BILLING,
    IronFiscalContractPack,
    ProductContractPackRegistry,
    ProductOperationContractError,
)
from kordena_fiscal.domain import (
    ExecutionScope,
    FiscalDocumentKind,
    FiscalEnvironment,
    Money,
    SourceReference,
)
from kordena_fiscal.operations import (
    FiscalOperationKind,
    FiscalOperationSnapshot,
    FiscalOperationTotals,
)
from kordena_fiscal.verticals import FITNESS_VERTICAL, VerticalModuleRegistry


def _operation(
    *,
    kind: FiscalOperationKind,
    host_namespace: str = IRON_HOST_NAMESPACE,
) -> FiscalOperationSnapshot:
    total = Money(Decimal("129.90"))
    return FiscalOperationSnapshot(
        scope=ExecutionScope(
            tenant_id="synthetic-iron-tenant",
            unit_id="synthetic-iron-unit",
            environment=FiscalEnvironment.HOMOLOGATION,
            correlation_id="contract-iron-001",
            host_namespace=host_namespace,
        ),
        operation_reference=SourceReference(
            source_type="iron-billing",
            source_id="synthetic-billing-001",
        ),
        operation_kind=kind,
        occurred_at=datetime(2026, 9, 12, 2, 0, tzinfo=UTC),
        totals=FiscalOperationTotals.from_net_amount(total),
    )


def test_iron_pack_has_stable_identity_and_three_explicit_use_cases() -> None:
    descriptor = IRON_FISCAL_CONTRACT_PACK.descriptor

    assert isinstance(IRON_FISCAL_CONTRACT_PACK, IronFiscalContractPack)
    assert descriptor.pack_id == "iron"
    assert descriptor.host_namespace == "fm.iron"
    assert descriptor.version == "1"
    assert tuple(use_case.use_case_id for use_case in descriptor.use_cases) == (
        "membership-billing",
        "recurring-membership-billing",
        "fitness-service-billing",
    )


def test_iron_membership_billing_maps_membership_to_nfse() -> None:
    use_case = IRON_MEMBERSHIP_BILLING

    assert use_case.operation_kinds == frozenset({FiscalOperationKind.MEMBERSHIP})
    assert use_case.document_kinds == frozenset({FiscalDocumentKind.NFSE})
    assert use_case.vertical_module_id == "fitness"
    assert use_case.required_vertical_capabilities == frozenset({"operation.membership"})


def test_iron_recurring_and_service_use_cases_are_distinct() -> None:
    assert IRON_RECURRING_MEMBERSHIP_BILLING.operation_kinds == frozenset(
        {FiscalOperationKind.RECURRING_CHARGE}
    )
    assert IRON_RECURRING_MEMBERSHIP_BILLING.required_vertical_capabilities == frozenset(
        {"operation.recurring"}
    )
    assert IRON_SERVICE_BILLING.operation_kinds == frozenset({FiscalOperationKind.SERVICE})
    assert IRON_SERVICE_BILLING.required_vertical_capabilities == frozenset(
        {"operation.service"}
    )
    assert IRON_SERVICE_BILLING.document_kinds == frozenset({FiscalDocumentKind.NFSE})


def test_iron_nfse_contract_does_not_claim_inutilization_or_contingency() -> None:
    for use_case in IRON_FISCAL_CONTRACT_PACK.descriptor.use_cases:
        assert FiscalActionCapability.ISSUE in use_case.fiscal_actions
        assert FiscalActionCapability.QUERY in use_case.fiscal_actions
        assert FiscalActionCapability.CANCEL in use_case.fiscal_actions
        assert FiscalActionCapability.INUTILIZE not in use_case.fiscal_actions
        assert FiscalActionCapability.CONTINGENCY not in use_case.fiscal_actions
        assert not hasattr(use_case, "readiness")


def test_iron_pack_validates_explicit_fitness_vertical() -> None:
    IRON_FISCAL_CONTRACT_PACK.descriptor.validate_vertical_contracts(
        VerticalModuleRegistry((FITNESS_VERTICAL,))
    )

    with pytest.raises(Exception, match="fitness"):
        IRON_FISCAL_CONTRACT_PACK.descriptor.validate_vertical_contracts(
            VerticalModuleRegistry()
        )


def test_iron_operation_requires_fm_iron_namespace_and_declared_kind() -> None:
    descriptor = IRON_FISCAL_CONTRACT_PACK.descriptor

    accepted = descriptor.validate_operation(
        use_case_id="membership-billing",
        operation=_operation(kind=FiscalOperationKind.MEMBERSHIP),
    )
    assert accepted is IRON_MEMBERSHIP_BILLING

    with pytest.raises(ProductOperationContractError, match="host namespace mismatch"):
        descriptor.validate_operation(
            use_case_id="membership-billing",
            operation=_operation(
                kind=FiscalOperationKind.MEMBERSHIP,
                host_namespace="fm.kordena",
            ),
        )

    with pytest.raises(ProductOperationContractError, match="operation kind"):
        descriptor.validate_operation(
            use_case_id="membership-billing",
            operation=_operation(kind=FiscalOperationKind.SERVICE),
        )


def test_iron_pack_registers_by_exact_host_namespace() -> None:
    registry = ProductContractPackRegistry((IRON_FISCAL_CONTRACT_PACK,))

    assert registry.require("iron") is IRON_FISCAL_CONTRACT_PACK
    assert registry.require_for_host("fm.iron") is IRON_FISCAL_CONTRACT_PACK
    assert registry.host_namespaces == ("fm.iron",)


def test_iron_declared_events_exist_in_public_asyncapi_contract() -> None:
    asyncapi = json.loads(Path("contracts/v1/asyncapi.json").read_text(encoding="utf-8"))
    public_event_types = {
        channel["address"] for channel in asyncapi["channels"].values()
    }

    for use_case in IRON_FISCAL_CONTRACT_PACK.descriptor.use_cases:
        assert set(use_case.inbound_event_types) <= public_event_types
        assert use_case.outbound_event_types == ()


def test_iron_pack_contains_no_restaurant_or_other_product_contract() -> None:
    rendered = repr(IRON_FISCAL_CONTRACT_PACK.descriptor)

    assert "restaurant" not in rendered
    assert "fm.kordena" not in rendered
    assert "fm.vendedor-ia" not in rendered
    assert "fm.campaia" not in rendered
