from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from kordena_fiscal.compliance import FiscalActionCapability
from kordena_fiscal.contract_packs import (
    SALES_FISCAL_CONTRACT_PACK,
    SALES_HOST_NAMESPACE,
    SALES_NFCE_SALE,
    SALES_NFE_SALE,
    ProductContractPackRegistry,
    ProductOperationContractError,
    SalesFiscalContractPack,
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


def _sale(
    *,
    kind: FiscalOperationKind = FiscalOperationKind.SALE,
    host_namespace: str = SALES_HOST_NAMESPACE,
) -> FiscalOperationSnapshot:
    total = Money(Decimal("249.90"))
    return FiscalOperationSnapshot(
        scope=ExecutionScope(
            tenant_id="synthetic-sales-tenant",
            unit_id="synthetic-sales-unit",
            environment=FiscalEnvironment.HOMOLOGATION,
            correlation_id="contract-sales-001",
            host_namespace=host_namespace,
        ),
        operation_reference=SourceReference(
            source_type="vendedor-ia-sale",
            source_id="synthetic-sale-001",
        ),
        operation_kind=kind,
        occurred_at=datetime(2026, 9, 12, 3, 0, tzinfo=UTC),
        totals=FiscalOperationTotals.from_net_amount(total),
    )


def test_sales_pack_has_stable_identity_and_two_explicit_sale_use_cases() -> None:
    descriptor = SALES_FISCAL_CONTRACT_PACK.descriptor

    assert isinstance(SALES_FISCAL_CONTRACT_PACK, SalesFiscalContractPack)
    assert descriptor.pack_id == "sales"
    assert descriptor.host_namespace == "fm.vendedor-ia"
    assert descriptor.version == "1"
    assert tuple(use_case.use_case_id for use_case in descriptor.use_cases) == (
        "nfce-sale",
        "nfe-sale",
    )


def test_sales_nfce_sale_is_generic_and_vertical_free() -> None:
    use_case = SALES_NFCE_SALE

    assert use_case.operation_kinds == frozenset({FiscalOperationKind.SALE})
    assert use_case.document_kinds == frozenset({FiscalDocumentKind.NFCE})
    assert use_case.vertical_module_id is None
    assert use_case.required_vertical_capabilities == frozenset()
    assert FiscalActionCapability.ISSUE in use_case.fiscal_actions
    assert FiscalActionCapability.CONTINGENCY in use_case.fiscal_actions
    assert FiscalActionCapability.INUTILIZE not in use_case.fiscal_actions


def test_sales_nfe_sale_is_generic_and_does_not_promote_readiness() -> None:
    use_case = SALES_NFE_SALE

    assert use_case.operation_kinds == frozenset({FiscalOperationKind.SALE})
    assert use_case.document_kinds == frozenset({FiscalDocumentKind.NFE})
    assert use_case.vertical_module_id is None
    assert use_case.required_vertical_capabilities == frozenset()
    assert FiscalActionCapability.INUTILIZE in use_case.fiscal_actions
    assert FiscalActionCapability.CONTINGENCY in use_case.fiscal_actions
    assert not hasattr(use_case, "readiness")
    assert not hasattr(SALES_FISCAL_CONTRACT_PACK.descriptor, "production_approved")


def test_sales_pack_requires_no_vertical_module() -> None:
    SALES_FISCAL_CONTRACT_PACK.descriptor.validate_vertical_contracts(
        VerticalModuleRegistry()
    )


def test_sales_operation_requires_exact_namespace_and_sale_kind() -> None:
    descriptor = SALES_FISCAL_CONTRACT_PACK.descriptor

    accepted = descriptor.validate_operation(
        use_case_id="nfce-sale",
        operation=_sale(),
    )
    assert accepted is SALES_NFCE_SALE

    with pytest.raises(ProductOperationContractError, match="host namespace mismatch"):
        descriptor.validate_operation(
            use_case_id="nfce-sale",
            operation=_sale(host_namespace="fm.kordena"),
        )

    with pytest.raises(ProductOperationContractError, match="operation kind"):
        descriptor.validate_operation(
            use_case_id="nfce-sale",
            operation=_sale(kind=FiscalOperationKind.SERVICE),
        )


def test_sales_pack_does_not_infer_payment_or_settlement_authority() -> None:
    operation = _sale()

    SALES_FISCAL_CONTRACT_PACK.descriptor.validate_operation(
        use_case_id="nfe-sale",
        operation=operation,
    )

    assert operation.payments == ()
    assert operation.settled_at is None
    assert operation.payment_amount == Money.zero()
    assert operation.is_settled is False


def test_sales_pack_registers_by_exact_vendedor_ia_namespace() -> None:
    registry = ProductContractPackRegistry((SALES_FISCAL_CONTRACT_PACK,))

    assert registry.require("sales") is SALES_FISCAL_CONTRACT_PACK
    assert registry.require_for_host("fm.vendedor-ia") is SALES_FISCAL_CONTRACT_PACK
    assert registry.host_namespaces == ("fm.vendedor-ia",)


def test_sales_declared_events_exist_in_public_asyncapi_contract() -> None:
    asyncapi = json.loads(Path("contracts/v1/asyncapi.json").read_text(encoding="utf-8"))
    public_event_types = {
        channel["address"] for channel in asyncapi["channels"].values()
    }

    declared = set(SALES_NFCE_SALE.inbound_event_types)
    assert declared == set(SALES_NFE_SALE.inbound_event_types)
    assert declared <= public_event_types
    assert SALES_NFCE_SALE.outbound_event_types == ()
    assert SALES_NFE_SALE.outbound_event_types == ()


def test_sales_pack_contains_no_vertical_or_other_product_contract() -> None:
    rendered = repr(SALES_FISCAL_CONTRACT_PACK.descriptor)

    assert "restaurant" not in rendered
    assert "fitness" not in rendered
    assert "saas" not in rendered
    assert "fm.kordena" not in rendered
    assert "fm.iron" not in rendered
    assert "fm.campaia" not in rendered
