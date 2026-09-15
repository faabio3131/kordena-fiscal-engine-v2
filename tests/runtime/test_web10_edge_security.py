from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from kordena_fiscal.runtime import api as runtime_api
from kordena_fiscal.runtime.config import RuntimeConfigurationError, RuntimeSettings


def test_runtime_emits_defensive_security_headers() -> None:
    client = TestClient(runtime_api.create_runtime_app(RuntimeSettings.from_mapping({})))

    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert "default-src 'none'" in response.headers["content-security-policy"]
    assert "strict-transport-security" not in response.headers


def test_runtime_rejects_untrusted_host_header() -> None:
    client = TestClient(runtime_api.create_runtime_app(RuntimeSettings.from_mapping({})))

    response = client.get("/health/live", headers={"Host": "attacker.example"})

    assert response.status_code == 400
    assert response.headers["x-content-type-options"] == "nosniff"


def test_runtime_rejects_forwarded_authority_from_untrusted_peer() -> None:
    client = TestClient(runtime_api.create_runtime_app(RuntimeSettings.from_mapping({})))

    response = client.get("/health/live", headers={"X-Forwarded-Proto": "https"})

    assert response.status_code == 400
    assert response.json() == {"detail": "untrusted proxy forwarding headers"}


def test_explicit_cors_origin_is_echoed_without_wildcard() -> None:
    settings = RuntimeSettings.from_mapping(
        {
            "NFCORE_ALLOWED_ORIGINS": "https://portal.example.com",
        }
    )
    client = TestClient(runtime_api.create_runtime_app(settings))

    response = client.options(
        "/health/live",
        headers={
            "Origin": "https://portal.example.com",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://portal.example.com"
    assert response.headers["access-control-allow-credentials"] == "true"


def test_production_like_profile_emits_hsts(monkeypatch: pytest.MonkeyPatch) -> None:
    class UnavailableDatabase:
        def __init__(self, _dsn: str) -> None:
            raise RuntimeError("database unavailable")

    monkeypatch.setattr(runtime_api, "PostgresFiscalDatabase", UnavailableDatabase)
    settings = RuntimeSettings.from_mapping(
        {
            "NFCORE_ENVIRONMENT": "staging",
            "NFCORE_PERSISTENCE_BACKEND": "postgres",
            "DATABASE_URL": "postgresql://user:password@db:5432/nfcore",
            "NFCORE_SECRET_BACKEND": "external",
            "NFCORE_REQUIRE_HTTPS": "true",
            "NFCORE_PUBLIC_HOSTNAME": "api.example.com",
            "NFCORE_ALLOWED_ORIGINS": "https://portal.example.com",
        }
    )
    client = TestClient(runtime_api.create_runtime_app(settings))

    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.headers["strict-transport-security"].startswith("max-age=31536000")


def test_production_like_profile_rejects_wildcard_cors() -> None:
    with pytest.raises(RuntimeConfigurationError, match="CORS cannot allow wildcard"):
        RuntimeSettings.from_mapping(
            {
                "NFCORE_ENVIRONMENT": "staging",
                "NFCORE_PERSISTENCE_BACKEND": "postgres",
                "DATABASE_URL": "postgresql://user:password@db:5432/nfcore",
                "NFCORE_SECRET_BACKEND": "external",
                "NFCORE_REQUIRE_HTTPS": "true",
                "NFCORE_ALLOWED_ORIGINS": "*",
            }
        )


def test_production_requires_public_hostname_authority() -> None:
    with pytest.raises(RuntimeConfigurationError, match="NFCORE_PUBLIC_HOSTNAME"):
        RuntimeSettings.from_mapping(
            {
                "NFCORE_ENVIRONMENT": "production",
                "NFCORE_PERSISTENCE_BACKEND": "postgres",
                "DATABASE_URL": "postgresql://user:password@db:5432/nfcore",
                "NFCORE_SECRET_BACKEND": "external",
                "NFCORE_REQUIRE_HTTPS": "true",
            }
        )


def test_invalid_trusted_proxy_network_is_rejected() -> None:
    with pytest.raises(RuntimeConfigurationError, match="invalid network"):
        RuntimeSettings.from_mapping({"NFCORE_TRUSTED_PROXY_CIDRS": "not-a-network"})


def test_production_like_profile_rejects_global_proxy_trust() -> None:
    with pytest.raises(RuntimeConfigurationError, match="cannot trust all addresses"):
        RuntimeSettings.from_mapping(
            {
                "NFCORE_ENVIRONMENT": "staging",
                "NFCORE_PERSISTENCE_BACKEND": "postgres",
                "DATABASE_URL": "postgresql://user:password@db:5432/nfcore",
                "NFCORE_SECRET_BACKEND": "external",
                "NFCORE_TRUSTED_PROXY_CIDRS": "0.0.0.0/0",
            }
        )
