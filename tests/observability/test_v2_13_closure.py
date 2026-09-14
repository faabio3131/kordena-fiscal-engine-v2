from __future__ import annotations

from dataclasses import fields
from datetime import UTC, datetime, timedelta
from pathlib import Path

from kordena_fiscal.compliance import (
    CapabilityReadinessService,
    FiscalActionCapability,
    FiscalCapabilityLevel,
    JurisdictionCapabilityMatrix,
    JurisdictionCapabilityRule,
    RegulatoryReviewDecisionKind,
    RegulatoryWatcherService,
    TechnicalValidationMode,
)
from kordena_fiscal.domain import (
    BrazilianJurisdiction,
    ExecutionScope,
    FiscalDocumentKind,
    FiscalEnvironment,
)
from kordena_fiscal.observability import (
    QUEUE_DEPTH,
    AlertRegistry,
    ComplianceOperationalAlert,
    InMemoryAlertSink,
    InMemoryMetricSink,
    InMemoryStructuredEventSink,
    InMemoryTraceSpanSink,
    MetricPoint,
    MetricRecorder,
    ObservabilityCategory,
    ObservabilityContext,
    ObservabilitySeverity,
    OperationalAlertEvaluator,
    StructuredObservabilityEvent,
    StructuredObservabilityService,
    TraceContext,
    TracePropagation,
    TraceRecorder,
    TraceSpan,
    TraceStatus,
)

NOW = datetime(2026, 9, 13, 18, 0, tzinfo=UTC)
SP = BrazilianJurisdiction("SP")


class _Clock:
    def now(self) -> datetime:
        return NOW


class _FailingEventSink:
    def publish(self, event: StructuredObservabilityEvent) -> None:
        raise RuntimeError("synthetic event sink failure")


class _FailingMetricSink:
    def publish(self, point: MetricPoint) -> None:
        raise RuntimeError("synthetic metric sink failure")


class _FailingTraceSink:
    def publish(self, span: TraceSpan) -> None:
        raise RuntimeError("synthetic trace sink failure")


class _FailingAlertSink:
    def publish(self, alert: ComplianceOperationalAlert) -> None:
        raise RuntimeError("synthetic alert sink failure")


def _context(
    *,
    host: str = "fm.kordena",
    tenant: str = "tenant-closure",
    unit: str = "unit-closure",
    provider: str = "synthetic-sp",
    correlation: str = "corr-v2-13-closure",
) -> ObservabilityContext:
    return ObservabilityContext(
        scope=ExecutionScope(
            host_namespace=host,
            tenant_id=tenant,
            unit_id=unit,
            environment=FiscalEnvironment.HOMOLOGATION,
            correlation_id=correlation,
        ),
        document_kind=FiscalDocumentKind.NFE,
        provider_id=provider,
        operation="authorize",
    )


def test_b1_to_b4_surfaces_share_scope_and_sanitize_sensitive_material() -> None:
    context = _context()
    event_sink = InMemoryStructuredEventSink()
    metric_sink = InMemoryMetricSink()
    trace_sink = InMemoryTraceSpanSink()
    alert_sink = InMemoryAlertSink()

    event_service = StructuredObservabilityService(sink=event_sink, clock=_Clock())
    metric_recorder = MetricRecorder(sink=metric_sink, clock=_Clock())
    trace_recorder = TraceRecorder(sink=trace_sink, clock=_Clock())
    alert_registry = AlertRegistry(sink=alert_sink, clock=_Clock())
    alert_evaluator = OperationalAlertEvaluator(registry=alert_registry, clock=_Clock())

    assert event_service.emit(
        event_name="provider.authorize.completed",
        severity=ObservabilitySeverity.INFO,
        category=ObservabilityCategory.PROVIDER,
        context=context,
        attributes={
            "payload": "<NFe>must-not-leak</NFe>",
            "credential": "must-not-leak",
            "payload_sha256": "a" * 64,
            "credential_reference_id": "credential-ref-001",
        },
    )
    assert metric_recorder.record(
        definition=QUEUE_DEPTH,
        context=context,
        value=3,
        labels={"queue": "provider-outbox", "status": "ready"},
    )
    trace = TraceContext(
        trace_id="1" * 32,
        span_id="2" * 16,
        correlation_id=context.correlation_id,
        causation_id="outbox-entry-001",
    )
    assert trace_recorder.record(
        span_name="provider.authorize",
        trace=trace,
        context=context,
        started_at=NOW - timedelta(seconds=1),
        status=TraceStatus.OK,
        attributes={"payload": b"raw-fiscal-payload", "status": "accepted"},
    )
    alert = alert_evaluator.unknown_provider_outcome(
        context=context,
        jurisdiction=SP,
        outcome_reference="outcome-ref-001",
    )

    assert alert is not None
    assert event_sink.events[0].attributes["payload"] == "[REDACTED]"
    assert event_sink.events[0].attributes["credential"] == "[REDACTED]"
    assert event_sink.events[0].attributes["payload_sha256"] == "a" * 64
    assert metric_sink.points[0].labels["host_namespace"] == context.host_namespace
    assert metric_sink.points[0].labels["tenant_id"] == context.tenant_id
    assert trace_sink.spans[0].attributes["payload"] == "[REDACTED]"
    assert trace_sink.spans[0].trace.correlation_id == context.correlation_id
    assert alert.context == context
    assert alert.attributes["outcome_reference"] == "outcome-ref-001"
    assert "payload" not in alert.attributes


