"""Provider-neutral metrics and bounded-cardinality governance for V2-13."""

from __future__ import annotations

import math
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
)

_METRIC_NAME = re.compile(r"^[a-z][a-z0-9_.-]{0,127}$")
_LABEL_NAME = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_LABEL_VALUE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")
_BASE_LABELS = frozenset(
    {
        "host_namespace",
        "tenant_id",
        "unit_id",
        "environment",
        "document_kind",
        "operation",
        "provider_id",
    }
)
_ALLOWED_OPTIONAL_LABELS = frozenset(
    {
        "queue",
        "reason_code",
        "status",
        "contingency_mode",
    }
)
_FORBIDDEN_LABEL_TOKENS = frozenset(
    {
        "correlation",
        "document_id",
        "reference",
        "payload",
        "secret",
        "token",
        "credential",
        "password",
        "message",
        "error_text",
        "xml",
        "body",
    }
)


class MetricKind(StrEnum):
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"


@dataclass(frozen=True, slots=True)
class MetricDefinition:
    name: str
    kind: MetricKind
    optional_labels: frozenset[str] = frozenset()
    max_series: int = 4096

    def __post_init__(self) -> None:
        name = self.name.strip().lower()
        if not _METRIC_NAME.fullmatch(name):
            raise FiscalValidationError("metric name must be a safe lowercase token")
        object.__setattr__(self, "name", name)
        if not isinstance(self.kind, MetricKind):
            raise FiscalValidationError("metric kind must be MetricKind")
        if not isinstance(self.optional_labels, frozenset):
            raise FiscalValidationError("optional_labels must be a frozenset")
        for label in self.optional_labels:
            if label not in _ALLOWED_OPTIONAL_LABELS:
                raise FiscalValidationError(f"unsupported metric label: {label}")
        if not isinstance(self.max_series, int) or isinstance(self.max_series, bool):
            raise FiscalValidationError("max_series must be an integer")
        if self.max_series < 1 or self.max_series > 100_000:
            raise FiscalValidationError("max_series must be between 1 and 100000")


@dataclass(frozen=True, slots=True)
class MetricPoint:
    definition: MetricDefinition
    labels: Mapping[str, str]
    value: float
    observed_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.definition, MetricDefinition):
            raise FiscalValidationError("definition must be MetricDefinition")
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise FiscalValidationError("observed_at must be timezone-aware")
        object.__setattr__(self, "observed_at", self.observed_at.astimezone(UTC))
        object.__setattr__(self, "labels", MappingProxyType(dict(self.labels)))
        _validate_metric_value(self.definition.kind, self.value)


class MetricSink(Protocol):
    def publish(self, point: MetricPoint) -> None: ...


@dataclass(slots=True)
class InMemoryMetricSink:
    _points: list[MetricPoint] = field(default_factory=list, repr=False)

    def publish(self, point: MetricPoint) -> None:
        if not isinstance(point, MetricPoint):
            raise FiscalValidationError("point must be MetricPoint")
        self._points.append(point)

    @property
    def points(self) -> tuple[MetricPoint, ...]:
        return tuple(self._points)


def _validate_metric_value(kind: MetricKind, value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise FiscalValidationError("metric value must be numeric")
    normalized = float(value)
    if not math.isfinite(normalized):
        raise FiscalValidationError("metric value must be finite")
    if kind in {MetricKind.COUNTER, MetricKind.HISTOGRAM} and normalized < 0:
        raise FiscalValidationError(f"{kind.value} value must not be negative")
    return normalized


def _validate_label_name(name: str) -> str:
    normalized = name.strip().lower()
    if not _LABEL_NAME.fullmatch(normalized):
        raise FiscalValidationError("metric label name is invalid")
    if normalized not in _BASE_LABELS and normalized not in _ALLOWED_OPTIONAL_LABELS:
        raise FiscalValidationError(f"metric label is not whitelisted: {normalized}")
    if any(token in normalized for token in _FORBIDDEN_LABEL_TOKENS):
        raise FiscalValidationError(f"metric label is forbidden: {normalized}")
    return normalized


def _validate_label_value(value: str) -> str:
    if not isinstance(value, str):
        raise FiscalValidationError("metric label value must be a string")
    normalized = value.strip()
    if not _LABEL_VALUE.fullmatch(normalized):
        raise FiscalValidationError("metric label value must be a bounded safe token")
    return normalized


def _context_labels(context: ObservabilityContext) -> dict[str, str]:
    labels = {
        "host_namespace": context.host_namespace,
        "tenant_id": context.tenant_id,
        "unit_id": context.unit_id,
        "environment": context.environment.value,
    }
    if context.document_kind is not None:
        labels["document_kind"] = context.document_kind.value
    if context.operation is not None:
        labels["operation"] = context.operation
    if context.provider_id is not None:
        labels["provider_id"] = context.provider_id
    return {name: _validate_label_value(value) for name, value in labels.items()}


class MetricRecorder:
    """Best-effort metric recorder with per-definition series caps."""

    def __init__(
        self,
        *,
        sink: MetricSink,
        clock: ObservabilityClock | None = None,
    ) -> None:
        self._sink = sink
        self._clock = clock or SystemObservabilityClock()
        self._series: dict[str, set[tuple[tuple[str, str], ...]]] = {}

    def record(
        self,
        *,
        definition: MetricDefinition,
        context: ObservabilityContext,
        value: float,
        labels: Mapping[str, str] | None = None,
    ) -> bool:
        try:
            normalized_value = _validate_metric_value(definition.kind, value)
            merged = _context_labels(context)
            for raw_name, raw_value in (labels or {}).items():
                name = _validate_label_name(raw_name)
                if name in _BASE_LABELS:
                    raise FiscalValidationError("base metric labels cannot be overridden")
                if name not in definition.optional_labels:
                    raise FiscalValidationError(
                        f"metric label is not enabled for {definition.name}: {name}"
                    )
                merged[name] = _validate_label_value(raw_value)
            series_key = tuple(sorted(merged.items()))
            known = self._series.setdefault(definition.name, set())
            if series_key not in known and len(known) >= definition.max_series:
                return False
            point = MetricPoint(
                definition=definition,
                labels=merged,
                value=normalized_value,
                observed_at=self._clock.now(),
            )
            self._sink.publish(point)
            known.add(series_key)
        except Exception:
            return False
        return True

    def series_count(self, metric_name: str) -> int:
        return len(self._series.get(metric_name.strip().lower(), set()))


QUEUE_DEPTH = MetricDefinition(
    name="fiscal.queue.depth",
    kind=MetricKind.GAUGE,
    optional_labels=frozenset({"queue", "status"}),
)
RETRY_TOTAL = MetricDefinition(
    name="fiscal.retry.total",
    kind=MetricKind.COUNTER,
    optional_labels=frozenset({"reason_code"}),
)
REJECTION_TOTAL = MetricDefinition(
    name="fiscal.rejection.total",
    kind=MetricKind.COUNTER,
    optional_labels=frozenset({"reason_code"}),
)
UNKNOWN_OUTCOME_TOTAL = MetricDefinition(
    name="fiscal.provider.unknown_outcome.total",
    kind=MetricKind.COUNTER,
    optional_labels=frozenset({"status"}),
)
CONTINGENCY_ACTIVE = MetricDefinition(
    name="fiscal.contingency.active",
    kind=MetricKind.GAUGE,
    optional_labels=frozenset({"contingency_mode"}),
)
OPERATION_DURATION_SECONDS = MetricDefinition(
    name="fiscal.operation.duration_seconds",
    kind=MetricKind.HISTOGRAM,
    optional_labels=frozenset({"status"}),
)
