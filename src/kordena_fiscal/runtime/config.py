"""Deployment/runtime configuration profiles for FM NFCORE."""

from __future__ import annotations

import ipaddress
import os
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from urllib.parse import urlparse

_HOSTNAME = re.compile(
    r"^(?=.{1,253}$)(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)*"
    r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$"
)
_INTERNAL_TRUSTED_HOSTS = ("localhost", "127.0.0.1", "testserver")
_PROVIDER_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")


class RuntimeConfigurationError(RuntimeError):
    """Raised when an environment profile would start insecurely."""


class RuntimeEnvironment(StrEnum):
    DEVELOPMENT = "development"
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"


def _csv_tokens(value: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(item.strip() for item in value.split(",") if item.strip()))


def _validate_origin(origin: str, *, production_like: bool) -> None:
    if origin == "*":
        if production_like:
            raise RuntimeConfigurationError("staging/production CORS cannot allow wildcard origin")
        return
    parsed = urlparse(origin)
    try:
        _ = parsed.port
    except ValueError as exc:
        raise RuntimeConfigurationError("CORS origins contain an invalid port") from exc
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise RuntimeConfigurationError("CORS origins must be absolute HTTP(S) origins")
    if parsed.path or parsed.query or parsed.fragment or parsed.username or parsed.password:
        raise RuntimeConfigurationError("CORS origins must not contain path, query or credentials")
    if production_like and parsed.scheme != "https":
        raise RuntimeConfigurationError("staging/production CORS origins must use HTTPS")


@dataclass(frozen=True, slots=True)
class RuntimeSettings:
    environment: RuntimeEnvironment
    persistence_backend: str
    database_url: str | None
    secret_backend: str
    require_https: bool
    port: int
    public_hostname: str | None = None
    allowed_origins: tuple[str, ...] = ()
    trusted_hosts: tuple[str, ...] = _INTERNAL_TRUSTED_HOSTS
    trusted_proxy_cidrs: tuple[str, ...] = ()
    commercial_checkout_provider: str | None = None

    @classmethod
    def from_mapping(cls, values: Mapping[str, str]) -> RuntimeSettings:
        environment_raw = values.get("NFCORE_ENVIRONMENT", "development").strip().lower()
        try:
            environment = RuntimeEnvironment(environment_raw)
        except ValueError as exc:
            raise RuntimeConfigurationError("NFCORE_ENVIRONMENT is invalid") from exc

        is_local = environment in {
            RuntimeEnvironment.DEVELOPMENT,
            RuntimeEnvironment.TEST,
        }
        persistence = values.get(
            "NFCORE_PERSISTENCE_BACKEND",
            "sqlite" if is_local else "postgres",
        ).strip().lower()
        database_url = values.get("DATABASE_URL", "").strip() or None
        secret_backend = values.get(
            "NFCORE_SECRET_BACKEND",
            "memory" if is_local else "external",
        ).strip().lower()
        https_raw = values.get(
            "NFCORE_REQUIRE_HTTPS",
            "false" if is_local else "true",
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

        public_hostname = values.get("NFCORE_PUBLIC_HOSTNAME", "").strip().lower() or None
        allowed_origins = _csv_tokens(values.get("NFCORE_ALLOWED_ORIGINS", ""))
        if public_hostname and not allowed_origins:
            allowed_origins = (f"https://{public_hostname}",)
        configured_hosts = _csv_tokens(values.get("NFCORE_TRUSTED_HOSTS", ""))
        public_hosts = (public_hostname,) if public_hostname else ()
        trusted_hosts = tuple(
            dict.fromkeys((*_INTERNAL_TRUSTED_HOSTS, *configured_hosts, *public_hosts))
        )
        trusted_proxy_cidrs = _csv_tokens(values.get("NFCORE_TRUSTED_PROXY_CIDRS", ""))
        commercial_checkout_provider = (
            values.get("NFCORE_COMMERCIAL_CHECKOUT_PROVIDER", "").strip().lower() or None
        )

        settings = cls(
            environment=environment,
            persistence_backend=persistence,
            database_url=database_url,
            secret_backend=secret_backend,
            require_https=https_raw == "true",
            port=port,
            public_hostname=public_hostname,
            allowed_origins=allowed_origins,
            trusted_hosts=trusted_hosts,
            trusted_proxy_cidrs=trusted_proxy_cidrs,
            commercial_checkout_provider=commercial_checkout_provider,
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
            valid_dsn = self.database_url and self.database_url.startswith(
                ("postgresql://", "postgres://")
            )
            if not valid_dsn:
                raise RuntimeConfigurationError("DATABASE_URL PostgreSQL DSN is required")
        elif self.persistence_backend != "sqlite":
            raise RuntimeConfigurationError("unsupported persistence backend")
        if production_like and self.secret_backend in {"memory", "environment", "dev", "test"}:
            raise RuntimeConfigurationError(
                "staging/production requires an external secret backend"
            )
        if production_like and self.secret_backend != "external":
            raise RuntimeConfigurationError("unsupported production secret backend profile")
        if self.environment is RuntimeEnvironment.PRODUCTION and not self.require_https:
            raise RuntimeConfigurationError("production requires HTTPS policy")
        if self.environment is RuntimeEnvironment.PRODUCTION and self.public_hostname is None:
            raise RuntimeConfigurationError("production requires NFCORE_PUBLIC_HOSTNAME")

        if self.public_hostname is not None:
            if not _HOSTNAME.fullmatch(self.public_hostname) or ":" in self.public_hostname:
                raise RuntimeConfigurationError("NFCORE_PUBLIC_HOSTNAME must be a DNS hostname")
        if production_like and "*" in self.trusted_hosts:
            raise RuntimeConfigurationError(
                "staging/production trusted hosts cannot contain wildcard"
            )
        for host in self.trusted_hosts:
            if host != "*" and not _HOSTNAME.fullmatch(host):
                raise RuntimeConfigurationError("NFCORE_TRUSTED_HOSTS contains an invalid hostname")
        for origin in self.allowed_origins:
            _validate_origin(origin, production_like=production_like)
        if (
            self.commercial_checkout_provider is not None
            and not _PROVIDER_ID.fullmatch(self.commercial_checkout_provider)
        ):
            raise RuntimeConfigurationError(
                "NFCORE_COMMERCIAL_CHECKOUT_PROVIDER is invalid"
            )
        for cidr in self.trusted_proxy_cidrs:
            try:
                network = ipaddress.ip_network(cidr, strict=False)
            except ValueError as exc:
                raise RuntimeConfigurationError(
                    "NFCORE_TRUSTED_PROXY_CIDRS contains an invalid network"
                ) from exc
            if production_like and network.prefixlen == 0:
                raise RuntimeConfigurationError(
                    "staging/production trusted proxy networks cannot trust all addresses"
                )

    @property
    def is_production_like(self) -> bool:
        return self.environment in {RuntimeEnvironment.STAGING, RuntimeEnvironment.PRODUCTION}
