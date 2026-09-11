"""V2-06 compatibility checks between readiness authority and Bridge v1 contracts."""

from __future__ import annotations

import json
from pathlib import Path

from kordena_fiscal.compliance import FiscalActionCapability, FiscalCapabilityLevel
from kordena_fiscal.domain import FiscalDocumentKind

ROOT = Path(__file__).resolve().parents[2]
CONTRACT_ROOT = ROOT / "contracts" / "v1"
SCHEMA_PATH = CONTRACT_ROOT / "schemas" / "fm-fiscal.schema.json"
OPENAPI_PATH = CONTRACT_ROOT / "openapi.json"


def _load(path: Path) -> dict[str, object]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    assert isinstance(value, dict)
    return value


def test_capability_response_matches_v2_06_authority_vocabulary() -> None:
    schema = _load(SCHEMA_PATH)
    defs = schema["$defs"]
    assert isinstance(defs, dict)
    response = defs["CapabilityResponse"]
    assert isinstance(response, dict)
    properties = response["properties"]
    assert isinstance(properties, dict)

    readiness = properties["readiness"]
    assert isinstance(readiness, dict)
    assert readiness["enum"] == [level.name for level in FiscalCapabilityLevel]

    capabilities = properties["capabilities"]
    assert isinstance(capabilities, dict)
    items = capabilities["items"]
    assert isinstance(items, dict)
    expected = [
        *(kind.value for kind in FiscalDocumentKind),
        *(action.value for action in FiscalActionCapability),
    ]
    assert items["enum"] == expected

    provenance = properties["provenance"]
    assert isinstance(provenance, dict)
    assert provenance["maxLength"] == 512


def test_capability_endpoint_remains_s2s_protected_and_contract_compatible() -> None:
    openapi = _load(OPENAPI_PATH)
    assert openapi["info"]["version"] == "1.1.0"  # type: ignore[index]
    assert openapi["security"] == [
        {"FMWorkloadBearer": [], "FMWorkloadCredentialId": []}
    ]

    paths = openapi["paths"]
    assert isinstance(paths, dict)
    endpoint = paths["/v1/capabilities/query"]
    assert isinstance(endpoint, dict)
    operation = endpoint["post"]
    assert isinstance(operation, dict)
    assert operation["operationId"] == "queryCapabilities"

    request_ref = operation["requestBody"]["content"]["application/json"]["schema"]["$ref"]  # type: ignore[index]
    assert request_ref.endswith("#/$defs/CapabilityRequest")
    response_ref = operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]  # type: ignore[index]
    assert response_ref.endswith("#/$defs/CapabilityResponse")
    assert {"401", "403", "429"} <= set(operation["responses"])
