"""Synthetic runtime Vault adapter used only for contract certification."""

from __future__ import annotations

from dataclasses import dataclass, field

from kordena_fiscal.control_plane import SecretReference, SecretReferenceKind
from kordena_fiscal.domain import FiscalValidationError

from .contracts import (
    EphemeralSecretMaterial,
    SecretAuthorizationError,
    SecretMaterialTypeError,
    SecretResolutionContext,
    SecretUnavailableError,
)


@dataclass(slots=True)
class InMemorySyntheticFiscalSecretVault:
    """Non-production adapter with no persistence, filesystem or environment access."""

    available: bool = True
    _materials: dict[tuple[str, str, str | None], EphemeralSecretMaterial] = field(
        default_factory=dict,
        init=False,
        repr=False,
    )

    def register(
        self,
        *,
        host_namespace: str,
        reference: SecretReference,
        material: EphemeralSecretMaterial,
        provider_id: str | None = None,
    ) -> None:
        host = host_namespace.strip().lower()
        if not host:
            raise FiscalValidationError("host_namespace must not be blank")
        if material.reference_id != reference.reference_id:
            raise SecretMaterialTypeError("material reference_id does not match reference")
        if material.kind is not reference.kind:
            raise SecretMaterialTypeError("material kind does not match reference")

        provider: str | None = None
        if provider_id is not None:
            provider = provider_id.strip().lower()
            if not provider:
                raise FiscalValidationError("provider_id must not be blank")
            if len(provider) > 128:
                raise FiscalValidationError("provider_id exceeds max length 128")
        if reference.kind in {SecretReferenceKind.CREDENTIALS, SecretReferenceKind.CSC}:
            if provider is None:
                raise FiscalValidationError(
                    "provider_id is required for provider-scoped secret material"
                )
        elif provider is not None:
            raise FiscalValidationError(
                "provider_id is only valid for provider credentials or CSC material"
            )

        self._materials[(host, reference.reference_id, provider)] = material

    def resolve(
        self,
        reference: SecretReference,
        context: SecretResolutionContext,
    ) -> EphemeralSecretMaterial:
        if not self.available:
            raise SecretUnavailableError("secret vault is unavailable")
        scope = context.scope
        host = scope.host_namespace
        if host is None:
            raise SecretAuthorizationError("secret resolution requires host_namespace")
        if reference.tenant_id != scope.tenant_id:
            raise SecretAuthorizationError("secret reference tenant mismatch")
        if reference.unit_id != scope.unit_id:
            raise SecretAuthorizationError("secret reference unit mismatch")
        if reference.environment is not scope.environment:
            raise SecretAuthorizationError("secret reference environment mismatch")
        if reference.kind is not context.kind:
            raise SecretAuthorizationError("secret reference kind mismatch")
        try:
            material = self._materials[
                (host, reference.reference_id, context.provider_id)
            ]
        except KeyError as exc:
            raise SecretUnavailableError(
                "secret material is unavailable for requested host/reference/provider"
            ) from exc
        if material.kind is not reference.kind:
            raise SecretMaterialTypeError("vault material kind does not match reference")
        return material
