from __future__ import annotations

import pytest

from kordena_fiscal.runtime.config import (
    RuntimeConfigurationError,
    RuntimeEnvironment,
    RuntimeSettings,
)


def test_development_defaults_are_explicitly_non_production() -> None:
    settings = RuntimeSettings.from_mapping({})
    assert settings.environment is RuntimeEnvironment.DEVELOPMENT
    assert settings.persistence_backend == "sqlite"
    assert settings.secret_backend == "memory"
    assert settings.require_https is False
    assert settings.is_production_like is False


def test_staging_requires_postgres_external_secrets_and_valid_database_url() -> None:
    settings = RuntimeSettings.from_mapping(
        {
            "NFCORE_ENVIRONMENT": "staging",
            "NFCORE_PERSISTENCE_BACKEND": "postgres",
            "DATABASE_URL": "postgresql://user:password@db:5432/nfcore",
            "NFCORE_SECRET_BACKEND": "external",
            "NFCORE_REQUIRE_HTTPS": "true",
        }
    )
    assert settings.environment is RuntimeEnvironment.STAGING
    assert settings.is_production_like is True


@pytest.mark.parametrize("backend", ["sqlite", "memory-store", "unknown"])
def test_production_rejects_non_postgres_persistence(backend: str) -> None:
    with pytest.raises(RuntimeConfigurationError, match="persistence must be postgres"):
        RuntimeSettings.from_mapping(
            {
                "NFCORE_ENVIRONMENT": "production",
                "NFCORE_PERSISTENCE_BACKEND": backend,
                "DATABASE_URL": "postgresql://user:password@db:5432/nfcore",
                "NFCORE_SECRET_BACKEND": "external",
                "NFCORE_REQUIRE_HTTPS": "true",
            }
        )


@pytest.mark.parametrize("secret_backend", ["memory", "environment", "dev", "test"])
def test_production_rejects_insecure_secret_profiles(secret_backend: str) -> None:
    with pytest.raises(RuntimeConfigurationError, match="external secret backend"):
        RuntimeSettings.from_mapping(
            {
                "NFCORE_ENVIRONMENT": "production",
                "NFCORE_PERSISTENCE_BACKEND": "postgres",
                "DATABASE_URL": "postgresql://user:password@db:5432/nfcore",
                "NFCORE_SECRET_BACKEND": secret_backend,
                "NFCORE_REQUIRE_HTTPS": "true",
            }
        )


def test_production_requires_https_policy() -> None:
    with pytest.raises(RuntimeConfigurationError, match="requires HTTPS"):
        RuntimeSettings.from_mapping(
            {
                "NFCORE_ENVIRONMENT": "production",
                "NFCORE_PERSISTENCE_BACKEND": "postgres",
                "DATABASE_URL": "postgresql://user:password@db:5432/nfcore",
                "NFCORE_SECRET_BACKEND": "external",
                "NFCORE_REQUIRE_HTTPS": "false",
            }
        )


def test_postgres_profile_requires_real_dsn_shape() -> None:
    with pytest.raises(RuntimeConfigurationError, match="PostgreSQL DSN"):
        RuntimeSettings.from_mapping(
            {
                "NFCORE_ENVIRONMENT": "staging",
                "NFCORE_PERSISTENCE_BACKEND": "postgres",
                "DATABASE_URL": "sqlite:///nfcore.db",
                "NFCORE_SECRET_BACKEND": "external",
            }
        )
