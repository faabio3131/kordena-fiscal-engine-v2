from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from kordena_fiscal.domain import (
    ExecutionScope,
    FiscalDocumentKind,
    FiscalEnvironment,
    FiscalValidationError,
)
from kordena_fiscal.observability import (
    InMemoryTraceSpanSink,
    ObservabilityContext,
    TraceContext,
    TracePropagation,
    TraceRecorder,
    TraceSpan,
    TraceStatus,
)

NOW = datetime(2026, 9, 13, 16, 0, tzinfo=UTC)
TRACE_ID = "a" * 32
ROOT_SPAN = "1" * 16
OUTBOX_SPAN = "2" * 16
PROVIDER_SPAN = "3" * 16
RECON_SPAN = "4" * 16
CORRELATION = "corr-trace-001"


class _Clock:
    def now(self) -> datetime:
        return NOW


class _FailingTraceSink:
    def publish(self, span: TraceSpan) -> None:
        raise RuntimeError("synthetic trace sink unavailable")


def _context(
    *,
    correlation_id: str = CORRELATION,
    host: str = "fm.kordena",
    tenant: str = "tenant-trace",
    unit: str = "unit-trace",
    provider: str | None = "synthetic-sp",
    operation: str | None = "authorize",
) -> ObservabilityContext:
    return ObservabilityContext(
        scope=ExecutionScope(
            host_namespace=host,
            tenant_id=tenant,
            unit_id=unit,
            environment=FiscalEnvironment.HOMOLOGATION,
            correlation_id=correlation_id,
        ),
        document_kind=FiscalDocumentKind.NFE,
        provider_id=provider,
        operation=operation,
    )


def _root() -> TraceContext:
    return TraceContext(
        trace_id=TRACE_ID,
        span_id=ROOT_SPAN,
        correlation_id=CORRELATION,
        causation_id="command-001",
    )


def test_trace_carrier_roundtrip_uses_fixed_allowlist() -> None:
    root = _root()
    carrier = TracePropagation.to_carrier(root)

    assert carrier == {
        "x-fm-trace-id": TRACE_ID,
        "x-fm-span-id": ROOT_SPAN,
        "x-fm-correlation-id": CORRELATION,
        "x-fm-causation-id": "command-001",
    }
    assert TracePropagation.from_carrier(carrier) == root


def test_trace_carrier_rejects_unknown_headers() -> None:
    carrier = dict(TracePropagation.to_carrier(_root()))
    carrier["authorization"] = "Bearer forbidden"

    with pytest.raises(FiscalValidationError, match="unsupported headers"):
        TracePropagation.from_carrier(carrier)


def test_child_spans_preserve_trace_and_correlation_chain() -> None:
    application = _root()
    outbox = application.child(span_id=OUTBOX_SPAN, causation_id="event-outbox-001")
    provider = outbox.child(span_id=PROVIDER_SPAN, causation_id="delivery-001")
    reconciliation = provider.child(span_id=RECON_SPAN, causation_id="query-001")

    assert {item.trace_id for item in (application, outbox, provider, reconciliation)} == {
        TRACE_ID
    }
    assert {
        item.correlation_id for item in (application, outbox, provider, reconciliation)
    } == {CORRELATION}
    assert outbox.parent_span_id == ROOT_SPAN
    assert provider.parent_span_id == OUTBOX_SPAN
    assert reconciliation.parent_span_id == PROVIDER_SPAN


def test_replay_can_rehydrate_carrier_without_persisting_trace_as_fiscal_state() -> None:
    outbox = _root().child(span_id=OUTBOX_SPAN, causation_id="event-outbox-001")
    carrier = TracePropagation.to_carrier(outbox)

    rehydrated = TracePropagation.from_carrier(carrier)
    provider = rehydrated.child(span_id=PROVIDER_SPAN, causation_id="delivery-replay-001")

    assert provider.trace_id == TRACE_ID
    assert provider.parent_span_id == OUTBOX_SPAN
    assert provider.correlation_id == CORRELATION
    assert provider.causation_id == "delivery-replay-001"


def test_span_attributes_reuse_fail_closed_sanitization() -> None:
    sink = InMemoryTraceSpanSink()
    recorder = TraceRecorder(sink=sink, clock=_Clock())

    assert recorder.record(
        span_name="provider.authorize",
        trace=_root(),
        context=_context(),
        started_at=NOW - timedelta(milliseconds=10),
        status=TraceStatus.OK,
        attributes={
            "status": "accepted",
            "payload": b"secret-payload",
            "credential_reference_id": "ref:provider/credential",
            "authorization": "Bearer forbidden",
        },
    )

    span = sink.spans[0]
    assert span.attributes["status"] == "accepted"
    assert span.attributes["payload"] == "[REDACTED]"
    assert span.attributes["credential_reference_id"] == "ref:provider/credential"
    assert span.attributes["authorization"] == "[REDACTED]"


def test_trace_correlation_must_match_explicit_fiscal_scope() -> None:
    sink = InMemoryTraceSpanSink()
    recorder = TraceRecorder(sink=sink, clock=_Clock())

    assert recorder.record(
        span_name="provider.authorize",
        trace=_root(),
        context=_context(correlation_id="corr-other"),
        started_at=NOW - timedelta(milliseconds=1),
    ) is False
    assert sink.spans == ()


def test_invalid_trace_and_span_identifiers_fail_closed() -> None:
    with pytest.raises(FiscalValidationError, match="32 lowercase hex"):
        TraceContext(trace_id="trace-1", span_id=ROOT_SPAN, correlation_id=CORRELATION)
    with pytest.raises(FiscalValidationError, match="16 lowercase hex"):
        TraceContext(trace_id=TRACE_ID, span_id="span-1", correlation_id=CORRELATION)
    with pytest.raises(FiscalValidationError, match="own parent"):
        TraceContext(
            trace_id=TRACE_ID,
            span_id=ROOT_SPAN,
            parent_span_id=ROOT_SPAN,
            correlation_id=CORRELATION,
        )


def test_trace_sink_failure_is_best_effort() -> None:
    recorder = TraceRecorder(sink=_FailingTraceSink(), clock=_Clock())

    assert recorder.record(
        span_name="application.execute",
        trace=_root(),
        context=_context(provider=None, operation="execute"),
        started_at=NOW,
        status=TraceStatus.OK,
    ) is False


def test_span_scope_isolation_is_explicit() -> None:
    sink = InMemoryTraceSpanSink()
    recorder = TraceRecorder(sink=sink, clock=_Clock())

    for trace_id, span_id, context in (
        ("b" * 32, "5" * 16, _context(host="fm.kordena", tenant="tenant-a", unit="u1")),
        ("c" * 32, "6" * 16, _context(host="fm.iron", tenant="tenant-a", unit="u1")),
        ("d" * 32, "7" * 16, _context(host="fm.kordena", tenant="tenant-b", unit="u2")),
    ):
        trace = TraceContext(
            trace_id=trace_id,
            span_id=span_id,
            correlation_id=context.correlation_id,
        )
        assert recorder.record(
            span_name="application.execute",
            trace=trace,
            context=context,
            started_at=NOW,
            status=TraceStatus.OK,
        )

    partitions = {
        (span.context.host_namespace, span.context.tenant_id, span.context.unit_id)
        for span in sink.spans
    }
    assert partitions == {
        ("fm.kordena", "tenant-a", "u1"),
        ("fm.iron", "tenant-a", "u1"),
        ("fm.kordena", "tenant-b", "u2"),
    }
