from __future__ import annotations

from datetime import UTC, datetime

import pytest

from kordena_fiscal.domain import (
    ExecutionScope,
    FiscalDocumentKind,
    FiscalEnvironment,
    FiscalValidationError,
)
from kordena_fiscal.observability import (
    CONTINGENCY_ACTIVE,
    OPERATION_DURATION_SECONDS,
    QUEUE_DEPTH,
    REJECTION_TOTAL,
    RETRY_TOTAL,
    UNKNOWN_OUTCOME_TOTAL,
    InMemoryMetricSink,
    MetricDefinition,
    MetricKind,
    MetricPoint,
    MetricRecorder,
    ObservabilityContext,
)

NOW = datetime(2026, 9, 13, 15, 30, tzinfo=UTC)


class _Clock:
    def now(self) -> datetime:
        return NOW


class _FailingMetricSink:
    def publish(self, point: MetricPoint) -> None:
        raise RuntimeError("synthetic metric sink unavailable")


def _context(
    *,
    host: str = "fm.kordena",
    tenant: str = "tenant-a",
    unit: str = "unit-a",
    provider: str | None = "synthetic-sp",
) -> ObservabilityContext:
    return ObservabilityContext(
        scope=ExecutionScope(
            host_namespace=host,
            tenant_id=tenant,
            unit_id=unit,
            environment=FiscalEnvironment.HOMOLOGATION,
            correlation_id=f"corr-{tenant}-{unit}",
        ),
        document_kind=FiscalDocumentKind.NFE,
        provider_id=provider,
        operation="authorize",
    )


def test_queue_metric_contains_only_governed_scope_and_optional_labels() -> None:
    sink = InMemoryMetricSink()
    recorder = MetricRecorder(sink=sink, clock=_Clock())

    assert recorder.record(
        definition=QUEUE_DEPTH,
        context=_context(),
        value=7,
        labels={"queue": "provider-outbox", "status": "pending"},
    )

    point = sink.points[0]
    assert point.observed_at == NOW
    assert point.value == 7.0
    assert point.labels == {
        "host_namespace": "fm.kordena",
        "tenant_id": "tenant-a",
        "unit_id": "unit-a",
        "environment": "homologation",
        "document_kind": "nfe",
        "operation": "authorize",
        "provider_id": "synthetic-sp",
        "queue": "provider-outbox",
        "status": "pending",
    }
    assert "correlation_id" not in point.labels


def test_metric_series_are_isolated_by_host_tenant_and_unit() -> None:
    sink = InMemoryMetricSink()
    recorder = MetricRecorder(sink=sink, clock=_Clock())

    assert recorder.record(definition=RETRY_TOTAL, context=_context(), value=1)
    assert recorder.record(
        definition=RETRY_TOTAL,
        context=_context(host="fm.iron", tenant="tenant-a", unit="unit-a"),
        value=1,
    )
    assert recorder.record(
        definition=RETRY_TOTAL,
        context=_context(tenant="tenant-b", unit="unit-b"),
        value=1,
    )

    assert recorder.series_count(RETRY_TOTAL.name) == 3
    partitions = {
        (
            point.labels["host_namespace"],
            point.labels["tenant_id"],
            point.labels["unit_id"],
        )
        for point in sink.points
    }
    assert partitions == {
        ("fm.kordena", "tenant-a", "unit-a"),
        ("fm.iron", "tenant-a", "unit-a"),
        ("fm.kordena", "tenant-b", "unit-b"),
    }


def test_series_cap_rejects_new_partition_but_allows_existing_partition() -> None:
    definition = MetricDefinition(
        name="fiscal.test.bounded",
        kind=MetricKind.COUNTER,
        max_series=2,
    )
    sink = InMemoryMetricSink()
    recorder = MetricRecorder(sink=sink, clock=_Clock())

    assert recorder.record(definition=definition, context=_context(tenant="a"), value=1)
    assert recorder.record(definition=definition, context=_context(tenant="b"), value=1)
    assert recorder.record(definition=definition, context=_context(tenant="c"), value=1) is False
    assert recorder.record(definition=definition, context=_context(tenant="a"), value=1)

    assert recorder.series_count(definition.name) == 2
    assert len(sink.points) == 3


def test_unwhitelisted_high_cardinality_labels_fail_closed() -> None:
    sink = InMemoryMetricSink()
    recorder = MetricRecorder(sink=sink, clock=_Clock())

    assert recorder.record(
        definition=RETRY_TOTAL,
        context=_context(),
        value=1,
        labels={"correlation_id": "corr-unique-001"},
    ) is False
    assert recorder.record(
        definition=RETRY_TOTAL,
        context=_context(),
        value=1,
        labels={"document_id": "doc-unique-001"},
    ) is False
    assert sink.points == ()


def test_metric_optional_labels_cannot_override_scope_or_smuggle_free_text() -> None:
    sink = InMemoryMetricSink()
    recorder = MetricRecorder(sink=sink, clock=_Clock())

    assert recorder.record(
        definition=REJECTION_TOTAL,
        context=_context(),
        value=1,
        labels={"tenant_id": "tenant-other"},
    ) is False
    assert recorder.record(
        definition=REJECTION_TOTAL,
        context=_context(),
        value=1,
        labels={"reason_code": "Bearer secret-value"},
    ) is False
    assert sink.points == ()


def test_counter_and_histogram_reject_negative_or_nonfinite_values() -> None:
    sink = InMemoryMetricSink()
    recorder = MetricRecorder(sink=sink, clock=_Clock())

    assert recorder.record(definition=RETRY_TOTAL, context=_context(), value=-1) is False
    assert recorder.record(
        definition=OPERATION_DURATION_SECONDS,
        context=_context(),
        value=-0.1,
    ) is False
    assert recorder.record(definition=RETRY_TOTAL, context=_context(), value=float("inf")) is False
    assert sink.points == ()


def test_gauge_can_represent_signed_operational_delta() -> None:
    definition = MetricDefinition(name="fiscal.test.delta", kind=MetricKind.GAUGE)
    sink = InMemoryMetricSink()
    recorder = MetricRecorder(sink=sink, clock=_Clock())

    assert recorder.record(definition=definition, context=_context(), value=-2)
    assert sink.points[0].value == -2.0


def test_catalog_covers_required_operational_metric_families() -> None:
    assert QUEUE_DEPTH.kind is MetricKind.GAUGE
    assert RETRY_TOTAL.kind is MetricKind.COUNTER
    assert REJECTION_TOTAL.kind is MetricKind.COUNTER
    assert UNKNOWN_OUTCOME_TOTAL.kind is MetricKind.COUNTER
    assert CONTINGENCY_ACTIVE.kind is MetricKind.GAUGE
    assert OPERATION_DURATION_SECONDS.kind is MetricKind.HISTOGRAM


def test_metric_definition_rejects_non_whitelisted_label_schema() -> None:
    with pytest.raises(FiscalValidationError, match="unsupported metric label"):
        MetricDefinition(
            name="fiscal.invalid.metric",
            kind=MetricKind.COUNTER,
            optional_labels=frozenset({"correlation_id"}),
        )


def test_metric_sink_failure_is_best_effort() -> None:
    recorder = MetricRecorder(sink=_FailingMetricSink(), clock=_Clock())

    assert recorder.record(
        definition=RETRY_TOTAL,
        context=_context(),
        value=1,
        labels={"reason_code": "timeout"},
    ) is False
    assert recorder.series_count(RETRY_TOTAL.name) == 0
