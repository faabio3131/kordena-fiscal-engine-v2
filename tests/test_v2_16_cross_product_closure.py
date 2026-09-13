from __future__ import annotations

from dataclasses import replace

import pytest

from kordena_fiscal.contract_packs import (
    FM_PRODUCT_CONTRACT_PACKS,
    FM_PRODUCT_CONTRACT_REGISTRY,
    V2_10_PRODUCT_CONTRACT_MATRIX,
)
from kordena_fiscal.contract_packs.onboarding import (
    ProductMutationPreflight,
    ProductMutationPreflightError,
    validate_product_mutation_preflight,
)
from kordena_fiscal.domain import ExecutionScope, FiscalEnvironment
from kordena_fiscal.integrations import resolve_product_integration_contract
from kordena_fiscal.observability.tracing import TraceContext, TracePropagation


def _preflight_for_pack(index: int) -> ProductMutationPreflight:
    pack = FM_PRODUCT_CONTRACT_PACKS[index]
    descriptor = pack.descriptor
    use_case = descriptor.use_cases[0]
    operation = sorted(use_case.operation_kinds, key=lambda item: item.value)[0]
    document = sorted(use_case.document_kinds, key=lambda item: item.value)[0]
    action = sorted(use_case.fiscal_actions, key=lambda item: item.value)[0]
    return ProductMutationPreflight(
        pack_id=descriptor.pack_id,
        host_namespace=descriptor.host_namespace,
        use_case_id=use_case.use_case_id,
        operation_kind=operation,
        document_kind=document,
        fiscal_action=action,
        scope_headers={
            "X-FM-Host-Namespace": descriptor.host_namespace,
            "X-FM-Tenant-Id": f"tenant-{index}",
            "X-FM-Unit-Id": f"unit-{index}",
            "X-FM-Environment": "HOMOLOGATION",
            "X-Correlation-Id": f"corr-product-{index}",
        },
        idempotency_key=f"v2-16-closure:{descriptor.pack_id}:{index}",
        fiscal_binding_resolved=True,
        capability_granted=True,
        readiness_granted=True,
    )


def test_current_catalog_certifies_multiple_hosts_operations_and_document_families() -> None:
    assert len(FM_PRODUCT_CONTRACT_PACKS) == 4
    assert len(FM_PRODUCT_CONTRACT_REGISTRY.host_namespaces) == 4
    assert {row.document_kinds[0].value for row in V2_10_PRODUCT_CONTRACT_MATRIX} == {
        "nfce",
        "nfe",
        "nfse",
    }
    assert len(
        {
            operation.value
            for row in V2_10_PRODUCT_CONTRACT_MATRIX
            for operation in row.operation_kinds
        }
    ) >= 5


def test_current_product_preflights_are_isolated_by_host_tenant_unit_and_idempotency() -> None:
    requests = tuple(_preflight_for_pack(index) for index in range(4))

    for request in requests:
        validate_product_mutation_preflight(
            request,
            registry=FM_PRODUCT_CONTRACT_REGISTRY,
        )

    partitions = {
        (
            request.scope_headers["X-FM-Host-Namespace"],
            request.scope_headers["X-FM-Tenant-Id"],
            request.scope_headers["X-FM-Unit-Id"],
            request.scope_headers["X-FM-Environment"],
        )
        for request in requests
    }
    correlations = {
        request.scope_headers["X-Correlation-Id"] for request in requests
    }
    idempotency_keys = {request.idempotency_key for request in requests}

    assert len(partitions) == 4
    assert len(correlations) == 4
    assert len(idempotency_keys) == 4


def test_cross_product_scope_spoofing_fails_closed_at_current_preflight_boundary() -> None:
    first = _preflight_for_pack(0)
    second = _preflight_for_pack(1)
    spoofed_headers = dict(first.scope_headers)
    spoofed_headers["X-FM-Host-Namespace"] = second.host_namespace
    spoofed = replace(first, scope_headers=spoofed_headers)

    with pytest.raises(ProductMutationPreflightError, match="scope host namespace does not match"):
        validate_product_mutation_preflight(
            spoofed,
            registry=FM_PRODUCT_CONTRACT_REGISTRY,
        )


def test_environment_is_part_of_the_execution_partition() -> None:
    common = {
        "tenant_id": "tenant-same",
        "unit_id": "unit-same",
        "correlation_id": "corr-environment-isolation",
        "host_namespace": "fm.kordena",
    }
    homologation = ExecutionScope(
        environment=FiscalEnvironment.HOMOLOGATION,
        **common,
    )
    production = ExecutionScope(
        environment=FiscalEnvironment.PRODUCTION,
        **common,
    )

    assert homologation.identity_partition_key != production.identity_partition_key


def test_correlation_and_causation_propagation_remain_explicit_and_isolated() -> None:
    traces = tuple(
        TraceContext(
            trace_id=f"{index + 1:032x}",
            span_id=f"{index + 1:016x}",
            correlation_id=f"corr-product-{index}",
            causation_id=f"cause-product-{index}",
        )
        for index in range(4)
    )
    carriers = tuple(TracePropagation.to_carrier(trace) for trace in traces)

    assert len({carrier["x-fm-correlation-id"] for carrier in carriers}) == 4
    assert len({carrier["x-fm-causation-id"] for carrier in carriers}) == 4
    for trace, carrier in zip(traces, carriers, strict=True):
        assert TracePropagation.from_carrier(carrier) == trace


def test_every_product_integration_contract_requires_runtime_readiness() -> None:
    for pack in FM_PRODUCT_CONTRACT_PACKS:
        descriptor = pack.descriptor
        for use_case in descriptor.use_cases:
            contract = resolve_product_integration_contract(
                descriptor.pack_id,
                use_case.use_case_id,
            )
            assert contract.host_namespace == descriptor.host_namespace
            assert contract.readiness_required_before_mutation is True


def test_product_integration_surface_cannot_grant_production_approval() -> None:
    for pack in FM_PRODUCT_CONTRACT_PACKS:
        descriptor = pack.descriptor
        assert not hasattr(descriptor, "production_approved")
        for use_case in descriptor.use_cases:
            contract = resolve_product_integration_contract(
                descriptor.pack_id,
                use_case.use_case_id,
            )
            assert not hasattr(contract, "production_approved")