def test_all_telemetry_boundaries_fail_open_without_changing_execution() -> None:
    context = _context()
    event_service = StructuredObservabilityService(sink=_FailingEventSink(), clock=_Clock())
    metric_recorder = MetricRecorder(sink=_FailingMetricSink(), clock=_Clock())
    trace_recorder = TraceRecorder(sink=_FailingTraceSink(), clock=_Clock())
    alert_registry = AlertRegistry(sink=_FailingAlertSink(), clock=_Clock())
    alert_evaluator = OperationalAlertEvaluator(registry=alert_registry, clock=_Clock())

    assert event_service.emit(
        event_name="application.synthetic",
        severity=ObservabilitySeverity.INFO,
        category=ObservabilityCategory.APPLICATION,
        context=context,
    ) is False
    assert metric_recorder.record(
        definition=QUEUE_DEPTH,
        context=context,
        value=1,
        labels={"queue": "provider-outbox"},
    ) is False
    trace = TraceContext(
        trace_id="3" * 32,
        span_id="4" * 16,
        correlation_id=context.correlation_id,
    )
    assert trace_recorder.record(
        span_name="application.synthetic",
        trace=trace,
        context=context,
        started_at=NOW,
    ) is False
    assert alert_evaluator.queue_backlog(
        context=context,
        queue="provider-outbox",
        depth=10,
        threshold=1,
    ) is None


def test_cross_host_tenant_and_provider_partitions_remain_distinct() -> None:
    metric_sink = InMemoryMetricSink()
    metric_recorder = MetricRecorder(sink=metric_sink, clock=_Clock())
    alert_sink = InMemoryAlertSink()
    alert_registry = AlertRegistry(sink=alert_sink, clock=_Clock())
    evaluator = OperationalAlertEvaluator(registry=alert_registry, clock=_Clock())

    contexts = (
        _context(host="fm.kordena", tenant="tenant-a", provider="provider-a", correlation="c-a"),
        _context(host="fm.iron", tenant="tenant-a", provider="provider-a", correlation="c-b"),
        _context(host="fm.kordena", tenant="tenant-b", provider="provider-b", correlation="c-c"),
    )
    for context in contexts:
        assert metric_recorder.record(
            definition=QUEUE_DEPTH,
            context=context,
            value=1,
            labels={"queue": "provider-outbox"},
        )
        assert evaluator.unknown_provider_outcome(
            context=context,
            jurisdiction=SP,
            outcome_reference="shared-outcome-reference",
        ) is not None

    assert metric_recorder.series_count(QUEUE_DEPTH.name) == 3
    metric_partitions = {
        (
            point.labels["host_namespace"],
            point.labels["tenant_id"],
            point.labels["provider_id"],
        )
        for point in metric_sink.points
    }
    assert metric_partitions == {
        ("fm.kordena", "tenant-a", "provider-a"),
        ("fm.iron", "tenant-a", "provider-a"),
        ("fm.kordena", "tenant-b", "provider-b"),
    }
    assert len({alert.deduplication_key for alert in alert_sink.alerts}) == 3


