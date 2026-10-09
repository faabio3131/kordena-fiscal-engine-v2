"""Provider-agnostic production adapter for external secret managers.

The NFCORE domain keeps only opaque ``SecretReference`` values. Cloud/provider-specific
clients implement ``ExternalSecretClient`` and return short-lived records to this adapter;
raw material is immediately converted to the existing ephemeral secret types and is never
persisted, cached or serialized by the Core.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol, runtime_checkable

from kordena_fiscal.control_plane import SecretReference, SecretReferenceKind
from kordena_fiscal.domain import FiscalValidationError

from .contracts import (
    EphemeralCertificateMaterial,
    EphemeralCscMaterial,
    EphemeralProviderCredentialsMaterial,
    EphemeralSecretMaterial,
    SecretAuthorizationError,
    SecretMaterialTypeError,
    SecretResolutionContext,
    SecretUnavailableError,
)


class ExternalSecretBackendError(RuntimeError):
    """Base error emitted by a cloud/Vault client without secret material."""


class ExternalSecretBackendUnavailable(ExternalSecretBackendError):
    """External secret service is unavailable or timed out."""


class ExternalSecretPermissionDenied(ExternalSecretBackendError):
    """The workload identity is not authorized to read the reference."""


@dataclass(frozen=True, slots=True, repr=False, eq=False)
class ExternalSecretRecord:
    """One short-lived result returned by an external secret manager client."""

    reference_id: str
    kind: SecretReferenceKind
    material: bytes
    password: bytes | None = None
    version_id: str | None = None
    expires_at: datetime | None = None

    def __post_init__(self) -> None:
        reference_id = self.reference_id.strip().lower()
        if not reference_id.startswith("ref:"):
            raise FiscalValidationError("external secret record requires opaque ref: identifier")
        object.__setattr__(self, "reference_id", reference_id)
        if not isinstance(self.kind, SecretReferenceKind):
            raise FiscalValidationError("external secret record kind is invalid")
        if not isinstance(self.material, bytes) or not self.material:
            raise FiscalValidationError("external secret record material must be non-empty bytes")
        if self.password is not None and not isinstance(self.password, bytes):
            raise FiscalValidationError("external secret record password must be bytes or None")
        if self.version_id is not None:
            version = self.version_id.strip()
            if not version or len(version) > 256:
                raise FiscalValidationError("external secret version_id is invalid")
            object.__setattr__(self, "version_id", version)
        if self.expires_at is not None:
            if self.expires_at.tzinfo is None or self.expires_at.utcoffset() is None:
                raise FiscalValidationError("external secret expires_at must be timezone-aware")

    def __repr__(self) -> str:
        return "<ExternalSecretRecord redacted>"


class ExternalSecretClient(Protocol):
    """Cloud-specific driver boundary (AWS/Azure/GCP/Vault/etc.)."""

    def fetch(self, reference_id: str) -> ExternalSecretRecord | None: ...


@runtime_checkable
class ScopedExternalSecretClient(Protocol):
    def fetch_scoped(self, reference: SecretReference,
                     context: SecretResolutionContext) -> ExternalSecretRecord | None: ...


@dataclass(frozen=True, slots=True)
class SecretAccessAuditEvent:
    """Metadata-only runtime audit event; it cannot carry secret material."""

    reference_id: str
    kind: SecretReferenceKind
    tenant_id: str
    unit_id: str
    environment: str
    workload_id: str
    provider_id: str | None
    outcome: str
    version_id: str | None = None


class SecretAccessAuditSink(Protocol):
    def record(self, event: SecretAccessAuditEvent) -> None: ...


class NullSecretAccessAuditSink:
    def record(self, event: SecretAccessAuditEvent) -> None:
        del event


class ExternalSecretClock(Protocol):
    def now(self) -> datetime: ...


class SystemExternalSecretClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


class ExternalFiscalSecretVault:
    """Resolve external material while preserving NFCORE scope and type invariants.

    No in-process cache is used intentionally: provider-side rotation behind a stable
    reference becomes visible on the next resolution and stale material is not retained.
    """

    def __init__(
        self,
        *,
        client: ExternalSecretClient,
        audit: SecretAccessAuditSink,
        clock: ExternalSecretClock | None = None,
    ) -> None:
        self._client = client
        self._audit = audit
        self._clock = clock or SystemExternalSecretClock()

    def resolve(
        self,
        reference: SecretReference,
        context: SecretResolutionContext,
    ) -> EphemeralSecretMaterial:
        self._validate_scope(reference, context)
        try:
            record = (self._client.fetch_scoped(reference, context)
                      if isinstance(self._client, ScopedExternalSecretClient)
                      else self._client.fetch(reference.reference_id))
        except ExternalSecretPermissionDenied:
            self._record(reference, context, outcome="permission_denied")
            raise SecretAuthorizationError("external secret access denied") from None
        except ExternalSecretBackendUnavailable:
            self._record(reference, context, outcome="backend_unavailable")
            raise SecretUnavailableError("external secret backend is unavailable") from None

        if record is None:
            self._record(reference, context, outcome="missing")
            raise SecretUnavailableError("external secret material is unavailable")
        if record.reference_id != reference.reference_id or record.kind is not reference.kind:
            self._record(reference, context, outcome="type_mismatch")
            raise SecretMaterialTypeError("external secret material does not match reference")

        now = self._clock.now()
        if now.tzinfo is None or now.utcoffset() is None:
            raise FiscalValidationError("external secret clock must be timezone-aware")
        if record.expires_at is not None and record.expires_at <= now:
            self._record(
                reference,
                context,
                outcome="expired",
                version_id=record.version_id,
            )
            raise SecretUnavailableError("external secret material is expired")

        material = self._material(record)
        self._record(
            reference,
            context,
            outcome="resolved",
            version_id=record.version_id,
        )
        return material

    @staticmethod
    def _material(record: ExternalSecretRecord) -> EphemeralSecretMaterial:
        if record.kind is SecretReferenceKind.CERTIFICATE:
            return EphemeralCertificateMaterial(
                reference_id=record.reference_id,
                pkcs12_bytes=record.material,
                password=record.password,
            )
        if record.password is not None:
            raise SecretMaterialTypeError(
                "password metadata is valid only for certificate material"
            )
        if record.kind is SecretReferenceKind.CSC:
            return EphemeralCscMaterial(
                reference_id=record.reference_id,
                code=record.material,
            )
        if record.kind is SecretReferenceKind.CREDENTIALS:
            return EphemeralProviderCredentialsMaterial(
                reference_id=record.reference_id,
                credential_bytes=record.material,
            )
        raise SecretMaterialTypeError("unsupported external secret kind")

    @staticmethod
    def _validate_scope(reference: SecretReference, context: SecretResolutionContext) -> None:
        scope = context.scope
        if reference.tenant_id != scope.tenant_id:
            raise SecretAuthorizationError("secret reference tenant mismatch")
        if reference.unit_id != scope.unit_id:
            raise SecretAuthorizationError("secret reference unit mismatch")
        if reference.environment is not scope.environment:
            raise SecretAuthorizationError("secret reference environment mismatch")
        if reference.kind is not context.kind:
            raise SecretAuthorizationError("secret reference kind mismatch")
        if reference.provider_id != context.provider_id:
            raise SecretAuthorizationError("secret reference provider mismatch")

    def _record(
        self,
        reference: SecretReference,
        context: SecretResolutionContext,
        *,
        outcome: str,
        version_id: str | None = None,
    ) -> None:
        event = SecretAccessAuditEvent(
            reference_id=reference.reference_id,
            kind=reference.kind,
            tenant_id=reference.tenant_id,
            unit_id=reference.unit_id,
            environment=reference.environment.value,
            workload_id=context.workload_id,
            provider_id=reference.provider_id,
            outcome=outcome,
            version_id=version_id,
        )
        try:
            self._audit.record(event)
        except Exception:
            # Runtime audit exporters are observability sinks, never secret authority.
            return
