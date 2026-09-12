from __future__ import annotations

import ast
import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from kordena_fiscal.contract_packs import (
    FM_PRODUCT_CONTRACT_PACKS,
    FM_PRODUCT_CONTRACT_REGISTRY,
    V2_10_PRODUCT_CONTRACT_MATRIX,
    ProductOperationContractError,
)
from kordena_fiscal.domain import (
    ExecutionScope,
    FiscalEnvironment,
    Money,
    SourceReference,
)
from kordena_fiscal.operations import FiscalOperationSnapshot, FiscalOperationTotals
from kordena_fiscal.verticals import (
    FITNESS_VERTICAL,
    SAAS_VERTICAL,
    SERVICE_VERTICAL,
    VerticalModuleRegistry,
)
from kordena_fiscal.verticals.restaurant import RestaurantVerticalModule

_EXPECTED_HOSTS = (
    "fm.campaia",
    "fm.iron",
    "fm.kordena",
    "fm.vendedor-ia",
)


def _operation(*, host_namespace: str, operation_kind: object) -> FiscalOperationSnapshot:
    from kordena_fiscal.operations import FiscalOperationKind

    assert isinstance(operation_kind, FiscalOperationKind)
    return FiscalOperationSnapshot(
        scope=ExecutionScope(
            tenant_id="synthetic-cross-product-tenant",
            unit_id="synthetic-cross-product-unit",
            environment=FiscalEnvironment.HOMOLOGATION,
            correlation_id=f"cross-product-{host_namespace}",
            host_namespace=host_namespace,
        ),
        operation_reference=SourceReference(
            source_type="cross-product-certification",
            source_id=f"synthetic-{host_namespace}",
        ),
        operation_kind=operation_kind,
        occurred_at=datetime(2026, 9, 12, 5, 0, tzinfo=UTC),
        totals=FiscalOperationTotals.from_net_amount(Money(Decimal("100.00"))),
    )


def test_catalog_contains_exactly_four_unique_product_namespaces() -> None:
    assert len(FM_PRODUCT_CONTRACT_PACKS) == 4
    assert FM_PRODUCT_CONTRACT_REGISTRY.pack_ids == (
        "campaia",
        "iron",
        "kordena",
        "sales",
    )
    assert FM_PRODUCT_CONTRACT_REGISTRY.host_namespaces == _EXPECTED_HOSTS


def test_versioned_contract_matrix_has_all_nine_declared_use_cases() -> None:
    rows = V2_10_PRODUCT_CONTRACT_MATRIX

    assert len(rows) == 9
    assert all(row.pack_version == "1" for row in rows)
    assert len({(row.pack_id, row.use_case_id) for row in rows}) == 9
    assert {row.host_namespace for row in rows} == set(_EXPECTED_HOSTS)


def test_contract_matrix_preserves_expected_product_boundaries() -> None:
    summary = {
        (row.pack_id, row.use_case_id): (
            tuple(kind.value for kind in row.operation_kinds),
            tuple(kind.value for kind in row.document_kinds),
            row.vertical_module_id,
        )
        for row in V2_10_PRODUCT_CONTRACT_MATRIX
    }

    assert summary == {
        ("kordena", "restaurant-pos-sale"): (("sale",), ("nfce",), "restaurant"),
        ("kordena", "restaurant-invoice-sale"): (("sale",), ("nfe",), "restaurant"),
        ("iron", "membership-billing"): (("membership",), ("nfse",), "fitness"),
        ("iron", "recurring-membership-billing"): (
            ("recurring_charge",),
            ("nfse",),
            "fitness",
        ),
        ("iron", "fitness-service-billing"): (("service",), ("nfse",), "fitness"),
        ("sales", "nfce-sale"): (("sale",), ("nfce",), None),
        ("sales", "nfe-sale"): (("sale",), ("nfe",), None),
        ("campaia", "service-billing"): (("service",), ("nfse",), "service"),
        ("campaia", "saas-billing"): (("saas_billing",), ("nfse",), "saas"),
    }


def test_every_pack_accepts_its_own_host_and_rejects_every_other_host() -> None:
    hosts = [pack.descriptor.host_namespace for pack in FM_PRODUCT_CONTRACT_PACKS]

    for pack in FM_PRODUCT_CONTRACT_PACKS:
        descriptor = pack.descriptor
        use_case = descriptor.use_cases[0]
        operation_kind = next(iter(use_case.operation_kinds))
        accepted = descriptor.validate_operation(
            use_case_id=use_case.use_case_id,
            operation=_operation(
                host_namespace=descriptor.host_namespace,
                operation_kind=operation_kind,
            ),
        )
        assert accepted is use_case

        for other_host in hosts:
            if other_host == descriptor.host_namespace:
                continue
            with pytest.raises(ProductOperationContractError, match="host namespace mismatch"):
                descriptor.validate_operation(
                    use_case_id=use_case.use_case_id,
                    operation=_operation(
                        host_namespace=other_host,
                        operation_kind=operation_kind,
                    ),
                )


def test_all_vertical_contracts_validate_against_governed_vertical_registry() -> None:
    registry = VerticalModuleRegistry(
        (
            RestaurantVerticalModule(),
            FITNESS_VERTICAL,
            SERVICE_VERTICAL,
            SAAS_VERTICAL,
        )
    )

    for pack in FM_PRODUCT_CONTRACT_PACKS:
        pack.descriptor.validate_vertical_contracts(registry)


def test_all_matrix_events_are_public_and_no_pack_invents_outbound_events() -> None:
    asyncapi = json.loads(Path("contracts/v1/asyncapi.json").read_text(encoding="utf-8"))
    public_event_types = {
        channel["address"] for channel in asyncapi["channels"].values()
    }

    for row in V2_10_PRODUCT_CONTRACT_MATRIX:
        assert set(row.inbound_event_types) <= public_event_types
        assert row.outbound_event_types == ()


def test_matrix_contains_no_readiness_or_production_approval_authority() -> None:
    for pack in FM_PRODUCT_CONTRACT_PACKS:
        descriptor = pack.descriptor
        assert not hasattr(descriptor, "readiness")
        assert not hasattr(descriptor, "production_approved")
        for use_case in descriptor.use_cases:
            assert not hasattr(use_case, "readiness")
            assert not hasattr(use_case, "production_approved")


def test_product_pack_modules_do_not_import_each_other_or_private_saas_domains() -> None:
    pack_paths = (
        Path("src/kordena_fiscal/contract_packs/kordena.py"),
        Path("src/kordena_fiscal/contract_packs/iron.py"),
        Path("src/kordena_fiscal/contract_packs/sales.py"),
        Path("src/kordena_fiscal/contract_packs/campaia.py"),
    )
    forbidden_import_tokens = (
        "contract_packs.kordena",
        "contract_packs.iron",
        "contract_packs.sales",
        "contract_packs.campaia",
        "kordena_app",
        "iron_fit",
        "vendedor_ia",
        "campaia_app",
    )

    for path in pack_paths:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported_modules: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                imported_modules.append(node.module)
            elif isinstance(node, ast.Import):
                imported_modules.extend(alias.name for alias in node.names)
        rendered = "\n".join(imported_modules)
        assert not any(token in rendered for token in forbidden_import_tokens)
