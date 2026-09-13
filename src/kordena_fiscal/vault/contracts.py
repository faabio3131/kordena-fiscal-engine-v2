"""Provider-neutral secret resolution boundary for V2-12.

Secret references remain durable Control Plane metadata. Secret material returned by
this module is deliberately ephemeral and has no persistence or serialization port.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from kordena_fiscal.control_plane import SecretReference, SecretReferenceKind
from kordena_fiscal.domain import ExecutionScope, FiscalDomainError, FiscalValidationError
from kordena_fiscal.persistence.ports import FiscalUnitOfWorkFactory


class SecretResolutionError(FiscalDomainError):
    """Base error for fail-closed secret resolution."""


class SecretAuthorizationError(SecretResolutionError):
    """Requested secret scope is not administratively valid."""


class SecretUnavailableError(SecretResolutionError):
    """Secret reference or runtime material is unavailable."""


class SecretMaterialTypeError(SecretResolutionError):
    """Resolved material does not match the governed secret kind."""


class SecretUsagePurpose(StrEnum):
    DOCUMENT_SIGNING = "document-signing"
    CSC_AUTHENTICATION = "csc-authentication"
    PROVIDER_AUTHENTICATION = "provider-authentication"


_PURPOSE_KIND: dict[SecretUsagePurpose, SecretReferenceKind] = {
    SecretUsagePurpose.DOCUMENT_SIGNING: SecretReferenceKind.CERTIFICATE,
    SecretUsagePurpose.CSC_AUTHENTICATION: SecretReferenceKind.CSC,
    SecretUsagePurpose.PROVIDER_AUTHENTICATION: SecretReferenceKind.CREDENTIALS,
}
_PROVIDER_SCOPED_PURPOSES = frozenset(
    {
        SecretUsagePurpose.CSC_AUTHENTICATION,
        SecretUsagePurpose.PROVIDER_AUTHENTICATION,
    }
)


def _required_text(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise FiscalValidationError(f"{field_name} must not be blank")
    if len(normalized) > 128:
        raise FiscalValidationError(f"{field_name} exceeds max length 128")
    return normalized


@dataclass(frozen=True, slots=True)
class SecretResolutionContext:
    """Explicit workload, fiscal scope and optional provider partition for one secret."""

    scope: ExecutionScope
    purpose: SecretUsagePurpose
    kind: SecretReferenceKind
    workload_id: str
    provider_id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.scope, ExecutionScope):
            raise FiscalValidationError("scope must be ExecutionScope")
        if self.scope.host_namespace is None:
            raise FiscalValidationError("secret resolution requires host_namespace")
        if not isinstance(self.purpose, SecretUsagePurpose):
            raise FiscalValidationError("purpose must be SecretUsagePurpose")
        if not isinstance(self.kind, SecretReferenceKind):
            raise FiscalValidationError("kind must be SecretReferenceKind")
        if _PURPOSE_KIND[self.purpose] is not self.kind:
            raise FiscalValidationError("secret kind is incompatible with usage purpose")
        object.__setattr__(self, "workload_id", _required_text(self.workload_id, "workload_id"))

        if self.provider_id is not None:
            object.__setattr__(
                self,
                "provider_id",
                _required_text(self.provider_id, "provider_id").lower(),
            )
        if self.purpose in _PROVIDER_SCOPED_PURPOSES and self.provider_id is None:
            raise FiscalValidationError(
                "provider_id is required for provider-scoped secret resolution"
            )


@dataclass(frozen=True, slots=True, repr=False, eq=False)
class EphemeralCertificateMaterial:
    """PKCS#12 certificate material that must exist only in process memory."""

    reference_id: str
    pkcs12_bytes: bytes
    password: bytes | None = None

    @property
    def kind(self) -> SecretReferenceKind:
        return SecretReferenceKind.CERTIFICATE

    def __repr__(self) -> str:
        return "<EphemeralCertificateMaterial redacted>"


@dataclass(frozen=True, slots=True, repr=False, eq=False)
class EphemeralCscMaterial:
    """CSC material kept out of durable state and diagnostic representations."""

    reference_id: str
    code: bytes

    @property
    def kind(self) -> SecretReferenceKind:
        return SecretReferenceKind.CSC

    def __repr__(self) -> str:
        return "<EphemeralCscMaterial redacted>"


@dataclass(frozen=True, slots=True, repr=False, eq=False)
class EphemeralProviderCredentialsMaterial:
    """Opaque provider credential bytes, never a persisted configuration object."""

    reference_id: str
    credential_bytes: bytes

    @property
    def kind(self) -> SecretReferenceKind:
        return SecretReferenceKind.CREDENTIALS

    def __repr__(self) -> str:
        return "<EphemeralProviderCredentialsMaterial redacted>"


EphemeralSecretMaterial = (
    EphemeralCertificateMaterial
    | EphemeralCscMaterial
    | EphemeralProviderCredentialsMaterial
)


class FiscalSecretVault(Protocol):
    """Runtime-only resolver implemented by a production Vault/KMS adapter later."""

    def resolve(
        self,
        reference: SecretReference,
        context: SecretResolutionContext,
    ) -> EphemeralSecretMaterial: ...


class SecretResolutionService:
    """Resolve an opaque Control Plane reference through a runtime Vault port."""

    def __init__(
        self,
        *,
        unit_of_work_factory: FiscalUnitOfWorkFactory,
        vault: FiscalSecretVault,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._vault = vault

    def resolve(self, context: SecretResolutionContext) -> EphemeralSecretMaterial:
        if not isinstance(context, SecretResolutionContext):
            raise FiscalValidationError("context must be SecretResolutionContext")

        scope = context.scope
        with self._unit_of_work_factory() as uow:
            organization = uow.control_plane.get_organization(scope.tenant_id)
            if organization is None:
                raise SecretUnavailableError(
                    "secret reference is not bound for requested scope"
                )
            unit = uow.control_plane.get_unit(scope.tenant_id, scope.unit_id)
            if unit is None:
                raise SecretUnavailableError(
                    "secret reference is not bound for requested scope"
                )
            if scope.environment not in unit.enabled_environments:
                raise SecretAuthorizationError("secret environment is not enabled")
            reference = uow.control_plane.get_secret_reference(
                scope.tenant_id,
                scope.unit_id,
                scope.environment,
                context.kind,
            )

        if reference is None:
            raise SecretUnavailableError("secret reference is not bound for requested scope")
        self._validate_reference(reference, context)
        material = self._vault.resolve(reference, context)
        if material.reference_id != reference.reference_id or material.kind is not reference.kind:
            raise SecretMaterialTypeError("vault returned material inconsistent with reference")
        return material

    @staticmethod
    def _validate_reference(
        reference: SecretReference,
        context: SecretResolutionContext,
    ) -> None:
        scope = context.scope
        if reference.tenant_id != scope.tenant_id:
            raise SecretAuthorizationError("secret reference tenant mismatch")
        if reference.unit_id != scope.unit_id:
            raise SecretAuthorizationError("secret reference unit mismatch")
        if reference.environment is not scope.environment:
            raise SecretAuthorizationError("secret reference environment mismatch")
        if reference.kind is not context.kind:
            raise SecretAuthorizationError("secret reference kind mismatch")
