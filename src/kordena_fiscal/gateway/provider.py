"""Provider-neutral gateway routing and runtime secret integration for V2-12."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol

from kordena_fiscal.compliance import CapabilityReadinessService, FiscalActionCapability
from kordena_fiscal.control_plane import SecretReferenceKind
from kordena_fiscal.domain import (
    BrazilianJurisdiction,
    ExecutionScope,
    FiscalDocumentKind,
    FiscalDomainError,
    FiscalEnvironment,
    FiscalValidationError,
)
from kordena_fiscal.signing import FiscalSignatureResult
from kordena_fiscal.vault import (
    EphemeralCscMaterial,
    EphemeralProviderCredentialsMaterial,
    SecretResolutionContext,
    SecretResolutionError,
    SecretResolutionService,
    SecretUsagePurpose,
)


class ProviderGatewayError(FiscalDomainError):
    """Base error for provider/gateway boundary failures."""


class ProviderUnavailableError(ProviderGatewayError):
    """Configured provider or transport is unavailable."""


class UnsupportedProviderError(ProviderGatewayError):
    """No unambiguous provider supports the requested fiscal context."""


class UnsupportedJurisdictionError(ProviderGatewayError):
    """Provider does not support the requested jurisdiction."""


class ProviderCredentialsUnavailableError(ProviderGatewayError):
    """Provider credentials cannot be resolved for the requested scope."""


class CscUnavailableError(ProviderGatewayError):
    """NFC-e CSC cannot be resolved for the requested scope."""


class ProviderAuthenticationError(ProviderGatewayError):
    """Provider authentication failed without exposing credential material."""


class ProviderRejectedError(ProviderGatewayError):
    """Provider rejected a transport-level request before normalized processing."""


class MalformedProviderResponseError(ProviderGatewayError):
    """Provider transport returned an invalid normalized response."""


class ProviderTransportError(ProviderGatewayError):
    """Transport failed; ``delivery_unknown`` marks an ambiguous delivery outcome."""

    def __init__(self, message: str, *, delivery_unknown: bool = False) -> None:
        super().__init__(message)
        self.delivery_unknown = delivery_unknown


class ProviderOperation(StrEnum):
    AUTHORIZE = "authorize"
    QUERY = "query"
    CANCEL = "cancel"
    INUTILIZE = "inutilize"
    STATUS = "status"


class ProviderResponseStatus(StrEnum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    PENDING = "pending"
    FOUND = "found"
    CANCELLED = "cancelled"
    AVAILABLE = "available"


_OPERATION_ACTION: dict[ProviderOperation, FiscalActionCapability] = {
    ProviderOperation.AUTHORIZE: FiscalActionCapability.ISSUE,
    ProviderOperation.QUERY: FiscalActionCapability.QUERY,
    ProviderOperation.CANCEL: FiscalActionCapability.CANCEL,
    ProviderOperation.INUTILIZE: FiscalActionCapability.INUTILIZE,
    ProviderOperation.STATUS: FiscalActionCapability.QUERY,
}


def _required(value: str, field_name: str, max_length: int = 256) -> str:
    normalized = value.strip()
    if not normalized:
        raise FiscalValidationError(f"{field_name} must not be blank")
    if len(normalized) > max_length:
        raise FiscalValidationError(f"{field_name} exceeds max length {max_length}")
    return normalized


@dataclass(frozen=True, slots=True)
class ProviderDescriptor:
    """Explicit provider identity and supported fiscal surface."""

    provider_id: str
    document_kinds: frozenset[FiscalDocumentKind]
    jurisdictions: tuple[BrazilianJurisdiction, ...]
    environments: frozenset[FiscalEnvironment]
    operations: frozenset[ProviderOperation]
    csc_required_for: frozenset[tuple[FiscalDocumentKind, ProviderOperation]] = frozenset()

    def __post_init__(self) -> None:
        provider_id = _required(self.provider_id, "provider_id", 128).lower()
        object.__setattr__(self, "provider_id", provider_id)
        if not self.document_kinds or not all(
            isinstance(item, FiscalDocumentKind) for item in self.document_kinds
        ):
            raise FiscalValidationError("document_kinds must be a non-empty frozenset")
        if not self.jurisdictions or not all(
            isinstance(item, BrazilianJurisdiction) for item in self.jurisdictions
        ):
            raise FiscalValidationError("jurisdictions must contain BrazilianJurisdiction values")
        if not self.environments or not all(
            isinstance(item, FiscalEnvironment) for item in self.environments
        ):
            raise FiscalValidationError("environments must be a non-empty frozenset")
        if not self.operations or not all(
            isinstance(item, ProviderOperation) for item in self.operations
        ):
            raise FiscalValidationError("operations must be a non-empty frozenset")
        if not isinstance(self.csc_required_for, frozenset):
            raise FiscalValidationError("csc_required_for must be a frozenset")
        for document_kind, operation in self.csc_required_for:
            if document_kind not in self.document_kinds or operation not in self.operations:
                raise FiscalValidationError("CSC requirement must reference a supported capability")

    def supports(
        self,
        *,
        document_kind: FiscalDocumentKind,
        jurisdiction: BrazilianJurisdiction,
        environment: FiscalEnvironment,
        operation: ProviderOperation,
    ) -> bool:
        return (
            document_kind in self.document_kinds
            and jurisdiction in self.jurisdictions
            and environment in self.environments
            and operation in self.operations
        )

    def requires_csc(
        self,
        document_kind: FiscalDocumentKind,
        operation: ProviderOperation,
    ) -> bool:
        return (document_kind, operation) in self.csc_required_for


@dataclass(frozen=True, slots=True, repr=False)
class ProviderRequest:
    """Canonical provider request with no credential or CSC material."""

    scope: ExecutionScope
    document_kind: FiscalDocumentKind
    jurisdiction: BrazilianJurisdiction
    operation: ProviderOperation
    payload: bytes
    correlation_id: str
    workload_id: str
    signed_artifact: FiscalSignatureResult | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.scope, ExecutionScope) or self.scope.host_namespace is None:
            raise FiscalValidationError("provider request requires bound ExecutionScope")
        if not isinstance(self.document_kind, FiscalDocumentKind):
            raise FiscalValidationError("document_kind must be FiscalDocumentKind")
        if not isinstance(self.jurisdiction, BrazilianJurisdiction):
            raise FiscalValidationError("jurisdiction must be BrazilianJurisdiction")
        if not isinstance(self.operation, ProviderOperation):
            raise FiscalValidationError("operation must be ProviderOperation")
        if not isinstance(self.payload, bytes) or not self.payload:
            raise FiscalValidationError("payload must be non-empty bytes")
        object.__setattr__(
            self,
            "correlation_id",
            _required(self.correlation_id, "correlation_id"),
        )
        object.__setattr__(
            self,
            "workload_id",
            _required(self.workload_id, "workload_id", 128),
        )
        if self.operation is ProviderOperation.AUTHORIZE:
            if not isinstance(self.signed_artifact, FiscalSignatureResult):
                raise FiscalValidationError("authorize requires FiscalSignatureResult")
            if self.signed_artifact.document_kind is not self.document_kind:
                raise FiscalValidationError("signed artifact document kind mismatch")

    def __repr__(self) -> str:
        return (
            "<ProviderRequest "
            f"operation={self.operation.value} document_kind={self.document_kind.value} "
            f"tenant={self.scope.tenant_id} unit={self.scope.unit_id}>"
        )


@dataclass(frozen=True, slots=True)
class ProviderTransportResponse:
    """Sanitized provider transport response before Core normalization."""

    status: ProviderResponseStatus
    provider_request_id: str | None = None
    external_reference: str | None = None
    code: str | None = None
    message: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.status, ProviderResponseStatus):
            raise FiscalValidationError("status must be ProviderResponseStatus")
        for field_name in ("provider_request_id", "external_reference", "code", "message"):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, _required(value, field_name, 512))


@dataclass(frozen=True, slots=True)
class ProviderResponse:
    """Provider-neutral normalized gateway result."""

    provider_id: str
    operation: ProviderOperation
    status: ProviderResponseStatus
    correlation_id: str
    provider_request_id: str | None = None
    external_reference: str | None = None
    code: str | None = None
    message: str | None = None

    def __post_init__(self) -> None:
        provider_id = _required(self.provider_id, "provider_id", 128).lower()
        object.__setattr__(self, "provider_id", provider_id)
        if not isinstance(self.operation, ProviderOperation):
            raise FiscalValidationError("operation must be ProviderOperation")
        if not isinstance(self.status, ProviderResponseStatus):
            raise FiscalValidationError("status must be ProviderResponseStatus")
        object.__setattr__(
            self,
            "correlation_id",
            _required(self.correlation_id, "correlation_id"),
        )


class FiscalProviderTransport(Protocol):
    """Injected transport; production HTTP/SOAP implementations live outside the Core."""

    def exchange(
        self,
        *,
        provider_id: str,
        request: ProviderRequest,
        credentials: EphemeralProviderCredentialsMaterial,
        csc: EphemeralCscMaterial | None,
    ) -> ProviderTransportResponse: ...


class ProviderClock(Protocol):
    def now(self) -> datetime: ...


class SystemProviderClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


class ConfiguredProviderAdapter:
    """One configured provider using runtime-only credentials and optional CSC."""

    def __init__(
        self,
        *,
        descriptor: ProviderDescriptor,
        secret_resolution: SecretResolutionService,
        transport: FiscalProviderTransport,
    ) -> None:
        self.descriptor = descriptor
        self._secret_resolution = secret_resolution
        self._transport = transport

    def execute(self, request: ProviderRequest) -> ProviderResponse:
        if not self.descriptor.supports(
            document_kind=request.document_kind,
            jurisdiction=request.jurisdiction,
            environment=request.scope.environment,
            operation=request.operation,
        ):
            if request.jurisdiction not in self.descriptor.jurisdictions:
                raise UnsupportedJurisdictionError(
                    "provider does not support requested jurisdiction"
                )
            raise UnsupportedProviderError(
                "provider does not support requested fiscal capability"
            )

        credentials = self._resolve_credentials(request)
        csc = (
            self._resolve_csc(request)
            if self.descriptor.requires_csc(request.document_kind, request.operation)
            else None
        )
        response = self._transport.exchange(
            provider_id=self.descriptor.provider_id,
            request=request,
            credentials=credentials,
            csc=csc,
        )
        if not isinstance(response, ProviderTransportResponse):
            raise MalformedProviderResponseError("provider transport returned invalid response")
        return ProviderResponse(
            provider_id=self.descriptor.provider_id,
            operation=request.operation,
            status=response.status,
            correlation_id=request.correlation_id,
            provider_request_id=response.provider_request_id,
            external_reference=response.external_reference,
            code=response.code,
            message=response.message,
        )

    def _resolve_credentials(
        self,
        request: ProviderRequest,
    ) -> EphemeralProviderCredentialsMaterial:
        try:
            material = self._secret_resolution.resolve(
                SecretResolutionContext(
                    scope=request.scope,
                    purpose=SecretUsagePurpose.PROVIDER_AUTHENTICATION,
                    kind=SecretReferenceKind.CREDENTIALS,
                    workload_id=request.workload_id,
                )
            )
        except SecretResolutionError:
            raise ProviderCredentialsUnavailableError(
                "provider credentials are unavailable"
            ) from None
        if not isinstance(material, EphemeralProviderCredentialsMaterial):
            raise ProviderCredentialsUnavailableError("provider credentials are unavailable")
        return material

    def _resolve_csc(self, request: ProviderRequest) -> EphemeralCscMaterial:
        try:
            material = self._secret_resolution.resolve(
                SecretResolutionContext(
                    scope=request.scope,
                    purpose=SecretUsagePurpose.CSC_AUTHENTICATION,
                    kind=SecretReferenceKind.CSC,
                    workload_id=request.workload_id,
                )
            )
        except SecretResolutionError:
            raise CscUnavailableError("CSC is unavailable for requested scope") from None
        if not isinstance(material, EphemeralCscMaterial):
            raise CscUnavailableError("CSC is unavailable for requested scope")
        return material


class ProviderRegistry:
    """Resolve exactly one configured provider or fail closed on none/ambiguity."""

    def __init__(self, adapters: tuple[ConfiguredProviderAdapter, ...]) -> None:
        if not adapters or not all(
            isinstance(item, ConfiguredProviderAdapter) for item in adapters
        ):
            raise FiscalValidationError(
                "adapters must contain ConfiguredProviderAdapter values"
            )
        ids = [item.descriptor.provider_id for item in adapters]
        if len(ids) != len(set(ids)):
            raise FiscalValidationError("provider ids must be unique")
        self._adapters = adapters

    @property
    def descriptors(self) -> tuple[ProviderDescriptor, ...]:
        return tuple(item.descriptor for item in self._adapters)

    def resolve(
        self,
        *,
        document_kind: FiscalDocumentKind,
        jurisdiction: BrazilianJurisdiction,
        environment: FiscalEnvironment,
        operation: ProviderOperation,
        provider_id: str | None = None,
    ) -> ConfiguredProviderAdapter:
        requested_id = provider_id.strip().lower() if provider_id is not None else None
        candidates = [
            item
            for item in self._adapters
            if (requested_id is None or item.descriptor.provider_id == requested_id)
            and item.descriptor.supports(
                document_kind=document_kind,
                jurisdiction=jurisdiction,
                environment=environment,
                operation=operation,
            )
        ]
        if len(candidates) != 1:
            raise UnsupportedProviderError(
                "provider resolution requires exactly one explicit supported provider"
            )
        return candidates[0]


class ProviderGatewayService:
    """Readiness-governed provider routing; adapters never promote readiness."""

    def __init__(
        self,
        *,
        registry: ProviderRegistry,
        readiness: CapabilityReadinessService,
        clock: ProviderClock | None = None,
    ) -> None:
        self._registry = registry
        self._readiness = readiness
        self._clock = clock or SystemProviderClock()

    def execute(
        self,
        request: ProviderRequest,
        *,
        provider_id: str | None = None,
    ) -> ProviderResponse:
        if not isinstance(request, ProviderRequest):
            raise FiscalValidationError("request must be ProviderRequest")
        self._readiness.require_action(
            jurisdiction=request.jurisdiction,
            document_kind=request.document_kind,
            environment=request.scope.environment,
            instant=self._clock.now(),
            action=_OPERATION_ACTION[request.operation],
        )
        adapter = self._registry.resolve(
            document_kind=request.document_kind,
            jurisdiction=request.jurisdiction,
            environment=request.scope.environment,
            operation=request.operation,
            provider_id=provider_id,
        )
        return adapter.execute(request)
