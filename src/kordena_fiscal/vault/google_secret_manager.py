"""Read-only GSM infrastructure adapter over canonical reference-only bindings.

No automatic identity discovery, tenant URLs, payload cache or fallback. Explicit
platform identity and allowlisted resources are required by the composition root.
"""

from __future__ import annotations

import base64
import json
import math
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

import google_crc32c
from google.api_core import exceptions
from google.auth.credentials import Credentials
from google.auth.external_account import Credentials as FederatedCredentials
from google.cloud import secretmanager_v1
from google.oauth2.service_account import Credentials as ServiceAccountCredentials

from kordena_fiscal.control_plane import SecretReference as FiscalReference
from kordena_fiscal.control_plane import SecretReferenceKind
from kordena_fiscal.persistence.ports import FiscalUnitOfWorkFactory
from kordena_fiscal.security.secret_binding import SecretBinding
from kordena_fiscal.security.secrets import (
    SecretBackendUnavailable,
    SecretReference,
    SecretResolutionError,
    SecretScope,
    StoredSecret,
)

from .contracts import SecretResolutionContext
from .external import (
    ExternalSecretBackendUnavailable,
    ExternalSecretPermissionDenied,
    ExternalSecretRecord,
)

MAX_ENVELOPE_BYTES = 65536
GSM_ENDPOINT = "secretmanager.googleapis.com"


@dataclass(frozen=True, slots=True, repr=False)
class GsmPayload:
    name: str
    data: bytes
    crc32c: int

    def __repr__(self) -> str:
        return "<GsmPayload redacted>"


class GsmAccess(Protocol):
    def access(self, name: str) -> GsmPayload: ...


