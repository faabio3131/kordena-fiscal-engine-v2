"""Contract lint for the language-neutral FM Fiscal Bridge v1 artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CONTRACT_ROOT = ROOT / "contracts" / "v1"
SCHEMA_PATH = CONTRACT_ROOT / "schemas" / "fm-fiscal.schema.json"
OPENAPI_PATH = CONTRACT_ROOT / "openapi.json"
ASYNCAPI_PATH = CONTRACT_ROOT / "asyncapi.json"
MANIFEST_PATH = CONTRACT_ROOT / "manifest.json"


def _load(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    assert isinstance(value, dict)
    return value


def _schema_ref_name(value: str) -> str:
    prefix = "./schemas/fm-fiscal.schema.json#/$defs/"
    assert value.startswith(prefix), value
    return value.removeprefix(prefix)


def _operation(openapi: dict[str, Any], path: str) -> dict[str, Any]:
    value = openapi["paths"][path]["post"]
    assert isinstance(value, dict)
    return value


def _parameter_names(openapi: dict[str, Any], operation: dict[str, Any]) -> set[str]:
    components = openapi["components"]["parameters"]
    names: set[str] = set()
    for parameter in operation["parameters"]:
        ref = parameter["$ref"]
        name = ref.removeprefix("#/components/parameters/")
        assert name in components
        names.add(components[name]["name"])
    return names


def test_manifest_and_artifacts_are_versioned_json_contracts() -> None:
    manifest = _load(MANIFEST_PATH)
    assert manifest["name"] == "FM Fiscal Bridge"
    assert manifest["contract_version"] == "1.0.0"
    assert manifest["status"] == "CONTRACT_ONLY"
    assert manifest["openapi"] == "openapi.json"
    assert manifest["asyncapi"] == "asyncapi.json"
    assert manifest["canonical_schema"] == "schemas/fm-fiscal.schema.json"

    for path in (SCHEMA_PATH, OPENAPI_PATH, ASYNCAPI_PATH, MANIFEST_PATH):
        assert path.is_file()
        _load(path)


def test_public_contracts_are_fm_fiscal_and_language_neutral() -> None:
    public_text = "\n".join(
        path.read_text(encoding="utf-8").lower()
        for path in (SCHEMA_PATH, OPENAPI_PATH, ASYNCAPI_PATH, MANIFEST_PATH)
    )
    assert "kordena" not in public_text
    assert "kordena_fiscal" not in public_text
    assert "python" not in public_text
    assert "sqlalchemy" not in public_text
    assert "postgres" not in public_text


def test_json_schema_exposes_all_canonical_bridge_shapes() -> None:
    schema = _load(SCHEMA_PATH)
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    defs = schema["$defs"]

    required = {
        "HostScope",
        "FiscalOperation",
        "IssuanceRequest",
        "IssuanceResponse",
        "QueryRequest",
        "QueryResponse",
        "CancellationRequest",
        "CancellationResponse",
        "InutilizationRequest",
        "InutilizationResponse",
        "CapabilityRequest",
        "CapabilityResponse",
        "ReconciliationRequest",
        "ReconciliationResponse",
        "ArchiveReferenceQuery",
        "ArchiveReference",
        "CanonicalError",
        "EventEnvelope",
    }
    assert required <= set(defs)

    assert defs["FiscalOperation"]["properties"]["operation_kind"]["enum"] == [
        "sale",
        "membership",
        "subscription",
        "service",
        "recurring_charge",
        "saas_billing",
        "other",
    ]
    assert set(defs["HostScope"]["required"]) == {
        "host_namespace",
        "tenant_id",
        "unit_id",
        "environment",
    }
    assert defs["CapabilityResponse"]["properties"]["readiness"]["enum"] == [
        "CONTRACT_ONLY",
        "HOMOLOGATION_READY",
        "PRODUCTION_APPROVED",
    ]


def test_openapi_covers_bridge_operations_and_transport_metadata() -> None:
    openapi = _load(OPENAPI_PATH)
    assert openapi["openapi"] == "3.1.0"
    assert openapi["info"]["version"] == "1.0.0"
    assert openapi["x-fm-contract-readiness"] == "CONTRACT_ONLY"
    assert openapi["security"] == []

    expected_paths = {
        "/v1/issuances",
        "/v1/queries",
        "/v1/cancellations",
        "/v1/inutilizations",
        "/v1/capabilities/query",
        "/v1/reconciliations",
        "/v1/archive/references/query",
    }
    assert set(openapi["paths"]) == expected_paths

    scope_headers = {
        "X-FM-Host-Namespace",
        "X-FM-Tenant-Id",
        "X-FM-Unit-Id",
        "X-FM-Environment",
        "X-Correlation-Id",
        "X-Causation-Id",
    }
    mutation_paths = {
        "/v1/issuances",
        "/v1/cancellations",
        "/v1/inutilizations",
        "/v1/reconciliations",
    }

    for path in expected_paths:
        operation = _operation(openapi, path)
        names = _parameter_names(openapi, operation)
        assert scope_headers <= names
        if path in mutation_paths:
            assert "Idempotency-Key" in names
        else:
            assert "Idempotency-Key" not in names

        request_ref = operation["requestBody"]["content"]["application/json"]["schema"]["$ref"]
        assert _schema_ref_name(request_ref) in _load(SCHEMA_PATH)["$defs"]

        for response in operation["responses"].values():
            content = response.get("content")
            if content is None:
                continue
            ref = content["application/json"]["schema"]["$ref"]
            assert _schema_ref_name(ref) in _load(SCHEMA_PATH)["$defs"]


def test_openapi_declares_no_live_server_or_v2_05_security_scheme() -> None:
    openapi = _load(OPENAPI_PATH)
    assert openapi["servers"] == [
        {
            "description": (
                "Non-routable documentation placeholder; "
                "no production endpoint is declared by this contract."
            ),
            "url": "https://fiscal.invalid",
        }
    ]
    assert "securitySchemes" not in openapi["components"]
    assert openapi["x-fm-authentication-stage"] == "V2-05"


def test_asyncapi_exposes_versioned_event_envelopes() -> None:
    asyncapi = _load(ASYNCAPI_PATH)
    schema = _load(SCHEMA_PATH)
    assert asyncapi["asyncapi"] == "3.0.0"
    assert asyncapi["info"]["version"] == "1.0.0"
    assert asyncapi["x-fm-contract-readiness"] == "CONTRACT_ONLY"

    addresses = {channel["address"] for channel in asyncapi["channels"].values()}
    assert addresses == {
        "fiscal.issuance.updated",
        "fiscal.document.authorized",
        "fiscal.document.rejected",
        "fiscal.document.cancelled",
        "fiscal.reconciliation.updated",
        "fiscal.archive.reference.created",
    }

    for message in asyncapi["components"]["messages"].values():
        all_of = message["payload"]["allOf"]
        envelope_ref = all_of[0]["$ref"]
        assert _schema_ref_name(envelope_ref) == "EventEnvelope"
        assert "EventEnvelope" in schema["$defs"]
        event_type = all_of[1]["properties"]["event_type"]["const"]
        assert event_type in addresses


def test_canonical_error_is_provider_neutral_and_correlatable() -> None:
    error = _load(SCHEMA_PATH)["$defs"]["CanonicalError"]["properties"]["error"]
    assert set(error["required"]) == {
        "code",
        "category",
        "message",
        "retryable",
        "correlation_id",
        "details",
    }
    serialized = json.dumps(error).lower()
    assert "provider_request_id" not in serialized
    assert "raw_response" not in serialized
    assert "xml" not in serialized
