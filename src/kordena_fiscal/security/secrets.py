"""Vendor-neutral secret resolution boundary for FM NFCORE.

Only opaque references and metadata belong in normal application state. Secret bytes are
resolved at the last responsible moment and wrapped in a redacted, zeroizable buffer.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from threading import RLock
from typing import Protocol, runtime_checkable

_SECRET_REF = re.compile(r"^sec_[A-Za-z0-9_-]{16,160}$")
_SAFE_PURPOSE = re.compile(r"^[a-z][a-z0-9_.-]{1,63}$")


class SecretResolutionError(RuntimeError):
    """Fail-closed secret resolution error that never carries secret material."""


class SecretBackendUnavailable(SecretResolutionError):
    """Raised when an external secret backend cannot be reached."""


class SecretState(StrEnum):
    ACTIVE = "active"
    REVOKED = "revoked"


@dataclass(frozen=True, slots=True)
class SecretScope:
    tenant_id: str
    unit_id: str | None
    purpose: str

    def __post_init__(self) -> None:
        tenant = self.tenant_id.strip()
        unit = self.unit_id.strip() if self.unit_id is not None else None
        purpose = self.purpose.strip().lower()
        if not tenant or len(tenant) > 160:
            raise SecretResolutionError("invalid secret tenant scope")
        if unit is not None and (not unit or len(unit) > 160):
            raise SecretResolutionError("invalid secret unit scope")
        if not _SAFE_PURPOSE.fullmatch(purpose):
            raise SecretResolutionError("invalid secret purpose")
        object.__setattr__(self, "tenant_id", tenant)
        object.__setattr__(self, "unit_id", unit)
        object.__setattr__(self, "purpose", purpose)


@dataclass(frozen=True, slots=True)
class SecretReference:
    reference_id: str
    version: int | None = None

    def __post_init__(self) -> None:
        reference = self.reference_id.strip()
        if not _SECRET_REF.fullmatch(reference):
            raise SecretResolutionError("invalid opaque secret reference")
        if self.version is not None and (
            not isinstance(self.version, int)
            or isinstance(self.version, bool)
            or self.version < 1
        ):
            raise SecretResolutionError("secret version must be a positive integer")
        object.__setattr__(self, "reference_id", reference)

    def __repr__(self) -> str:
        return f"SecretReference(reference_id={self.reference_id!r}, version={self.version!r})"


@dataclass(frozen=True, slots=True, repr=False)
class StoredSecret:
    reference: SecretReference
    scope: SecretScope
    value: bytes
    state: SecretState = SecretState.ACTIVE
    not_after: datetime | None = None

    def __post_init__(self) -> None:
        if not self.value:
            raise SecretResolutionError("secret material must not be empty")
        if self.not_after is not None and self.not_after.tzinfo is None:
            raise SecretResolutionError("secret expiry must be timezone-aware")

    def __repr__(self) -> str:
        return (
            "StoredSecret("
            f"reference={self.reference!r}, scope={self.scope!r}, value=<redacted>, "
            f"state={self.state.value!r}, not_after={self.not_after!r})"
        )


class SecretMaterial:
    """Short-lived secret buffer with safe repr and best-effort zeroization."""

    __slots__ = ("_buffer", "_closed")

    def __init__(self, value: bytes) -> None:
        self._buffer = bytearray(value)
        self._closed = False

    def reveal(self) -> bytes:
        if self._closed:
            raise SecretResolutionError("secret material is no longer available")
        return bytes(self._buffer)

    def close(self) -> None:
        if not self._closed:
            for index in range(len(self._buffer)):
                self._buffer[index] = 0
            self._closed = True

    def __enter__(self) -> SecretMaterial:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def __repr__(self) -> str:
        return "SecretMaterial(<redacted>)"


@runtime_checkable
class SecretBackend(Protocol):
    @property
    def production_safe(self) -> bool: ...

    def resolve(self, reference: SecretReference) -> StoredSecret: ...


@dataclass(frozen=True, slots=True)
class SecretAuditEvent:
    reference_id: str
    version: int | None
    tenant_id: str
    unit_id: str | None
    purpose: str
    outcome: str
    occurred_at: datetime


SecretAuditSink = Callable[[SecretAuditEvent], None]


class InMemorySecretBackend:
    """Development/test backend. Production use is rejected by SecretResolver."""

    def __init__(self) -> None:
        self._records: dict[tuple[str, int], StoredSecret] = {}
        self._latest: dict[str, int] = {}
        self._lock = RLock()

    @property
    def production_safe(self) -> bool:
        return False

    def put(
        self,
        *,
        reference_id: str,
        scope: SecretScope,
        value: bytes,
        not_after: datetime | None = None,
    ) -> SecretReference:
        base = SecretReference(reference_id)
        with self._lock:
            version = self._latest.get(base.reference_id, 0) + 1
            reference = SecretReference(base.reference_id, version)
            self._records[(base.reference_id, version)] = StoredSecret(
                reference=reference,
                scope=scope,
                value=bytes(value),
                not_after=not_after,
            )
            self._latest[base.reference_id] = version
            return reference

    def revoke(self, reference: SecretReference) -> None:
        with self._lock:
            record = self.resolve(reference)
            version = record.reference.version
            assert version is not None
            self._records[(record.reference.reference_id, version)] = StoredSecret(
                reference=record.reference,
                scope=record.scope,
                value=record.value,
                state=SecretState.REVOKED,
                not_after=record.not_after,
            )

    def resolve(self, reference: SecretReference) -> StoredSecret:
        with self._lock:
            version = reference.version or self._latest.get(reference.reference_id)
            if version is None:
                raise SecretResolutionError("secret reference was not found")
            record = self._records.get((reference.reference_id, version))
            if record is None:
                raise SecretResolutionError("secret reference was not found")
            return record


class CallableProductionSecretBackend:
    """Production-safe adapter boundary for a later selected cloud/vault provider.

    The injected resolver is responsible for authenticated provider access. This class
    intentionally selects no cloud vendor and stores no provider credential.
    """

    def __init__(self, resolver: Callable[[SecretReference], StoredSecret]) -> None:
        self._resolver = resolver

    @property
    def production_safe(self) -> bool:
        return True

    def resolve(self, reference: SecretReference) -> StoredSecret:
        try:
            return self._resolver(reference)
        except SecretResolutionError:
            raise
        except Exception as exc:
            raise SecretBackendUnavailable("secret backend is unavailable") from exc


class SecretResolver:
    def __init__(
        self,
        backend: SecretBackend,
        *,
        environment: str,
        audit_sink: SecretAuditSink | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        normalized = environment.strip().lower()
        if normalized not in {"development", "test", "staging", "production"}:
            raise SecretResolutionError("invalid runtime environment")
        if normalized in {"staging", "production"} and not backend.production_safe:
            raise SecretResolutionError("secure external secret backend is required")
        self._backend = backend
        self._environment = normalized
        self._audit = audit_sink or (lambda _event: None)
        self._clock = clock or (lambda: datetime.now(UTC))

    @property
    def environment(self) -> str:
        return self._environment

    def resolve(self, reference: SecretReference, *, scope: SecretScope) -> SecretMaterial:
        now = self._clock()
        outcome = "denied"
        try:
            stored = self._backend.resolve(reference)
            if stored.scope != scope:
                raise SecretResolutionError("secret access is not authorized for this scope")
            if stored.state is SecretState.REVOKED:
                raise SecretResolutionError("secret is revoked")
            if stored.not_after is not None and stored.not_after <= now:
                raise SecretResolutionError("secret is expired")
            outcome = "resolved"
            return SecretMaterial(stored.value)
        finally:
            self._audit(
                SecretAuditEvent(
                    reference_id=reference.reference_id,
                    version=reference.version,
                    tenant_id=scope.tenant_id,
                    unit_id=scope.unit_id,
                    purpose=scope.purpose,
                    outcome=outcome,
                    occurred_at=now,
                )
            )