class GoogleSdkSecretAccess:
    """Single pinned AccessSecretVersion call; SDK errors never escape with material."""

    def __init__(
        self,
        client: secretmanager_v1.SecretManagerServiceClient,
        *,
        timeout_seconds: float = 10.0,
        bootstrap_not_after: datetime | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if not math.isfinite(timeout_seconds) or not 0 < timeout_seconds <= 30:
            raise SecretResolutionError("invalid GSM timeout")
        self._client = client
        self._timeout = timeout_seconds
        self._bootstrap_expiry = bootstrap_not_after
        self._clock = clock or (lambda: datetime.now(UTC))

    def access(self, name: str) -> GsmPayload:
        if self._bootstrap_expiry is not None and self._bootstrap_expiry <= self._clock():
            raise SecretResolutionError("GSM bootstrap expired")
        try:
            result = self._client.access_secret_version(
                request={"name": name},
                retry=None,
                timeout=self._timeout,
            )
            if not secretmanager_v1.SecretPayload.pb(result.payload).HasField("data_crc32c"):
                raise ValueError
            return GsmPayload(
                result.name, bytes(result.payload.data), int(result.payload.data_crc32c)
            )
        except exceptions.PermissionDenied:
            raise ExternalSecretPermissionDenied("GSM access denied") from None
        except exceptions.NotFound:
            raise SecretResolutionError("GSM version is unavailable") from None
        except Exception:
            raise ExternalSecretBackendUnavailable("GSM backend unavailable") from None


def build_google_sdk_access(
    *,
    credentials: Credentials,
    environment: str,
    bootstrap_not_after: datetime | None = None,
    now: datetime | None = None,
) -> GoogleSdkSecretAccess:
    """Explicit WIF or approved staging-only service-account bootstrap; never ADC.

    Creating this reader does not grant IAM or certify cloud identity/audit/recovery.
    Actual credentials must be supplied through the separately approved runtime channel.
    """
    current = now or datetime.now(UTC)
    if environment not in {"staging", "production"} or current.utcoffset() is None:
        raise SecretResolutionError("invalid GSM identity environment")
    if isinstance(credentials, ServiceAccountCredentials):
        if (
            environment != "staging"
            or bootstrap_not_after is None
            or bootstrap_not_after.utcoffset() is None
            or not current < bootstrap_not_after <= current + timedelta(days=30)
        ):
            raise SecretResolutionError("staging bootstrap requires bounded rotation expiry")
    elif not isinstance(credentials, FederatedCredentials):
        raise SecretResolutionError("explicit federated workload identity required")
    try:
        client = secretmanager_v1.SecretManagerServiceClient(
            credentials=credentials,
            client_options={"api_endpoint": GSM_ENDPOINT, "universe_domain": "googleapis.com"},
        )
    except Exception:
        raise SecretBackendUnavailable("GSM identity bootstrap unavailable") from None
    return GoogleSdkSecretAccess(client, bootstrap_not_after=bootstrap_not_after)


def _no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError
        result[key] = value
    return result


def encode_gsm_envelope(
    binding: SecretBinding, material: bytes, *, password: bytes | None = None
) -> bytes:
    """Provisioning format only; performs no cloud write and returns ephemeral bytes."""
    if not isinstance(material, bytes) or not material:
        raise SecretResolutionError("secret material must be nonempty bytes")
    if password is not None and (binding.kind != "certificate" or not isinstance(password, bytes)):
        raise SecretResolutionError("invalid certificate password metadata")
    envelope = {
        "schema": 1,
        "binding": binding.metadata(),
        "material": base64.b64encode(material).decode("ascii"),
        "password": base64.b64encode(password).decode("ascii") if password is not None else None,
    }
    result = json.dumps(envelope, sort_keys=True, separators=(",", ":")).encode()
    if len(result) > MAX_ENVELOPE_BYTES:
        raise SecretResolutionError("GSM envelope exceeds payload limit")
    return result


class DurableGsmReader:
    """Validate durable metadata/context before provider I/O and again after it."""

    def __init__(
        self,
        *,
        uow_factory: FiscalUnitOfWorkFactory,
        access: GsmAccess,
        environment: str,
        workload_id: str,
        allowed_resources: frozenset[str],
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if environment not in {"test", "development", "staging", "production"}:
            raise SecretResolutionError("invalid GSM runtime environment")
        if not workload_id or not allowed_resources:
            raise SecretResolutionError("GSM workload/resource allowlist required")
        self._uow = uow_factory
        self._access = access
        self.environment = environment
        self._workload = workload_id
        self._resources = frozenset(allowed_resources)
        self._clock = clock or (lambda: datetime.now(UTC))

    def _binding(self, reference_id: str) -> SecretBinding:
        try:
            with self._uow() as uow:
                binding = uow.secret_bindings.get(reference_id)
        except Exception:
            raise SecretBackendUnavailable("secret binding storage unavailable") from None
        if binding is None:
            raise SecretResolutionError("secret binding unavailable")
        now = self._clock()
        if now.utcoffset() is None:
            raise SecretResolutionError("secret clock must be timezone-aware")
        if (
            binding.state != "active"
            or binding.runtime_environment != self.environment
            or binding.workload_id != self._workload
            or binding.resource not in self._resources
            or (binding.not_after is not None and binding.not_after <= now)
        ):
            raise SecretResolutionError("secret binding unavailable for this runtime")
        return binding

    def read(
        self,
        *,
        reference_id: str,
        scope: SecretScope,
        kind: str,
        provider_id: str | None,
        fiscal_environment: str | None,
        version: str | int | None = None,
    ) -> tuple[SecretBinding, bytes, bytes | None]:
        binding = self._binding(reference_id)
        if (
            binding.tenant_id != scope.tenant_id
            or binding.unit_id != scope.unit_id
            or binding.purpose != scope.purpose
            or binding.kind != kind
            or binding.provider_id != provider_id
            or binding.fiscal_environment != fiscal_environment
            or (
                version is not None
                and (
                    type(version) is not type(binding.canonical_version)
                    or version != binding.canonical_version
                )
            )
        ):
            raise SecretResolutionError("secret binding scope mismatch")
        try:
            payload = self._access.access(binding.version_name)
        except ExternalSecretPermissionDenied:
            raise
        except Exception:
            raise SecretBackendUnavailable("GSM version unavailable") from None
        try:
            if (
                payload.name != binding.version_name
                or type(payload.data) is not bytes
                or not 0 < len(payload.data) <= MAX_ENVELOPE_BYTES
                or type(payload.crc32c) is not int
                or google_crc32c.value(payload.data) != payload.crc32c
            ):
                raise ValueError
            envelope = json.loads(payload.data, object_pairs_hook=_no_duplicates)
            if (
                set(envelope) != {"schema", "binding", "material", "password"}
                or type(envelope["schema"]) is not int
                or envelope["schema"] != 1
                or envelope["binding"] != binding.metadata()
            ):
                raise ValueError
            # Dict equality alone treats True == 1. Reconstruct typed metadata as well.
            if SecretBinding.from_metadata(envelope["binding"]) != binding:
                raise ValueError
            value = base64.b64decode(envelope["material"], validate=True)
            password = (
                base64.b64decode(envelope["password"], validate=True)
                if envelope["password"] is not None
                else None
            )
            if not value or (password is not None and kind != "certificate"):
                raise ValueError
            if self._binding(reference_id) != binding:
                raise ValueError
        except Exception:
            raise SecretResolutionError("GSM secret payload invalid or binding changed") from None
        return binding, value, password


class GoogleFiscalSecretClient:
    def __init__(self, reader: DurableGsmReader) -> None:
        self._reader = reader

    def fetch(self, reference_id: str) -> ExternalSecretRecord | None:
        del reference_id
        raise ExternalSecretPermissionDenied("GSM fiscal access requires explicit context")

    def fetch_scoped(
        self, reference: FiscalReference, context: SecretResolutionContext
    ) -> ExternalSecretRecord:
        if context.workload_id != self._reader._workload:
            raise ExternalSecretPermissionDenied("GSM workload mismatch")
        try:
            binding, value, password = self._reader.read(
                reference_id=reference.reference_id,
                scope=SecretScope(
                    context.scope.tenant_id, context.scope.unit_id, context.purpose.value
                ),
                kind=context.kind.value,
                provider_id=context.provider_id,
                fiscal_environment=context.scope.environment.value,
            )
        except ExternalSecretPermissionDenied:
            raise
        except SecretBackendUnavailable:
            raise ExternalSecretBackendUnavailable("GSM backend unavailable") from None
        except SecretResolutionError:
            raise ExternalSecretPermissionDenied("GSM fiscal binding unavailable") from None
        assert isinstance(binding.canonical_version, str)
        return ExternalSecretRecord(
            reference.reference_id,
            SecretReferenceKind(binding.kind),
            value,
            password,
            binding.canonical_version,
            binding.not_after,
        )


class GoogleSignatureSecretBackend:
    def __init__(self, reader: DurableGsmReader, *, provider_id: str) -> None:
        self._reader = reader
        self._provider = provider_id

    @property
    def production_safe(self) -> bool:
        return True  # External adapter capability, not external certification.

    def resolve(self, reference: SecretReference) -> StoredSecret:
        del reference
        raise SecretResolutionError("GSM signature access requires explicit scope")

    def resolve_for_scope(self, reference: SecretReference, scope: SecretScope) -> StoredSecret:
        try:
            binding, value, _ = self._reader.read(
                reference_id=reference.reference_id,
                scope=scope,
                kind="signature",
                provider_id=self._provider,
                fiscal_environment=None,
                version=reference.version,
            )
        except ExternalSecretPermissionDenied:
            raise SecretResolutionError("GSM signature access denied") from None
        assert isinstance(binding.canonical_version, int)
        return StoredSecret(
            SecretReference(binding.reference_id, binding.canonical_version),
            scope,
            value,
            not_after=binding.not_after,
        )
