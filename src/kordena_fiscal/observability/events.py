"""Provider-neutral structured observability boundary for V2-13.

Observability is deliberately outside the fiscal domain. It receives already-known
scope/context, sanitizes all free-form metadata and publishes only sanitized events.
Telemetry failure must never change fiscal execution semantics.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Mapping, Protocol

from kordena_fiscal.domain import (
    ExecutionScope,
    FiscalDocumentKind,
    FiscalEnvironment,
    FiscalValidationError,
)

_REDACTED = "[REDACTED]"
_TRUNCATED = "…[TRUNCATED]"
_EVENT_NAME = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
_TOKEN = re.compile(r"^[a-z0-9][a-z0-9._:/-]{0,127}$")
_SENSITIVE_KEY_TOKENS = frozenset(
    {
        "api_key",
        "authorization",
        "body",
        "certificate",
        "content",
        "cookie",
        "credential",
        "csc",
        "password",
        "payload",
        "pem",
        "pfx",
        "pkcs12",
        "private_key",
        "secret",
        "signature",
        "token",
        "xml",
    }
)
_SAFE_SENSITIVE_SUFFIXES = (
    "_reference",
    "_reference_id",
    "_sha256",
    "_hash",
    "_fingerprint",
    "_fingerprint_sha256",
)
_SENSITIVE_TEXT_MARKERS = (
    "-----begin ",
    "<?xml",
    "<nfe",
    "<nfce",
    "<nfse",
    "bearer ",
    "basic ",
    "password=",
    "password:",
    "secret=",
    "secret:",
    "token=",
    "token:",
    "credential=",
    "credential:",
    "api_key=",
    "api-key=",
)
_MAX_TEXT_LENGTH = 1024
_MAX_COLLECTION_ITEMS = 64
_MAX_DEPTH = 8


class ObservabilitySeverity(StrEnum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ObservabilityCategory(StrEnum):
    APPLICATION = "application"
    CONTROL_PLANE = "control-plane"
    PROVIDER = "provider"
    DELIVERY = "delivery"
    RECONCILIATION = "reconciliation"
    ARCHIVE = "archive"
    SECURITY = "security"
    COMPLIANCE = "compliance"


class ObservabilityClock(Protocol):
    def now(self) -> datetime: ...


class SystemObservabilityClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


class StructuredEventSink(Protocol):
    def publish(self, event: StructuredObservabilityEvent) -> None: ...


def _required_token(value: str, field_name: str) -> str:
    normalized = value.strip().lower()
    if not _TOKEN.fullmatch(normalized):
        raise FiscalValidationError(f"{field_name} must be a safe token")
    return normalized


def _is_sensitive_key(key: str) -> bool:
    normalized = key.strip().lower().replace("-", "_")
    if not normalized:
        return True
    if normalized.endswith(_SAFE_SENSITIVE_SUFFIXES):
        return False
    return any(token in normalized for token in _SENSITIVE_KEY_TOKENS)


def _sanitize_text(value: str) -> str:
    lowered = value.casefold()
    if any(marker in lowered for marker in _SENSITIVE_TEXT_MARKERS):
        return _REDACTED
    if len(value) <= _MAX_TEXT_LENGTH:
        return value
    return value[:_MAX_TEXT_LENGTH] + _TRUNCATED


def sanitize_observability_value(value: object, *, _depth: int = 0) -> object:
    """Sanitize recursively without ever serializing unknown objects through repr()."""

    if _depth >= _MAX_DEPTH:
        return _REDACTED
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return _sanitize_text(value)
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            return _REDACTED
        return value.astimezone(UTC).isoformat()
    if isinstance(value, (bytes, bytearray, memoryview)):
        return _REDACTED
    if isinstance(value, Mapping):
        sanitized: dict[str, object] = {}
        for index, (raw_key, raw_value) in enumerate(value.items()):
            if index >= _MAX_COLLECTION_ITEMS:
                sanitized["_truncated"] = True
                break
            if not isinstance(raw_key, str):
                continue
            key = raw_key.strip()
            if not key:
                continue
            sanitized[key] = (
                _REDACTED
                if _is_sensitive_key(key)
                else sanitize_observability_value(raw_value, _depth=_depth + 1)
            )
        return MappingProxyType(sanitized)
    if isinstance(value, (tuple, list, set, frozenset)):
        items = tuple(value)
        sanitized_items = tuple(
            sanitize_observability_value(item, _depth=_depth + 1)
            for item in items[:_MAX_COLLECTION_ITEMS]
        )
        if len(items) > _MAX_COLLECTION_ITEMS:
            return (*sanitized_items, _TRUNCATED)
        return sanitized_items
    return _REDACTED


def sanitize_observability_attributes(
    attributes: Mapping[str, object] | None,
) -> Mapping[str, object]:
    if attributes is None:
        return MappingProxyType({})
    sanitized = sanitize_observability_value(attributes)
    if not isinstance(sanitized, Mapping):
        return MappingProxyType({})
    return sanitized


@dataclass(frozen=True, slots=True)
class ObservabilityContext:
    """Explicit fiscal partition carried into observability without payload data."""

    scope: ExecutionScope
    document_kind: FiscalDocumentKind | None = None
    provider_id: str | None = None
    operation: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.scope, ExecutionScope):
            raise FiscalValidationError("scope must be ExecutionScope")
        if self.scope.host_namespace is None:
            raise FiscalValidationError("observability requires host_namespace")
        if self.document_kind is not None and not isinstance(
            self.document_kind,
            FiscalDocumentKind,
        ):
            raise FiscalValidationError("document_kind must be FiscalDocumentKind")
        if self.provider_id is not None:
            object.__setattr__(
                self,
                "provider_id",
                _required_token(self.provider_id, "provider_id"),
            )
        if self.operation is not None:
            object.__setattr__(
                self,
                "operation",
                _required_token(self.operation, "operation"),
            )

    @property
    def host_namespace(self) -> str:
        host = self.scope.host_namespace
        if host is None:  # pragma: no cover - guarded in __post_init__
            raise FiscalValidationError("observability requires host_namespace")
        return host

    @property
    def tenant_id(self) -> str:
        return self.scope.tenant_id

    @property
    def unit_id(self) -> str:
        return self.scope.unit_id

    @property
    def environment(self) -> FiscalEnvironment:
        return self.scope.environment

    @property
    def correlation_id(self) -> str:
        return self.scope.correlation_id


@dataclass(frozen=True, slots=True)
class StructuredObservabilityEvent:
    event_name: str
    severity: ObservabilitySeverity
    category: ObservabilityCategory
    occurred_at: datetime
    context: ObservabilityContext
    message: str | None = None
    attributes: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        event_name = self.event_name.strip().lower()
        if not _EVENT_NAME.fullmatch(event_name):
            raise FiscalValidationError("event_name must be a safe lowercase token")
        object.__setattr__(self, "event_name", event_name)
        if not isinstance(self.severity, ObservabilitySeverity):
            raise FiscalValidationError("severity must be ObservabilitySeverity")
        if not isinstance(self.category, ObservabilityCategory):
            raise FiscalValidationError("category must be ObservabilityCategory")
        if not isinstance(self.context, ObservabilityContext):
            raise FiscalValidationError("context must be ObservabilityContext")
        if self.occurred_at.tzinfo is None or self.occurred_at.utcoffset() is None:
            raise FiscalValidationError("occurred_at must be timezone-aware")
        object.__setattr__(self, "occurred_at", self.occurred_at.astimezone(UTC))
        if self.message is not None:
            object.__setattr__(self, "message", _sanitize_text(self.message))
        object.__setattr__(
            self,
            "attributes",
            sanitize_observability_attributes(self.attributes),
        )


@dataclass(slots=True)
class InMemoryStructuredEventSink:
    """Synthetic sink with no filesystem, network or persistence side effects."""

    _events: list[StructuredObservabilityEvent] = field(default_factory=list, repr=False)

    def publish(self, event: StructuredObservabilityEvent) -> None:
        if not isinstance(event, StructuredObservabilityEvent):
            raise FiscalValidationError("event must be StructuredObservabilityEvent")
        self._events.append(event)

    @property
    def events(self) -> tuple[StructuredObservabilityEvent, ...]:
        return tuple(self._events)


class StructuredObservabilityService:
    """Best-effort sanitized publisher that cannot change fiscal semantics."""

    def __init__(
        self,
        *,
        sink: StructuredEventSink,
        clock: ObservabilityClock | None = None,
    ) -> None:
        self._sink = sink
        self._clock = clock or SystemObservabilityClock()

    def emit(
        self,
        *,
        event_name: str,
        severity: ObservabilitySeverity,
        category: ObservabilityCategory,
        context: ObservabilityContext,
        message: str | None = None,
        attributes: Mapping[str, object] | None = None,
    ) -> bool:
        try:
            event = StructuredObservabilityEvent(
                event_name=event_name,
                severity=severity,
                category=category,
                occurred_at=self._clock.now(),
                context=context,
                message=message,
                attributes=attributes or {},
            )
            self._sink.publish(event)
        except Exception:
            return False
        return True
