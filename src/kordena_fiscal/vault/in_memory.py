"""Synthetic runtime Vault adapter used only for contract certification."""

from __future__ import annotations

from dataclasses import dataclass, field

from kordena_fiscal.control_plane import SecretReference
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
    _materials: dict[tuple[str, str], EphemeralSecretMaterial] = field(
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
    ) -> None:
        host = host_namespace.strip().lower()
        if not host:
            raise FiscalValidationError("host_namespace must not be blank")
        if material.reference_id != reference.reference_id:
            raise SecretMaterialTypeError("material reference_id does not match reference")
        if material.kind is not reference.kind:
            raise SecretMaterialTypeError("material kind does not match reference")
        self._materials[(host, reference.reference_id)] = material

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
            material = self._materials[(host, reference.reference_id)]
        except KeyError as exc:
            raise SecretUnavailableError(
                "secret material is unavailable for requested host/reference"
            ) from exc
        if material.kind is not reference.kind:
            raise SecretMaterialTypeError("vault material kind does not match reference")
        return material
