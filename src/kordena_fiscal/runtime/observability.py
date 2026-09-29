"""Vendor-neutral observability primitives for FM NFCORE runtime boundaries."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import RLock
from time import monotonic
from typing import Any, Protocol

_SENSITIVE_KEY = re.compile(
    r"(authorization|password|passwd|secret|token|cookie|private[_-]?key|certificate|pfx|p12|pem|csc|email|legal[_-]?name|buyer|customer[_-]?id)",
    re.IGNORECASE,
)
_PRIVATE_MARKER = "-----BEGIN " + "PRIVATE KEY-----"
_CERTIFICATE_MARKER = "-----BEGIN " + "CERTIFICATE-----"
_SENSITIVE_VALUE = re.compile(
    rf"({re.escape(_PRIVATE_MARKER)}|{re.escape(_CERTIFICATE_MARKER)}|Bearer\s+\S+)",
    re.IGNORECASE,
)


def redact(value: Any, *, key: str | None = None) -> Any:
    """Recursively redact known credential fields without mutating the source object."""

    if key is not None and _SENSITIVE_KEY.search(key):
        return "<redacted>"
    if isinstance(value, Mapping):
        return {str(k): redact(v, key=str(k)) for k, v in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [redact(item) for item in value]
    if isinstance(value, bytes):
        return "<redacted-bytes>"
    if isinstance(value, str) and _SENSITIVE_VALUE.search(value):
        return "<redacted>"
    return value


LogSink = Callable[[str], None]


class StructuredLogger:
    def __init__(self, *, service: str, environment: str, sink: LogSink | None = None) -> None:
        self._service = service
        self._environment = environment
        self._sink = sink or print

    def emit(self, level: str, event: str, **fields: Any) -> None:
        payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": level.upper(),
            "service": self._service,
            "environment": self._environment,
            "event": event,
            **fields,
        }
        self._sink(json.dumps(redact(payload), sort_keys=True, separators=(",", ":")))


@dataclass(frozen=True, slots=True)
class MetricSample:
    name: str
    value: float
    labels: tuple[tuple[str, str], ...] = ()


class MetricsRegistry:
    """Small in-process adapter; export can later be wired to Prometheus/OTel."""

    _ALLOWED_LABELS = frozenset({"method", "status_class", "operation", "outcome", "service"})

    def __init__(self) -> None:
        self._values: dict[tuple[str, tuple[tuple[str, str], ...]], float] = defaultdict(float)
        self._lock = RLock()

    def increment(self, name: str, value: float = 1.0, **labels: str) -> None:
        if value < 0:
            raise ValueError("metric increment must be non-negative")
        unknown = set(labels) - self._ALLOWED_LABELS
        if unknown:
            raise ValueError(f"high-cardinality/unsupported metric labels: {sorted(unknown)}")
        key = (name, tuple(sorted((k, str(v)) for k, v in labels.items())))
        with self._lock:
            self._values[key] += float(value)

    def observe_seconds(self, name: str, seconds: float, **labels: str) -> None:
        self.increment(f"{name}_count", 1.0, **labels)
        self.increment(f"{name}_seconds_total", max(0.0, seconds), **labels)

    def snapshot(self) -> tuple[MetricSample, ...]:
        with self._lock:
            return tuple(
                MetricSample(name=name, value=value, labels=labels)
                for (name, labels), value in sorted(self._values.items())
            )

    def as_dicts(self) -> list[dict[str, Any]]:
        return [
            {"name": sample.name, "value": sample.value, "labels": dict(sample.labels)}
            for sample in self.snapshot()
        ]


@dataclass(frozen=True, slots=True)
class TraceContext:
    trace_id: str
    correlation_id: str
    causation_id: str | None = None


@dataclass(frozen=True, slots=True)
class TraceRecord:
    operation: str
    context: TraceContext
    started_at: datetime
    elapsed_seconds: float
    outcome: str
    attributes: Mapping[str, Any] = field(default_factory=dict)


class TraceSink(Protocol):
    def record(self, trace: TraceRecord) -> None: ...


class NullTraceSink:
    def record(self, trace: TraceRecord) -> None:
        del trace


class SafeTracer:
    """Tracing adapter that redacts attributes and never breaks fiscal execution."""

    def __init__(self, sink: TraceSink | None = None) -> None:
        self._sink = sink or NullTraceSink()

    def record(
        self,
        *,
        operation: str,
        context: TraceContext,
        started_at: datetime,
        elapsed_seconds: float,
        outcome: str,
        attributes: Mapping[str, Any] | None = None,
    ) -> None:
        safe_attributes = redact(dict(attributes or {}))
        try:
            self._sink.record(
                TraceRecord(
                    operation=operation,
                    context=context,
                    started_at=started_at,
                    elapsed_seconds=max(0.0, elapsed_seconds),
                    outcome=outcome,
                    attributes=safe_attributes,
                )
            )
        except Exception:
            # Observability must never become fiscal authority or take the runtime down.
            return


class WorkerObservability:
    def __init__(self, *, metrics: MetricsRegistry, logger: StructuredLogger) -> None:
        self._metrics = metrics
        self._logger = logger

    def cycle_completed(self, result: Any) -> None:
        for outcome in ("claimed", "succeeded", "retry_wait", "dead_letter"):
            value = int(getattr(result, outcome))
            self._metrics.increment("nfcore_worker_jobs_total", value, outcome=outcome)
        self._metrics.observe_seconds("nfcore_worker_cycle", float(result.elapsed_seconds))
        self._logger.emit(
            "INFO",
            "worker_cycle_completed",
            claimed=result.claimed,
            succeeded=result.succeeded,
            retry_wait=result.retry_wait,
            dead_letter=result.dead_letter,
            duration_seconds=result.elapsed_seconds,
        )

    def cycle_failed(self, *, error_type: str, elapsed_seconds: float) -> None:
        self._metrics.increment("nfcore_worker_cycle_failures_total", outcome="failed")
        self._metrics.observe_seconds("nfcore_worker_cycle", elapsed_seconds, outcome="failed")
        self._logger.emit(
            "ERROR",
            "worker_cycle_failed",
            error_type=error_type,
            duration_seconds=elapsed_seconds,
        )


class RequestTimer:
    def __init__(self) -> None:
        self.started = monotonic()

    def elapsed(self) -> float:
        return max(0.0, monotonic() - self.started)
