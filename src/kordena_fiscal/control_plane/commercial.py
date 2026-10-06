"""Commercial configuration contracts for zero-code customer onboarding.

This module contains only governed, host-neutral configuration data. It must not
contain customer-specific branching. New tenants are represented by persisted
configuration records that survive process restarts.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any, Protocol
from uuid import uuid4

from kordena_fiscal.domain import (
    BrazilianJurisdiction,
    ExecutionScope,
    FiscalDocumentKind,
    FiscalEnvironment,
    FiscalProductProfile,
    FiscalValidationError,
)
from kordena_fiscal.persistence.ports import (
    FiscalUnitOfWorkFactory,
    PersistenceConflictError,
)
from kordena_fiscal.security.human_identity import AuthenticatedHuman, PortalPermission

from .models import (
    AdminPrincipal,
    ControlPlaneAuditAction,
    ControlPlaneAuditEvent,
    ControlPlanePermission,
    SecretReference,
    SecretReferenceKind,
)
from .service import (
    ControlPlaneAuthorizationError,
    ControlPlaneConflictError,
    ControlPlaneNotFoundError,
)


def _required(value: str, field_name: str, max_length: int = 256) -> str:
    normalized = value.strip()
    if not normalized:
        raise FiscalValidationError(f"{field_name} must not be blank")
    if len(normalized) > max_length:
        raise FiscalValidationError(f"{field_name} exceeds max length {max_length}")
    return normalized


def _token(value: str, field_name: str) -> str:
    normalized = _required(value, field_name, 128).lower()
    allowed = set("abcdefghijklmnopqrstuvwxyz0123456789._-")
    if normalized[0] not in allowed or normalized[-1] not in allowed:
        raise FiscalValidationError(f"{field_name} has invalid token format")
    if any(character not in allowed for character in normalized):
        raise FiscalValidationError(f"{field_name} has invalid token format")
    return normalized


class ConfiguredFiscalOperation(StrEnum):
    """Provider-facing fiscal capabilities configurable per customer scope."""

    AUTHORIZE = "authorize"
    QUERY = "query"
    CANCEL = "cancel"
    INUTILIZE = "inutilize"
    STATUS = "status"


ProviderBindingKey = tuple[
    str,
    str,
    FiscalEnvironment,
    FiscalDocumentKind,
    str,
    str,
    ConfiguredFiscalOperation,
]


@dataclass(frozen=True, slots=True)
class ProviderBinding:
    """Exact tenant/unit/document/jurisdiction operation -> provider binding."""

    binding_id: str
    tenant_id: str
    unit_id: str
    environment: FiscalEnvironment
    document_kind: FiscalDocumentKind
    jurisdiction: BrazilianJurisdiction
    operation: ConfiguredFiscalOperation
    provider_id: str
    enabled: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "binding_id", _token(self.binding_id, "binding_id"))
        object.__setattr__(self, "tenant_id", _token(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "unit_id", _token(self.unit_id, "unit_id"))
        object.__setattr__(self, "provider_id", _token(self.provider_id, "provider_id"))
        if not isinstance(self.environment, FiscalEnvironment):
            raise FiscalValidationError("environment must be FiscalEnvironment")
        if not isinstance(self.document_kind, FiscalDocumentKind):
            raise FiscalValidationError("document_kind must be FiscalDocumentKind")
        if not isinstance(self.jurisdiction, BrazilianJurisdiction):
            raise FiscalValidationError("jurisdiction must be BrazilianJurisdiction")
        if not isinstance(self.operation, ConfiguredFiscalOperation):
            raise FiscalValidationError("operation must be ConfiguredFiscalOperation")
        if (
            self.document_kind is FiscalDocumentKind.NFSE
            and self.jurisdiction.municipality_ibge_code is None
        ):
            raise FiscalValidationError("NFSe provider binding requires municipality IBGE code")
        if not isinstance(self.enabled, bool):
            raise FiscalValidationError("enabled must be bool")

    @property
    def exact_key(self) -> ProviderBindingKey:
        return (
            self.tenant_id,
            self.unit_id,
            self.environment,
            self.document_kind,
            self.jurisdiction.state_code,
            self.jurisdiction.municipality_ibge_code or "",
            self.operation,
        )


@dataclass(frozen=True, slots=True)
class UnitModuleBinding:
    """Explicit module enablement for one customer unit/environment."""

    tenant_id: str
    unit_id: str
    environment: FiscalEnvironment
    module_id: str
    enabled: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "tenant_id", _token(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "unit_id", _token(self.unit_id, "unit_id"))
        object.__setattr__(self, "module_id", _token(self.module_id, "module_id"))
        if not isinstance(self.environment, FiscalEnvironment):
            raise FiscalValidationError("environment must be FiscalEnvironment")
        if not isinstance(self.enabled, bool):
            raise FiscalValidationError("enabled must be bool")


@dataclass(frozen=True, slots=True)
class WebhookDestinationConfig:
    """Durable non-secret webhook destination for one customer partition."""

    destination_id: str
    tenant_id: str
    unit_id: str
    environment: FiscalEnvironment
    url: str
    enabled: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "destination_id",
            _token(self.destination_id, "destination_id"),
        )
        object.__setattr__(self, "tenant_id", _token(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "unit_id", _token(self.unit_id, "unit_id"))
        if not isinstance(self.environment, FiscalEnvironment):
            raise FiscalValidationError("environment must be FiscalEnvironment")
        from .webhook_policy import normalize_webhook_url

        url, _hostname, _path = normalize_webhook_url(self.url)
        object.__setattr__(self, "url", url)
        if not isinstance(self.enabled, bool):
            raise FiscalValidationError("enabled must be bool")


@dataclass(frozen=True, slots=True)
class ProviderRuntimePolicyConfig:
    """Durable provider runtime policy instead of composition-time numeric literals."""

    policy_id: str
    tenant_id: str
    unit_id: str
    environment: FiscalEnvironment
    provider_id: str
    connect_timeout_seconds: float
    read_timeout_seconds: float
    max_attempts: int
    base_delay_seconds: float
    max_delay_seconds: float
    jitter_ratio: float
    circuit_failure_threshold: int
    circuit_recovery_seconds: float
    circuit_success_threshold: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(self, "policy_id", _token(self.policy_id, "policy_id"))
        object.__setattr__(self, "tenant_id", _token(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "unit_id", _token(self.unit_id, "unit_id"))
        object.__setattr__(self, "provider_id", _token(self.provider_id, "provider_id"))
        if not isinstance(self.environment, FiscalEnvironment):
            raise FiscalValidationError("environment must be FiscalEnvironment")
        for field_name in (
            "connect_timeout_seconds",
            "read_timeout_seconds",
            "base_delay_seconds",
            "max_delay_seconds",
            "jitter_ratio",
            "circuit_recovery_seconds",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise FiscalValidationError(f"{field_name} must be numeric")
            object.__setattr__(self, field_name, float(value))
        if not 0 < self.connect_timeout_seconds <= 300:
            raise FiscalValidationError("connect_timeout_seconds must be > 0 and <= 300")
        if not 0 < self.read_timeout_seconds <= 300:
            raise FiscalValidationError("read_timeout_seconds must be > 0 and <= 300")
        if not isinstance(self.max_attempts, int) or isinstance(self.max_attempts, bool):
            raise FiscalValidationError("max_attempts must be integer")
        if not 1 <= self.max_attempts <= 20:
            raise FiscalValidationError("max_attempts must be between 1 and 20")
        if self.base_delay_seconds < 0 or self.max_delay_seconds < self.base_delay_seconds:
            raise FiscalValidationError("retry delay bounds are invalid")
        if not 0 <= self.jitter_ratio <= 1:
            raise FiscalValidationError("jitter_ratio must be between 0 and 1")
        for field_name in ("circuit_failure_threshold", "circuit_success_threshold"):
            value = getattr(self, field_name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                raise FiscalValidationError(f"{field_name} must be integer >= 1")
        if self.circuit_recovery_seconds <= 0:
            raise FiscalValidationError("circuit_recovery_seconds must be > 0")


class ProviderBindingResolver(Protocol):
    def resolve_provider_id(
        self,
        *,
        scope: ExecutionScope,
        document_kind: FiscalDocumentKind,
        jurisdiction: BrazilianJurisdiction,
        operation: str,
    ) -> str: ...


class DurableProviderBindingResolver:
    """Resolve provider choice from durable customer configuration only."""

    def __init__(self, unit_of_work_factory: FiscalUnitOfWorkFactory) -> None:
        self._unit_of_work_factory = unit_of_work_factory

    def resolve_provider_id(
        self,
        *,
        scope: ExecutionScope,
        document_kind: FiscalDocumentKind,
        jurisdiction: BrazilianJurisdiction,
        operation: str,
    ) -> str:
        if scope.host_namespace is None:
            raise FiscalValidationError("provider binding resolution requires host_namespace")
        try:
            configured_operation = ConfiguredFiscalOperation(operation)
        except ValueError as exc:
            raise FiscalValidationError("unsupported configured provider operation") from exc
        with self._unit_of_work_factory() as uow:
            binding = uow.commercial.resolve_provider_binding(
                tenant_id=scope.tenant_id,
                unit_id=scope.unit_id,
                environment=scope.environment,
                document_kind=document_kind,
                jurisdiction=jurisdiction,
                operation=configured_operation,
            )
        if binding is None or not binding.enabled:
            raise ControlPlaneNotFoundError(
                "no enabled provider binding exists for exact fiscal capability"
            )
        return binding.provider_id


class CommercialConfigurationService:
    """Governed zero-code customer configuration writes and reads."""

    def __init__(self, unit_of_work_factory: FiscalUnitOfWorkFactory) -> None:
        self._unit_of_work_factory = unit_of_work_factory

    def set_provider_binding(
        self,
        *,
        actor: AdminPrincipal,
        binding: ProviderBinding,
    ) -> ProviderBinding:
        self._require_scope(actor, binding.tenant_id)
        self._require_unit_environment(
            binding.tenant_id,
            binding.unit_id,
            binding.environment,
        )
        with self._unit_of_work_factory() as uow:
            try:
                result = uow.commercial.put_provider_binding(binding)
            except PersistenceConflictError as exc:
                raise ControlPlaneConflictError(str(exc)) from exc
            uow.commit()
            return result

    def add_product_profile(
        self,
        *,
        actor: AdminPrincipal,
        profile: FiscalProductProfile,
    ) -> FiscalProductProfile:
        if not isinstance(profile, FiscalProductProfile):
            raise FiscalValidationError("profile must be FiscalProductProfile")
        self._require_scope(actor, profile.scope.tenant_id)
        self._require_unit_environment(
            profile.scope.tenant_id,
            profile.scope.unit_id,
            profile.scope.environment,
        )
        with self._unit_of_work_factory() as uow:
            try:
                result = uow.commercial.add_product_profile(profile)
            except PersistenceConflictError as exc:
                raise ControlPlaneConflictError(str(exc)) from exc
            uow.commit()
            return result

    def set_module_binding(
        self,
        *,
        actor: AdminPrincipal,
        binding: UnitModuleBinding,
    ) -> UnitModuleBinding:
        self._require_scope(actor, binding.tenant_id)
        self._require_unit_environment(
            binding.tenant_id,
            binding.unit_id,
            binding.environment,
        )
        with self._unit_of_work_factory() as uow:
            result = uow.commercial.put_module_binding(binding)
            uow.commit()
            return result

    def set_webhook_destination(
        self,
        *,
        actor: AdminPrincipal,
        destination: WebhookDestinationConfig,
    ) -> WebhookDestinationConfig:
        self._require_scope(actor, destination.tenant_id)
        self._require_unit_environment(
            destination.tenant_id,
            destination.unit_id,
            destination.environment,
        )
        with self._unit_of_work_factory() as uow:
            result = uow.commercial.put_webhook_destination(destination)
            uow.commit()
            return result

    def set_runtime_policy(
        self,
        *,
        actor: AdminPrincipal,
        policy: ProviderRuntimePolicyConfig,
    ) -> ProviderRuntimePolicyConfig:
        self._require_scope(actor, policy.tenant_id)
        self._require_unit_environment(
            policy.tenant_id,
            policy.unit_id,
            policy.environment,
        )
        with self._unit_of_work_factory() as uow:
            result = uow.commercial.put_runtime_policy(policy)
            uow.commit()
            return result

    def configure_customer(
        self,
        *,
        authority: AuthenticatedHuman,
        scope: ExecutionScope,
        surface_id: str,
        values: Mapping[str, Any],
        expected_version: int,
        idempotency_key: str,
        decision: str | None = None,
    ) -> Mapping[str, object]:
        from .webhook_policy import normalize_webhook_url

        if not isinstance(authority, AuthenticatedHuman):
            raise ControlPlaneAuthorizationError("human session is required")
        if decision is not None:
            if surface_id != "webhooks" or not authority.account.platform_admin:
                raise ControlPlaneAuthorizationError("platform admin is required")
            if decision not in {"approved", "revoked"}:
                raise FiscalValidationError("invalid egress decision")
        else:
            if authority.tenant_id != scope.tenant_id:
                raise ControlPlaneAuthorizationError("tenant scope mismatch")
            permission = (
                PortalPermission.CERTIFICATE_MANAGE
                if surface_id == "certificates"
                else PortalPermission.CONFIGURATION_WRITE
                if surface_id == "settings"
                else PortalPermission.INTEGRATION_MANAGE
            )
            authority.assert_permission(permission, unit_id=scope.unit_id)
        if surface_id not in {"certificates", "providers", "webhooks", "integrations", "settings"}:
            raise FiscalValidationError("unknown customer configuration")
        if (
            isinstance(expected_version, bool)
            or not isinstance(expected_version, int)
            or expected_version < 0
        ):
            raise FiscalValidationError("expected_version must be a nonnegative integer")
        key = _required(idempotency_key, "idempotency key", 256)
        actor = hashlib.sha256(authority.account.account_id.encode()).hexdigest()
        fingerprint = hashlib.sha256(
            json.dumps(
                {
                    "surface": surface_id,
                    "values": dict(values),
                    "expected": expected_version,
                    "actor": actor,
                    "decision": decision,
                },
                sort_keys=True,
                allow_nan=False,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        command_key = hashlib.sha256(key.encode()).hexdigest()
        allowed: dict[str, set[str]] = {
            "certificates": {"reference_id", "kind", "provider_id"},
            "providers": {
                "binding_id",
                "document_kind",
                "state_code",
                "municipality_ibge_code",
                "operation",
                "provider_id",
                "enabled",
            },
            "webhooks": {"destination_id", "url", "enabled"}
            if decision is None
            else {"destination_id", "url", "expires_at"},
            "integrations": {"module_id", "enabled"},
            "settings": {
                "policy_id",
                "provider_id",
                "connect_timeout_seconds",
                "read_timeout_seconds",
                "max_attempts",
                "base_delay_seconds",
                "max_delay_seconds",
                "jitter_ratio",
                "circuit_failure_threshold",
                "circuit_recovery_seconds",
                "circuit_success_threshold",
            },
        }
        if set(values) - allowed[surface_id]:
            raise FiscalValidationError("unsupported configuration field")
        target_key = str(
            values.get(
                {
                    "certificates": "kind",
                    "providers": "binding_id",
                    "webhooks": "destination_id",
                    "integrations": "module_id",
                    "settings": "provider_id",
                }[surface_id],
                "",
            )
        )
        target_key = _token(target_key, "configuration key")
        if surface_id == "certificates":
            target_key += ":" + (
                _token(str(values["provider_id"]), "provider_id")
                if values.get("provider_id")
                else ""
            )
        now = datetime.now(UTC)
        with self._unit_of_work_factory() as uow:
            unit = uow.control_plane.get_unit(scope.tenant_id, scope.unit_id)
            if unit is None or scope.environment not in unit.enabled_environments:
                raise ControlPlaneAuthorizationError("unit/environment is not configured")
            replay = uow.commercial.reserve_configuration_command(scope, command_key, fingerprint)
            if replay is not None:
                return replay
            version = uow.commercial.advance_configuration_version(
                scope, surface_id, target_key, expected_version
            )
            partition: dict[str, Any] = dict(
                tenant_id=scope.tenant_id, unit_id=scope.unit_id, environment=scope.environment
            )
            if surface_id == "certificates":
                reference = SecretReference(
                    **partition,
                    reference_id=str(values.get("reference_id", "")),
                    kind=SecretReferenceKind(str(values.get("kind", ""))),
                    provider_id=values.get("provider_id"),
                )
                uow.control_plane.put_secret_reference(reference)
            elif surface_id == "providers":
                binding = ProviderBinding(
                    **partition,
                    binding_id=str(values.get("binding_id", "")),
                    document_kind=FiscalDocumentKind(str(values.get("document_kind", ""))),
                    jurisdiction=BrazilianJurisdiction(
                        str(values.get("state_code", "")),
                        values.get("municipality_ibge_code") or None,
                    ),
                    operation=ConfiguredFiscalOperation(str(values.get("operation", ""))),
                    provider_id=str(values.get("provider_id", "")),
                    enabled=values.get("enabled", False),
                )
                current = uow.commercial.resolve_provider_binding(
                    tenant_id=scope.tenant_id,
                    unit_id=scope.unit_id,
                    environment=scope.environment,
                    document_kind=binding.document_kind,
                    jurisdiction=binding.jurisdiction,
                    operation=binding.operation,
                )
                if current is not None and current.binding_id != binding.binding_id:
                    raise ControlPlaneConflictError("provider binding identity conflict")
                uow.commercial.put_provider_binding(binding)
            elif surface_id == "integrations":
                uow.commercial.put_module_binding(
                    UnitModuleBinding(
                        **partition,
                        module_id=str(values.get("module_id", "")),
                        enabled=values.get("enabled", False),
                    )
                )
            elif surface_id == "settings":
                uow.commercial.put_runtime_policy(
                    ProviderRuntimePolicyConfig(**partition, **dict(values))
                )
            elif decision is None:
                url, _hostname, _path = normalize_webhook_url(str(values.get("url", "")))
                uow.commercial.put_webhook_destination(
                    WebhookDestinationConfig(
                        **partition,
                        destination_id=target_key,
                        url=url,
                        enabled=values.get("enabled", False),
                    )
                )
                uow.commercial.record_webhook_approval(
                    scope,
                    target_key,
                    status="pending",
                    version=None,
                    expires_at=None,
                    url_sha256=None,
                    requested_by=actor,
                )
            else:
                record = uow.commercial.webhook_approval(scope, target_key)
                if record is None:
                    raise ControlPlaneNotFoundError("webhook request is missing")
                if decision == "approved":
                    url, _hostname, _path = normalize_webhook_url(str(values.get("url", "")))
                    if record["url"] != url or record["requested_by"] in (actor, ""):
                        raise ControlPlaneAuthorizationError(
                            "exact destination and independent approval required"
                        )
                    expires = datetime.fromisoformat(str(values.get("expires_at", "")))
                    if expires.tzinfo is None or not now < expires <= now + timedelta(days=30):
                        raise FiscalValidationError("approval expiry must be within 30 days")
                    url_hash = hashlib.sha256(url.encode()).hexdigest()
                    expiry = expires.astimezone(UTC).isoformat()
                else:
                    url_hash = None
                    expiry = None
                uow.commercial.record_webhook_approval(
                    scope,
                    target_key,
                    status=decision,
                    version=version if decision == "approved" else None,
                    expires_at=expiry,
                    url_sha256=url_hash,
                    approved_by=actor,
                )
            action = (
                ControlPlaneAuditAction.WEBHOOK_EGRESS_DECIDED
                if decision is not None
                else ControlPlaneAuditAction.CUSTOMER_CONFIGURATION_CHANGED
            )
            uow.control_plane.append_audit(
                ControlPlaneAuditEvent(
                    event_id=uuid4().hex,
                    occurred_at=now,
                    actor_id="human-" + actor[:24],
                    action=action,
                    target_type=surface_id,
                    target_id=f"{target_key}:v{version}",
                    correlation_id=scope.correlation_id,
                    tenant_id=scope.tenant_id,
                    unit_id=scope.unit_id,
                )
            )
            result: dict[str, object] = {
                "status": "configuration_recorded",
                "target_key": target_key,
                "version": version,
                "unit_id": scope.unit_id,
                "environment": scope.environment.value,
                "operational_verification": "not_confirmed",
            }
            if surface_id == "webhooks":
                result["approval_status"] = decision or "pending"
            uow.commercial.complete_configuration_command(scope, command_key, result)
            uow.commit()
            return result

    def _require_unit_environment(
        self,
        tenant_id: str,
        unit_id: str,
        environment: FiscalEnvironment,
    ) -> None:
        with self._unit_of_work_factory() as uow:
            unit = uow.control_plane.get_unit(tenant_id, unit_id)
        if unit is None:
            raise ControlPlaneNotFoundError(f"unit is not onboarded: {tenant_id}/{unit_id}")
        if environment not in unit.enabled_environments:
            raise ControlPlaneAuthorizationError("environment is not enabled for the target unit")

    @staticmethod
    def _require_scope(actor: AdminPrincipal, tenant_id: str) -> None:
        if not isinstance(actor, AdminPrincipal):
            raise FiscalValidationError("actor must be AdminPrincipal")
        permission = ControlPlanePermission.COMMERCIAL_CONFIG_WRITE
        if not actor.has_permission(permission):
            raise ControlPlaneAuthorizationError(
                f"actor lacks required permission: {permission.value}"
            )
        if not actor.can_access_tenant(tenant_id):
            raise ControlPlaneAuthorizationError(f"actor cannot access tenant: {tenant_id}")
