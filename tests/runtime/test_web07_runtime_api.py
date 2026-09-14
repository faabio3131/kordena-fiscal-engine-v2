from __future__ import annotations

from fastapi.testclient import TestClient

from kordena_fiscal.runtime import api as runtime_api
from kordena_fiscal.runtime.config import RuntimeSettings


def _postgres_settings() -> RuntimeSettings:
    return RuntimeSettings.from_mapping(
        {
            "NFCORE_ENVIRONMENT": "staging",
            "NFCORE_PERSISTENCE_BACKEND": "postgres",
            "DATABASE_URL": "postgresql://user:password@db:5432/nfcore",
            "NFCORE_SECRET_BACKEND": "external",
            "NFCORE_REQUIRE_HTTPS": "true",
        }
    )


def test_readiness_fails_closed_when_database_boot_is_unavailable(monkeypatch) -> None:
    class UnavailableDatabase:
        def __init__(self, _dsn: str) -> None:
            raise RuntimeError("database unavailable")

    monkeypatch.setattr(runtime_api, "PostgresFiscalDatabase", UnavailableDatabase)
    client = TestClient(runtime_api.create_runtime_app(_postgres_settings()))

    assert client.get("/health/live").status_code == 200
    response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json() == {"status": "not_ready", "reason": "database_unavailable"}


def test_development_runtime_is_live_and_ready_without_production_claim() -> None:
    settings = RuntimeSettings.from_mapping({})
    client = TestClient(runtime_api.create_runtime_app(settings))

    assert client.get("/health/live").json()["status"] == "live"
    assert client.get("/health/ready").status_code == 200
    profile = client.get("/runtime/profile").json()
    assert profile["environment"] == "development"
    assert profile["fiscal_production_activated"] is False
