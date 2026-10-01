from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
HELPER = ROOT / "scripts" / "deploy" / "railway_graphql.py"


def _load_helper() -> ModuleType:
    spec = importlib.util.spec_from_file_location("nfcore_railway_graphql", HELPER)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _Response:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")


def test_railway_graphql_rollback_uses_bearer_token_without_printing_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    helper = _load_helper()
    secret = "synthetic-secret-never-print"
    monkeypatch.setenv("RAILWAY_API_TOKEN", secret)
    captured: dict[str, object] = {}

    def fake_urlopen(request: Any, timeout: int) -> _Response:
        captured["authorization"] = request.headers.get("Authorization")
        captured["timeout"] = timeout
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return _Response(
            {
                "data": {
                    "deploymentRollback": {
                        "id": "rollback-deployment",
                        "status": "QUEUED",
                    }
                }
            }
        )

    monkeypatch.setattr(helper, "urlopen", fake_urlopen)

    result = helper.rollback_deployment("baseline-deployment")

    assert result == ("rollback-deployment", "QUEUED")
    assert captured["authorization"] == f"Bearer {secret}"
    assert captured["timeout"] == 20
    assert captured["payload"] == {
        "query": helper._ROLLBACK_MUTATION,
        "variables": {"id": "baseline-deployment"},
    }


def test_railway_graphql_errors_are_redacted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    helper = _load_helper()
    secret = "synthetic-secret-never-print"
    monkeypatch.setenv("RAILWAY_API_TOKEN", secret)

    def fake_urlopen(_request: Any, timeout: int) -> _Response:
        assert timeout == 20
        return _Response(
            {
                "errors": [
                    {
                        "message": f"provider leaked {secret}",
                        "extensions": {"code": "INTERNAL_SERVER_ERROR"},
                    }
                ],
                "data": None,
            }
        )

    monkeypatch.setattr(helper, "urlopen", fake_urlopen)

    with pytest.raises(helper.RailwayGraphQLError) as exc_info:
        helper.rollback_deployment("baseline-deployment")

    assert "mutation failed" in str(exc_info.value)
    assert secret not in str(exc_info.value)
