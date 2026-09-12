from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from kordena_fiscal.compliance import FiscalActionCapability
from kordena_fiscal.contract_packs import (
    KORDENA_FISCAL_CONTRACT_PACK,
    KORDENA_HOST_NAMESPACE,
    KORDENA_RESTAURANT_INVOICE_SALE,
    KORDENA_RESTAURANT_POS_SALE,
    KordenaFiscalContractPack,
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
from kordena_fiscal.verticals import VerticalModuleRegistry
from kordena_fiscal.verticals.restaurant import RestaurantVerticalModule


def _sale(*, host_namespace: str = KORDENA_HOST_NAMESPACE) -> FiscalOperationSnapshot:
    total = Money(Decimal("89.90"))
    return FiscalOperationSnapshot(
        scope=ExecutionScope(
            tenant_id="synthetic-kordena-tenant",
            unit_id="synthetic-kordena-unit",
            environment=FiscalEnvironment.HOMOLOGATION,
            correlation_id="contract-kordena-001",
            host_namespace=host_namespace,
        ),
        operation_reference=SourceReference(
            source_type="kordena-sale",
            source_id="synthetic-sale-001",
        ),
        operation_kind=FiscalOperationKind.SALE,
        occurred_at=datetime(2026, 9, 12, 1, 30, tzinfo=UTC),
        totals=FiscalOperationTotals.from_net_amount(total),
    )


def test_kordena_pack_has_stable_identity_and_explicit_sale_use_cases() -> None:
    descriptor = KORDENA_FISCAL_CONTRACT_PACK.descriptor

    assert isinstance(KORDENA_FISCAL_CONTRACT_PACK, KordenaFiscalContractPack)
    assert descriptor.pack_id == "kordena"
    assert descriptor.host_namespace == "fm.kordena"
    assert descriptor.version == "1"
    assert tuple(use_case.use_case_id for use_case in descriptor.use_cases) == (
        "restaurant-pos-sale",
        "restaurant-invoice-sale",
    )


def test_kordena_pos_sale_is_nfce_and_requires_restaurant_vertical() -> None:
    use_case = KORDENA_RESTAURANT_POS_SALE

    assert use_case.operation_kinds == frozenset({FiscalOperationKind.SALE})
    assert use_case.document_kinds == frozenset({FiscalDocumentKind.NFCE})
    assert use_case.vertical_module_id == "restaurant"
    assert use_case.required_vertical_capabilities == frozenset(
        {
            "tax.restaurant.supply-classification",
            "tax.restaurant.base-adjustments",
        }
    )
    assert FiscalActionCapability.ISSUE in use_case.fiscal_actions
    assert FiscalActionCapability.CONTINGENCY in use_case.fiscal_actions
    assert FiscalActionCapability.INUTILIZE not in use_case.fiscal_actions


def test_kordena_invoice_sale_is_nfe_without_promoting_readiness() -> None:
    use_case = KORDENA_RESTAURANT_INVOICE_SALE

    assert use_case.document_kinds == frozenset({FiscalDocumentKind.NFE})
    assert FiscalActionCapability.ISSUE in use_case.fiscal_actions
    assert FiscalActionCapability.INUTILIZE in use_case.fiscal_actions
    assert not hasattr(use_case, "readiness")
    assert not hasattr(KORDENA_FISCAL_CONTRACT_PACK.descriptor, "production_approved")


def test_kordena_pack_validates_explicit_restaurant_module_and_capabilities() -> None:
    registry = VerticalModuleRegistry((RestaurantVerticalModule(),))

    KORDENA_FISCAL_CONTRACT_PACK.descriptor.validate_vertical_contracts(registry)

    with pytest.raises(Exception, match="restaurant"):
        KORDENA_FISCAL_CONTRACT_PACK.descriptor.validate_vertical_contracts(
            VerticalModuleRegistry()
        )


def test_kordena_operation_requires_fm_kordena_namespace() -> None:
    descriptor = KORDENA_FISCAL_CONTRACT_PACK.descriptor

    accepted = descriptor.validate_operation(
        use_case_id="restaurant-pos-sale",
        operation=_sale(),
    )
    assert accepted is KORDENA_RESTAURANT_POS_SALE

    with pytest.raises(ProductOperationContractError, match="host namespace mismatch"):
        descriptor.validate_operation(
            use_case_id="restaurant-pos-sale",
            operation=_sale(host_namespace="fm.iron"),
        )


def test_kordena_pack_registers_by_exact_host_namespace() -> None:
    registry = ProductContractPackRegistry((KORDENA_FISCAL_CONTRACT_PACK,))

    assert registry.require("kordena") is KORDENA_FISCAL_CONTRACT_PACK
    assert registry.require_for_host("fm.kordena") is KORDENA_FISCAL_CONTRACT_PACK
    assert registry.host_namespaces == ("fm.kordena",)


def test_kordena_declared_events_exist_in_public_asyncapi_contract() -> None:
    asyncapi = json.loads(Path("contracts/v1/asyncapi.json").read_text(encoding="utf-8"))
    public_event_types = {
        channel["address"] for channel in asyncapi["channels"].values()
    }

    declared = set(KORDENA_RESTAURANT_POS_SALE.inbound_event_types)
    assert declared == set(KORDENA_RESTAURANT_INVOICE_SALE.inbound_event_types)
    assert declared <= public_event_types
    assert KORDENA_RESTAURANT_POS_SALE.outbound_event_types == ()


def test_kordena_pack_does_not_expose_other_product_namespaces() -> None:
    descriptor = KORDENA_FISCAL_CONTRACT_PACK.descriptor
    rendered = repr(descriptor)

    assert "fm.iron" not in rendered
    assert "fm.vendedor-ia" not in rendered
    assert "fm.campaia" not in rendered
