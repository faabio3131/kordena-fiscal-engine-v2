from __future__ import annotations

import json
from pathlib import Path

import pytest

from kordena_fiscal.contract_packs.base import (
    ProductContractPackNotFoundError,
    ProductUseCaseNotFoundError,
)
from kordena_fiscal.integrations import (
    CAPABILITIES_ENDPOINT,
    IDEMPOTENCY_HEADER,
    ISSUANCES_ENDPOINT,
    QUERIES_ENDPOINT,
    RECONCILIATIONS_ENDPOINT,
    REQUIRED_SCOPE_HEADERS,
    resolve_product_integration_contract,
)


def _openapi() -> dict[str, object]:
    return json.loads(Path("contracts/v1/openapi.json").read_text(encoding="utf-8"))


def test_bridge_endpoints_declared_by_integration_contract_exist_in_openapi() -> None:
    spec = _openapi()
    paths = spec["paths"]
    assert isinstance(paths, dict)
    for endpoint in (
        CAPABILITIES_ENDPOINT,
        ISSUANCES_ENDPOINT,
        QUERIES_ENDPOINT,
        RECONCILIATIONS_ENDPOINT,
    ):
        assert endpoint in paths


def test_bridge_required_headers_and_idempotency_key_do_not_drift() -> None:
    spec = _openapi()
    components = spec["components"]
    assert isinstance(components, dict)
    parameters = components["parameters"]
    assert isinstance(parameters, dict)
    declared_header_names = {
        value["name"]
        for value in parameters.values()
        if isinstance(value, dict) and value.get("in") == "header"
    }
    assert set(REQUIRED_SCOPE_HEADERS).issubset(declared_header_names)
    assert IDEMPOTENCY_HEADER in declared_header_names


def test_iron_membership_contract_is_nfse_and_requires_readiness() -> None:
    contract = resolve_product_integration_contract("iron", "membership-billing")
    assert contract.pack_id == "iron"
    assert contract.host_namespace == "fm.iron"
    assert {kind.value for kind in contract.document_kinds} == {"nfse"}
    assert contract.capabilities_endpoint == CAPABILITIES_ENDPOINT
    assert contract.issuance_endpoint == ISSUANCES_ENDPOINT
    assert contract.readiness_required_before_mutation is True


def test_kordena_contract_resolves_without_claiming_runtime_readiness() -> None:
    contract = resolve_product_integration_contract("kordena", "restaurant-pos-sale")
    assert contract.pack_id == "kordena"
    assert contract.host_namespace == "fm.kordena"
    assert contract.readiness_required_before_mutation is True


def test_unknown_product_and_use_case_fail_closed() -> None:
    with pytest.raises(ProductContractPackNotFoundError):
        resolve_product_integration_contract("unknown-product", "billing")

    with pytest.raises(ProductUseCaseNotFoundError):
        resolve_product_integration_contract("iron", "unknown-use-case")
