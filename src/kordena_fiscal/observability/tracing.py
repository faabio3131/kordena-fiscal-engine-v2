"""Provider-neutral tracing, correlation and causation contracts for V2-13."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Protocol

from kordena_fiscal.domain import FiscalValidationError

from .events import (
    ObservabilityClock,
    ObservabilityContext,
    SystemObservabilityClock,
    sanitize_observability_attributes,
)

_TRACE_ID = re.compile(r"^[0-9a-f]{32}$")
_SPAN_ID = re.compile(r"^[0-9a-f]{16}$")
_REFERENCE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$")
_SPAN_NAME = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
_HEADER_TRACE_ID = "x-fm-trace-id"
_HEADER_SPAN_ID = "x-fm-span-id"
_HEADER_PARENT_SPAN_ID = "x-fm-parent-span-id"
_HEADER_CORRELATION_ID = "x-fm-correlation-id"
_HEADER_CAUSATION_ID = "x-fm-causation-id"
_ALLOWED_HEADERS = frozenset(
    {
        _HEADER_TRACE_ID,
        _HEADER_SPAN_ID,
        _HEADER_PARENT_SPAN_ID,
        _HEADER_CORRELATION_ID,
        _HEADER_CAUSATION_ID,
    }
)


class TraceStatus(StrEnum):
    UNSET = "unset"
    OK = "ok"
    ERROR = "error"


def _required_reference(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not _REFERENCE_ID.fullmatch(normalized):
        raise FiscalValidationError(f"{field_name} must be a bounded safe reference")
    return normalized


def _trace_id(value: str) -> str:
    normalized = value.strip().lower()
    if not _TRACE_ID.fullmatch(normalized):
        raise FiscalValidationError("trace_id must contain exactly 32 lowercase hex chars")
    return normalized


def _span_id(value: str, field_name: str = "span_id") -> str:
    normalized = value.strip().lower()
    if not _SPAN_ID.fullmatch(normalized):
        raise FiscalValidationError(f"{field_name} must contain exactly 16 lowercase hex chars")
    return normalized


@dataclass(frozen=True, slots=True)
class TraceContext:
    trace_id: str
    span_id: str
    correlation_id: str
    causation_id: str | None = None
    parent_span_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "trace_id", _trace_id(self.trace_id))
        object.__setattr__(self, "span_id", _span_id(self.span_id))
        object.__setattr__(
            self,
            "correlation_id",
            _required_reference(self.correlation_id, "correlation_id"),
        )
        if self.causation_id is not None:
            object.__setattr__(
                self,
                "causation_id",
                _required_reference(self.causation_id, "causation_id"),
            )
        if self.parent_span_id is not None:
            object.__setattr__(
                self,
                "parent_span_id",
                _span_id(self.parent_span_id, "parent_span_id"),
            )
            if self.parent_span_id == self.span_id:
                raise FiscalValidationError("span cannot be its own parent")

    def child(self, *, span_id: str, causation_id: str | None = None) -> TraceContext:
        return TraceContext(
            trace_id=self.trace_id,
            span_id=span_id,
            parent_span_id=self.span_id,
            correlation_id=self.correlation_id,
            causation_id=causation_id if causation_id is not None else self.causation_id,
        )


class TracePropagation:
    """Language-neutral carrier using a fixed allowlist of propagation headers."""

    @staticmethod
    def to_carrier(context: TraceContext) -> Mapping[str, str]:
        values = {
            _HEADER_TRACE_ID: context.trace_id,
            _HEADER_SPAN_ID: context.span_id,
            _HEADER_CORRELATION_ID: context.correlation_id,
        }
        if context.parent_span_id is not None:
            values[_HEADER_PARENT_SPAN_ID] = context.parent_span_id
        if context.causation_id is not None:
            values[_HEADER_CAUSATION_ID] = context.causation_id
        return MappingProxyType(values)

    @staticmethod
    def from_carrier(carrier: Mapping[str, str]) -> TraceContext:
        normalized = {key.strip().lower(): value for key, value in carrier.items()}
        unexpected = set(normalized) - _ALLOWED_HEADERS
        if unexpected:
            raise FiscalValidationError("trace carrier contains unsupported headers")
        try:
            trace_id = normalized[_HEADER_TRACE_ID]
            span_id = normalized[_HEADER_SPAN_ID]
            correlation_id = normalized[_HEADER_CORRELATION_ID]
        except KeyError as exc:
            raise FiscalValidationError("trace carrier is missing required headers") from exc
        return TraceContext(
            trace_id=trace_id,
            span_id=span_id,
            correlation_id=correlation_id,
            parent_span_id=normalized.get(_HEADER_PARENT_SPAN_ID),
            causation_id=normalized.get(_HEADER_CAUSATION_ID),
        )


@dataclass(frozen=True, slots=True)
class TraceSpan:
    span_name: str
    trace: TraceContext
    context: ObservabilityContext
    started_at: datetime
    finished_at: datetime
    status: TraceStatus = TraceStatus.UNSET
    attributes: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        name = self.span_name.strip().lower()
        if not _SPAN_NAME.fullmatch(name):
            raise FiscalValidationError("span_name must be a safe lowercase token")
        object.__setattr__(self, "span_name", name)
        if not isinstance(self.trace, TraceContext):
            raise FiscalValidationError("trace must be TraceContext")
        if not isinstance(self.context, ObservabilityContext):
            raise FiscalValidationError("context must be ObservabilityContext")
        if not isinstance(self.status, TraceStatus):
            raise FiscalValidationError("status must be TraceStatus")
        for field_name in ("started_at", "finished_at"):
            instant = getattr(self, field_name)
            if instant.tzinfo is None or instant.utcoffset() is None:
                raise FiscalValidationError(f"{field_name} must be timezone-aware")
            object.__setattr__(self, field_name, instant.astimezone(UTC))
        if self.finished_at < self.started_at:
            raise FiscalValidationError("finished_at must not be before started_at")
        if self.trace.correlation_id != self.context.correlation_id:
            raise FiscalValidationError("trace correlation_id must match fiscal scope")
        object.__setattr__(
            self,
            "attributes",
            sanitize_observability_attributes(self.attributes),
        )


class TraceSpanSink(Protocol):
    def publish(self, span: TraceSpan) -> None: ...


@dataclass(slots=True)
class InMemoryTraceSpanSink:
    _spans: list[TraceSpan] = field(default_factory=list, repr=False)

    def publish(self, span: TraceSpan) -> None:
        if not isinstance(span, TraceSpan):
            raise FiscalValidationError("span must be TraceSpan")
        self._spans.append(span)

    @property
    def spans(self) -> tuple[TraceSpan, ...]:
        return tuple(self._spans)


class TraceRecorder:
    """Best-effort span recorder; tracing failure never changes fiscal execution."""

    def __init__(
        self,
        *,
        sink: TraceSpanSink,
        clock: ObservabilityClock | None = None,
    ) -> None:
        self._sink = sink
        self._clock = clock or SystemObservabilityClock()

    def record(
        self,
        *,
        span_name: str,
        trace: TraceContext,
        context: ObservabilityContext,
        started_at: datetime,
        status: TraceStatus = TraceStatus.UNSET,
        attributes: Mapping[str, object] | None = None,
    ) -> bool:
        try:
            span = TraceSpan(
                span_name=span_name,
                trace=trace,
                context=context,
                started_at=started_at,
                finished_at=self._clock.now(),
                status=status,
                attributes=attributes or {},
            )
            self._sink.publish(span)
        except Exception:
            return False
        return True
