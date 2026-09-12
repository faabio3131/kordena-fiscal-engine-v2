from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from kordena_fiscal.compliance import FiscalActionCapability
from kordena_fiscal.contract_packs import (
    CAMPAIA_FISCAL_CONTRACT_PACK,
    CAMPAIA_HOST_NAMESPACE,
    CAMPAIA_SAAS_BILLING,
    CAMPAIA_SERVICE_BILLING,
    CampaiaFiscalContractPack,
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
from kordena_fiscal.verticals import (
    SAAS_VERTICAL,
    SERVICE_VERTICAL,
    VerticalModuleRegistry,
)


def _operation(
    *,
    kind: FiscalOperationKind,
    host_namespace: str = CAMPAIA_HOST_NAMESPACE,
) -> FiscalOperationSnapshot:
    total = Money(Decimal("499.00"))
    return FiscalOperationSnapshot(
        scope=ExecutionScope(
            tenant_id="synthetic-campaia-tenant",
            unit_id="synthetic-campaia-unit",
            environment=FiscalEnvironment.HOMOLOGATION,
            correlation_id="contract-campaia-001",
            host_namespace=host_namespace,
        ),
        operation_reference=SourceReference(
            source_type="campaia-own-billing",
            source_id="synthetic-billing-001",
        ),
        operation_kind=kind,
        occurred_at=datetime(2026, 9, 12, 4, 0, tzinfo=UTC),
        totals=FiscalOperationTotals.from_net_amount(total),
    )


def test_campaia_pack_has_stable_identity_and_two_explicit_use_cases() -> None:
    descriptor = CAMPAIA_FISCAL_CONTRACT_PACK.descriptor

    assert isinstance(CAMPAIA_FISCAL_CONTRACT_PACK, CampaiaFiscalContractPack)
    assert descriptor.pack_id == "campaia"
    assert descriptor.host_namespace == "fm.campaia"
    assert descriptor.version == "1"
    assert tuple(use_case.use_case_id for use_case in descriptor.use_cases) == (
        "service-billing",
        "saas-billing",
    )


def test_campaia_service_billing_maps_service_to_nfse_and_service_vertical() -> None:
    use_case = CAMPAIA_SERVICE_BILLING

    assert use_case.operation_kinds == frozenset({FiscalOperationKind.SERVICE})
    assert use_case.document_kinds == frozenset({FiscalDocumentKind.NFSE})
    assert use_case.vertical_module_id == "service"
    assert use_case.required_vertical_capabilities == frozenset({"operation.service"})


def test_campaia_saas_billing_maps_saas_to_nfse_and_neutral_saas_vertical() -> None:
    use_case = CAMPAIA_SAAS_BILLING

    assert use_case.operation_kinds == frozenset({FiscalOperationKind.SAAS_BILLING})
    assert use_case.document_kinds == frozenset({FiscalDocumentKind.NFSE})
    assert use_case.vertical_module_id == "saas"
    assert use_case.required_vertical_capabilities == frozenset(
        {"operation.service", "operation.subscription"}
    )


def test_campaia_nfse_contract_does_not_overclaim_actions_or_readiness() -> None:
    for use_case in CAMPAIA_FISCAL_CONTRACT_PACK.descriptor.use_cases:
        assert FiscalActionCapability.ISSUE in use_case.fiscal_actions
        assert FiscalActionCapability.QUERY in use_case.fiscal_actions
        assert FiscalActionCapability.CANCEL in use_case.fiscal_actions
        assert FiscalActionCapability.RECONCILE in use_case.fiscal_actions
        assert FiscalActionCapability.INUTILIZE not in use_case.fiscal_actions
        assert FiscalActionCapability.CONTINGENCY not in use_case.fiscal_actions
        assert not hasattr(use_case, "readiness")
    assert not hasattr(CAMPAIA_FISCAL_CONTRACT_PACK.descriptor, "production_approved")


def test_campaia_pack_requires_both_explicit_neutral_verticals() -> None:
    registry = VerticalModuleRegistry((SERVICE_VERTICAL, SAAS_VERTICAL))
    CAMPAIA_FISCAL_CONTRACT_PACK.descriptor.validate_vertical_contracts(registry)

    with pytest.raises(Exception, match="saas"):
        CAMPAIA_FISCAL_CONTRACT_PACK.descriptor.validate_vertical_contracts(
            VerticalModuleRegistry((SERVICE_VERTICAL,))
        )

    with pytest.raises(Exception, match="service"):
        CAMPAIA_FISCAL_CONTRACT_PACK.descriptor.validate_vertical_contracts(
            VerticalModuleRegistry((SAAS_VERTICAL,))
        )


def test_campaia_operation_requires_exact_namespace_and_declared_kind() -> None:
    descriptor = CAMPAIA_FISCAL_CONTRACT_PACK.descriptor

    accepted = descriptor.validate_operation(
        use_case_id="saas-billing",
        operation=_operation(kind=FiscalOperationKind.SAAS_BILLING),
    )
    assert accepted is CAMPAIA_SAAS_BILLING

    with pytest.raises(ProductOperationContractError, match="host namespace mismatch"):
        descriptor.validate_operation(
            use_case_id="saas-billing",
            operation=_operation(
                kind=FiscalOperationKind.SAAS_BILLING,
                host_namespace="fm.vendedor-ia",
            ),
        )

    with pytest.raises(ProductOperationContractError, match="operation kind"):
        descriptor.validate_operation(
            use_case_id="saas-billing",
            operation=_operation(kind=FiscalOperationKind.SUBSCRIPTION),
        )


def test_campaia_pack_does_not_infer_payment_or_missing_fiscal_facts() -> None:
    operation = _operation(kind=FiscalOperationKind.SAAS_BILLING)

    CAMPAIA_FISCAL_CONTRACT_PACK.descriptor.validate_operation(
        use_case_id="saas-billing",
        operation=operation,
    )

    assert operation.payments == ()
    assert operation.settled_at is None
    assert operation.payment_amount == Money.zero()
    assert operation.is_settled is False


def test_campaia_pack_registers_by_exact_host_namespace() -> None:
    registry = ProductContractPackRegistry((CAMPAIA_FISCAL_CONTRACT_PACK,))

    assert registry.require("campaia") is CAMPAIA_FISCAL_CONTRACT_PACK
    assert registry.require_for_host("fm.campaia") is CAMPAIA_FISCAL_CONTRACT_PACK
    assert registry.host_namespaces == ("fm.campaia",)


def test_campaia_declared_events_exist_and_descriptor_is_cross_product_isolated() -> None:
    asyncapi = json.loads(Path("contracts/v1/asyncapi.json").read_text(encoding="utf-8"))
    public_event_types = {
        channel["address"] for channel in asyncapi["channels"].values()
    }

    for use_case in CAMPAIA_FISCAL_CONTRACT_PACK.descriptor.use_cases:
        assert set(use_case.inbound_event_types) <= public_event_types
        assert use_case.outbound_event_types == ()

    rendered = repr(CAMPAIA_FISCAL_CONTRACT_PACK.descriptor)
    assert "restaurant" not in rendered
    assert "fitness" not in rendered
    assert "fm.kordena" not in rendered
    assert "fm.iron" not in rendered
    assert "fm.vendedor-ia" not in rendered
