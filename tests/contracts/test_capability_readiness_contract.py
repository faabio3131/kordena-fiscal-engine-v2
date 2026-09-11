"""V2-06 compatibility checks between readiness authority and Bridge v1 contracts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from kordena_fiscal.compliance import FiscalActionCapability, FiscalCapabilityLevel
from kordena_fiscal.domain import FiscalDocumentKind

ROOT = Path(__file__).resolve().parents[2]
CONTRACT_ROOT = ROOT / "contracts" / "v1"
SCHEMA_PATH = CONTRACT_ROOT / "schemas" / "fm-fiscal.schema.json"
OPENAPI_PATH = CONTRACT_ROOT / "openapi.json"


def _load(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    assert isinstance(value, dict)
    return value


def test_capability_response_matches_v2_06_authority_vocabulary() -> None:
    schema = _load(SCHEMA_PATH)
    properties = schema["$defs"]["CapabilityResponse"]["properties"]

    assert properties["readiness"]["enum"] == [
        level.name for level in FiscalCapabilityLevel
    ]
    expected = [
        *(kind.value for kind in FiscalDocumentKind),
        *(action.value for action in FiscalActionCapability),
    ]
    assert properties["capabilities"]["items"]["enum"] == expected
    assert properties["provenance"]["maxLength"] == 512


def test_capability_endpoint_remains_s2s_protected_and_contract_compatible() -> None:
    openapi = _load(OPENAPI_PATH)
    assert openapi["info"]["version"] == "1.1.0"
    assert openapi["security"] == [
        {"FMWorkloadBearer": [], "FMWorkloadCredentialId": []}
    ]

    operation = openapi["paths"]["/v1/capabilities/query"]["post"]
    assert operation["operationId"] == "queryCapabilities"

    request_schema = operation["requestBody"]["content"]["application/json"]["schema"]
    assert request_schema["$ref"].endswith("#/$defs/CapabilityRequest")

    response_schema = operation["responses"]["200"]["content"]["application/json"][
        "schema"
    ]
    assert response_schema["$ref"].endswith("#/$defs/CapabilityResponse")
    assert {"401", "403", "429"} <= set(operation["responses"])