def test_trace_carrier_can_be_rehydrated_for_restart_and_replay() -> None:
    original = TraceContext(
        trace_id="5" * 32,
        span_id="6" * 16,
        correlation_id="corr-replay-001",
        causation_id="outbox-entry-777",
    )

    carrier = TracePropagation.to_carrier(original)
    rehydrated = TracePropagation.from_carrier(dict(carrier))
    child = rehydrated.child(span_id="7" * 16, causation_id="provider-attempt-001")

    assert rehydrated == original
    assert child.trace_id == original.trace_id
    assert child.parent_span_id == original.span_id
    assert child.correlation_id == original.correlation_id
    assert child.causation_id == "provider-attempt-001"
    assert set(TracePropagation.to_carrier(rehydrated)) == {
        "x-fm-trace-id",
        "x-fm-span-id",
        "x-fm-correlation-id",
        "x-fm-causation-id",
    }


def test_regulatory_approval_cannot_mutate_readiness_authority() -> None:
    rule = JurisdictionCapabilityRule(
        rule_id="sp-nfe-hml-v1",
        version=1,
        state_code="SP",
        document_kind=FiscalDocumentKind.NFE,
        environment=FiscalEnvironment.HOMOLOGATION,
        capability_level=FiscalCapabilityLevel.HOMOLOGATION_READY,
        validation_mode=TechnicalValidationMode.STRICT_REJECTION,
        effective_from=NOW - timedelta(days=1),
        source_normative="synthetic certified baseline",
        capabilities=frozenset({FiscalActionCapability.ISSUE, FiscalActionCapability.QUERY}),
    )
    readiness = CapabilityReadinessService(JurisdictionCapabilityMatrix((rule,)))
    before = readiness.query(
        jurisdiction=SP,
        document_kind=FiscalDocumentKind.NFE,
        environment=FiscalEnvironment.HOMOLOGATION,
        instant=NOW,
    )

    watcher = RegulatoryWatcherService(clock=_Clock())
    watcher.observe(
        observation_id="obs-001",
        source_reference="synthetic://regulatory/source/001",
        source_sha256="b" * 64,
        jurisdiction=SP,
        subject="nfe.rule.change",
        summary="Synthetic normative observation for closure certification.",
        published_at=NOW - timedelta(hours=1),
        effective_from=NOW + timedelta(days=30),
    )
    watcher.triage("obs-001")
    proposal = watcher.propose(
        proposal_id="proposal-001",
        observation_ids=("obs-001",),
        jurisdiction=SP,
        subject="nfe.rule.change",
        summary="Synthetic governed proposal that must remain non executable.",
        required_tests=("test-contract", "test-readiness"),
        document_kind=FiscalDocumentKind.NFE,
        current_rule_version=1,
    )
    reviewed, _ = watcher.review(
        proposal_id=proposal.proposal_id,
        reviewer_id="human-reviewer-001",
        decision=RegulatoryReviewDecisionKind.APPROVE,
        tests_evidence_sha256="c" * 64,
        reason_code="review-approved",
    )

    after = readiness.query(
        jurisdiction=SP,
        document_kind=FiscalDocumentKind.NFE,
        environment=FiscalEnvironment.HOMOLOGATION,
        instant=NOW,
    )
    assert proposal.executable is False
    assert reviewed.executable is False
    assert before == after
    assert before.capability_version == after.capability_version
    assert not hasattr(watcher, "apply")
    assert not hasattr(watcher, "promote")


def test_structural_contract_has_no_raw_secret_or_payload_fields() -> None:
    forbidden = {
        "payload",
        "payload_bytes",
        "secret",
        "secret_value",
        "credential",
        "credential_bytes",
        "certificate_bytes",
        "private_key",
        "pfx",
        "xml",
        "body",
    }
    telemetry_types = (
        StructuredObservabilityEvent,
        MetricPoint,
        TraceSpan,
        ComplianceOperationalAlert,
    )

    for telemetry_type in telemetry_types:
        assert forbidden.isdisjoint({field.name for field in fields(telemetry_type)})

    root = Path(__file__).resolve().parents[2]
    domain_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (root / "src" / "kordena_fiscal" / "domain").rglob("*.py")
    )
    watcher_text = (
        root / "src" / "kordena_fiscal" / "compliance" / "regulatory_watcher.py"
    ).read_text(encoding="utf-8")
    assert "kordena_fiscal.observability" not in domain_text
    assert "CapabilityReadinessService" not in watcher_text
    assert "JurisdictionCapabilityMatrix" not in watcher_text
