"""Deployment/runtime configuration profiles for FM NFCORE."""

from __future__ import annotations

import os
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum


class RuntimeConfigurationError(RuntimeError):
    """Raised when an environment profile would start insecurely."""


class RuntimeEnvironment(StrEnum):
    DEVELOPMENT = "development"
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"


@dataclass(frozen=True, slots=True)
class RuntimeSettings:
    environment: RuntimeEnvironment
    persistence_backend: str
    database_url: str | None
    secret_backend: str
    require_https: bool
    port: int

    @classmethod
    def from_mapping(cls, values: Mapping[str, str]) -> RuntimeSettings:
        environment_raw = values.get("NFCORE_ENVIRONMENT", "development").strip().lower()
        try:
            environment = RuntimeEnvironment(environment_raw)
        except ValueError as exc:
            raise RuntimeConfigurationError("NFCORE_ENVIRONMENT is invalid") from exc

        persistence = values.get(
            "NFCORE_PERSISTENCE_BACKEND",
            "sqlite" if environment in {RuntimeEnvironment.DEVELOPMENT, RuntimeEnvironment.TEST} else "postgres",
        ).strip().lower()
        database_url = values.get("DATABASE_URL", "").strip() or None
        secret_backend = values.get(
            "NFCORE_SECRET_BACKEND",
            "memory" if environment in {RuntimeEnvironment.DEVELOPMENT, RuntimeEnvironment.TEST} else "external",
        ).strip().lower()
        https_raw = values.get(
            "NFCORE_REQUIRE_HTTPS",
            "false" if environment in {RuntimeEnvironment.DEVELOPMENT, RuntimeEnvironment.TEST} else "true",
        ).strip().lower()
        if https_raw not in {"true", "false"}:
            raise RuntimeConfigurationError("NFCORE_REQUIRE_HTTPS must be true or false")
        port_raw = values.get("PORT", "8080").strip()
        try:
            port = int(port_raw)
        except ValueError as exc:
            raise RuntimeConfigurationError("PORT must be an integer") from exc
        if port < 1 or port > 65535:
            raise RuntimeConfigurationError("PORT must be between 1 and 65535")

        settings = cls(
            environment=environment,
            persistence_backend=persistence,
            database_url=database_url,
            secret_backend=secret_backend,
            require_https=https_raw == "true",
            port=port,
        )
        settings.validate()
        return settings

    @classmethod
    def from_environ(cls, environ: Iterable[tuple[str, str]] | None = None) -> RuntimeSettings:
        return cls.from_mapping(dict(environ if environ is not None else os.environ.items()))

    def validate(self) -> None:
        production_like = self.environment in {
            RuntimeEnvironment.STAGING,
            RuntimeEnvironment.PRODUCTION,
        }
        if production_like and self.persistence_backend != "postgres":
            raise RuntimeConfigurationError("staging/production persistence must be postgres")
        if self.persistence_backend == "postgres":
            if not self.database_url or not self.database_url.startswith(("postgresql://", "postgres://")):
                raise RuntimeConfigurationError("DATABASE_URL PostgreSQL DSN is required")
        elif self.persistence_backend != "sqlite":
            raise RuntimeConfigurationError("unsupported persistence backend")
        if production_like and self.secret_backend in {"memory", "environment", "dev", "test"}:
            raise RuntimeConfigurationError("staging/production requires an external secret backend")
        if production_like and self.secret_backend != "external":
            raise RuntimeConfigurationError("unsupported production secret backend profile")
        if self.environment is RuntimeEnvironment.PRODUCTION and not self.require_https:
            raise RuntimeConfigurationError("production requires HTTPS policy")

    @property
    def is_production_like(self) -> bool:
        return self.environment in {RuntimeEnvironment.STAGING, RuntimeEnvironment.PRODUCTION}
