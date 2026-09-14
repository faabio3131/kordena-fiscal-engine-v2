"""Reference-only external configuration for the standalone FM Fiscal platform."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from urllib.parse import urlparse

from .tenant_configuration import (
    ExternalDependencyState,
    ExternalReference,
    TenantConfigurationError,
)


@dataclass(frozen=True, slots=True)
class PlatformExternalConfiguration:
    """External platform bindings that must not be hardcoded into FM Fiscal source."""

    configuration_id: str
    version: int
    deployment_profile_id: str
    public_base_url: str
    cloud_account: ExternalReference
    dns_control: ExternalReference
    secret_backend: ExternalReference
    commercial_gateway_account: ExternalReference
    production_activation: ExternalReference

    def __post_init__(self) -> None:
        for field_name in ("configuration_id", "deployment_profile_id"):
            value = getattr(self, field_name).strip()
            if not value or len(value) > 160:
                raise TenantConfigurationError(f"{field_name} must be non-blank and <= 160 chars")
            object.__setattr__(self, field_name, value)
        if self.version < 1:
            raise TenantConfigurationError("version must be >= 1")
        parsed = urlparse(self.public_base_url.strip())
        if parsed.scheme != "https" or not parsed.netloc:
            raise TenantConfigurationError("public_base_url must be an absolute HTTPS URL")
        object.__setattr__(self, "public_base_url", self.public_base_url.strip().rstrip("/"))

    @property
    def production_ready(self) -> bool:
        dependencies = (
            self.cloud_account,
            self.dns_control,
            self.secret_backend,
            self.commercial_gateway_account,
            self.production_activation,
        )
        return all(item.state is ExternalDependencyState.VERIFIED for item in dependencies)

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> PlatformExternalConfiguration:
        return cls(
            configuration_id=_string(payload.get("configuration_id"), "configuration_id"),
            version=_integer(payload.get("version"), "version"),
            deployment_profile_id=_string(
                payload.get("deployment_profile_id"),
                "deployment_profile_id",
            ),
            public_base_url=_string(payload.get("public_base_url"), "public_base_url"),
            cloud_account=_reference(payload.get("cloud_account"), "cloud_account"),
            dns_control=_reference(payload.get("dns_control"), "dns_control"),
            secret_backend=_reference(payload.get("secret_backend"), "secret_backend"),
            commercial_gateway_account=_reference(
                payload.get("commercial_gateway_account"),
                "commercial_gateway_account",
            ),
            production_activation=_reference(
                payload.get("production_activation"),
                "production_activation",
            ),
        )


def _reference(value: object, field_name: str) -> ExternalReference:
    if not isinstance(value, Mapping):
        raise TenantConfigurationError(f"{field_name} must be a mapping")
    state_value = value.get("state")
    if not isinstance(state_value, str):
        raise TenantConfigurationError(f"{field_name}.state must be string")
    reference_id = value.get("reference_id")
    evidence_reference = value.get("evidence_reference")
    if reference_id is not None and not isinstance(reference_id, str):
        raise TenantConfigurationError(f"{field_name}.reference_id must be string")
    if evidence_reference is not None and not isinstance(evidence_reference, str):
        raise TenantConfigurationError(f"{field_name}.evidence_reference must be string")
    return ExternalReference(
        reference_id=reference_id,
        state=ExternalDependencyState(state_value),
        evidence_reference=evidence_reference,
    )


def _string(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise TenantConfigurationError(f"{field_name} must be string")
    return value


def _integer(value: object, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TenantConfigurationError(f"{field_name} must be integer")
    return value
