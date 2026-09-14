from __future__ import annotations

from datetime import UTC, datetime, timedelta

from kordena_fiscal.domain import (
    BrazilianJurisdiction,
    ExecutionScope,
    FiscalDocumentKind,
    FiscalEnvironment,
)
from kordena_fiscal.observability import (
    AlertKind,
    AlertRegistry,
    AlertSeverity,
    ComplianceOperationalAlert,
    InMemoryAlertSink,
    ObservabilityContext,
    OperationalAlertEvaluator,
)

NOW = datetime(2026, 9, 13, 17, 0, tzinfo=UTC)
SP = BrazilianJurisdiction("SP")


class _Clock:
    def now(self) -> datetime:
        return NOW


class _FailingAlertSink:
    def publish(self, alert: ComplianceOperationalAlert) -> None:
        raise RuntimeError("synthetic alert sink unavailable")


def _context(
    *,
    host: str = "fm.kordena",
    tenant: str = "tenant-alert",
    unit: str = "unit-alert",
    provider: str | None = "synthetic-sp",
) -> ObservabilityContext:
    return ObservabilityContext(
        scope=ExecutionScope(
            host_namespace=host,
            tenant_id=tenant,
            unit_id=unit,
            environment=FiscalEnvironment.HOMOLOGATION,
            correlation_id=f"corr-{host}-{tenant}-{unit}",
        ),
        document_kind=FiscalDocumentKind.NFE,
        provider_id=provider,
        operation="authorize",
    )


def _evaluator() -> tuple[InMemoryAlertSink, AlertRegistry, OperationalAlertEvaluator]:
    sink = InMemoryAlertSink()
    registry = AlertRegistry(sink=sink, clock=_Clock())
    return sink, registry, OperationalAlertEvaluator(registry=registry, clock=_Clock())


def test_certificate_expiry_warning_and_critical_windows() -> None:
    sink, _, evaluator = _evaluator()

    warning = evaluator.certificate_expiry(
        context=_context(),
        expires_at=NOW + timedelta(days=20),
        certificate_reference_id="cert-ref-001",
    )
    critical = evaluator.certificate_expiry(
        context=_context(unit="unit-critical"),
        expires_at=NOW + timedelta(days=3),
        certificate_reference_id="cert-ref-001",
    )

    assert warning is not None and warning.severity is AlertSeverity.WARNING
    assert critical is not None and critical.severity is AlertSeverity.CRITICAL
    assert len(sink.alerts) == 2
    assert warning.attributes["certificate_reference_id"] == "cert-ref-001"


def test_certificate_unavailable_is_critical_and_reference_only() -> None:
    sink, _, evaluator = _evaluator()

    alert = evaluator.certificate_unavailable(
        context=_context(),
        certificate_reference_id="cert-ref-002",
    )

    assert alert is not None
    assert alert.kind is AlertKind.CERTIFICATE_UNAVAILABLE
    assert alert.severity is AlertSeverity.CRITICAL
    assert alert.attributes == {"certificate_reference_id": "cert-ref-002"}
    assert len(sink.alerts) == 1


def test_queue_backlog_and_dead_letter_only_fire_when_threshold_met() -> None:
    sink, _, evaluator = _evaluator()

    assert evaluator.queue_backlog(
        context=_context(), queue="provider-outbox", depth=9, threshold=10
    ) is None
    backlog = evaluator.queue_backlog(
        context=_context(), queue="provider-outbox", depth=10, threshold=10
    )
    dead = evaluator.dead_letter(
        context=_context(unit="unit-dead"), queue="provider-outbox", count=2
    )

    assert backlog is not None and backlog.kind is AlertKind.QUEUE_BACKLOG
    assert dead is not None and dead.kind is AlertKind.DEAD_LETTER
    assert len(sink.alerts) == 2


def test_rejection_rate_and_sequence_gap_are_jurisdiction_scoped() -> None:
    sink, _, evaluator = _evaluator()

    rejection = evaluator.rejection_rate(
        context=_context(),
        jurisdiction=SP,
        rejected=12,
        total=100,
        threshold=0.1,
    )
    gap = evaluator.sequence_gap(
        context=_context(unit="unit-gap"),
        jurisdiction=SP,
        expected=100,
        observed=103,
    )

    assert rejection is not None and rejection.jurisdiction == SP
    assert rejection.attributes["rate"] == 0.12
    assert gap is not None and gap.attributes["gap"] == 3
    assert len(sink.alerts) == 2


def test_contingency_prolonged_requires_elapsed_threshold() -> None:
    sink, _, evaluator = _evaluator()

    assert evaluator.contingency_prolonged(
        context=_context(),
        jurisdiction=SP,
        started_at=NOW - timedelta(minutes=4),
        threshold=timedelta(minutes=5),
        mode="svc-an",
    ) is None
    alert = evaluator.contingency_prolonged(
        context=_context(),
        jurisdiction=SP,
        started_at=NOW - timedelta(minutes=6),
        threshold=timedelta(minutes=5),
        mode="svc-an",
    )

    assert alert is not None
    assert alert.kind is AlertKind.CONTINGENCY_PROLONGED
    assert alert.attributes["contingency_mode"] == "svc-an"
    assert len(sink.alerts) == 1


def test_unknown_provider_outcome_requires_reconciliation_without_payload() -> None:
    sink, _, evaluator = _evaluator()

    alert = evaluator.unknown_provider_outcome(
        context=_context(),
        jurisdiction=SP,
        outcome_reference="outcome-001",
    )

    assert alert is not None
    assert alert.kind is AlertKind.UNKNOWN_PROVIDER_OUTCOME
    assert alert.attributes["requires_reconciliation"] is True
    assert alert.attributes["outcome_reference"] == "outcome-001"
    assert "payload" not in alert.attributes
    assert len(sink.alerts) == 1


def test_active_alert_is_deduplicated_until_resolved() -> None:
    sink, registry, evaluator = _evaluator()

    first = evaluator.queue_backlog(
        context=_context(), queue="provider-outbox", depth=20, threshold=10
    )
    duplicate = evaluator.queue_backlog(
        context=_context(), queue="provider-outbox", depth=25, threshold=10
    )

    assert first is not None
    assert duplicate is None
    assert len(sink.alerts) == 1
    assert registry.is_active(first.deduplication_key)
    assert registry.resolve(first.deduplication_key)
    again = evaluator.queue_backlog(
        context=_context(), queue="provider-outbox", depth=25, threshold=10
    )
    assert again is not None
    assert len(sink.alerts) == 2


def test_deduplication_is_partitioned_by_host_tenant_unit_provider_and_jurisdiction() -> None:
    sink, _, evaluator = _evaluator()

    contexts = (
        _context(host="fm.kordena", tenant="tenant-a", unit="u1", provider="p1"),
        _context(host="fm.iron", tenant="tenant-a", unit="u1", provider="p1"),
        _context(host="fm.kordena", tenant="tenant-b", unit="u1", provider="p1"),
        _context(host="fm.kordena", tenant="tenant-a", unit="u2", provider="p2"),
    )
    alerts = [
        evaluator.unknown_provider_outcome(
            context=context,
            jurisdiction=SP,
            outcome_reference="outcome-shared",
        )
        for context in contexts
    ]

    assert all(alert is not None for alert in alerts)
    keys = {alert.deduplication_key for alert in alerts if alert is not None}
    assert len(keys) == 4
    assert len(sink.alerts) == 4


def test_alert_attributes_are_sanitized_fail_closed() -> None:
    sink = InMemoryAlertSink()
    registry = AlertRegistry(sink=sink, clock=_Clock())

    alert = registry.emit(
        kind=AlertKind.QUEUE_BACKLOG,
        severity=AlertSeverity.WARNING,
        context=_context(),
        message_code="queue.backlog",
        dimension="provider-outbox",
        attributes={
            "depth": 20,
            "payload": b"forbidden",
            "credential_reference_id": "credential-ref-1",
            "authorization": "Bearer forbidden",
        },
    )

    assert alert is not None
    assert alert.attributes["payload"] == "[REDACTED]"
    assert alert.attributes["credential_reference_id"] == "credential-ref-1"
    assert alert.attributes["authorization"] == "[REDACTED]"


def test_alert_sink_failure_does_not_mark_alert_active() -> None:
    registry = AlertRegistry(sink=_FailingAlertSink(), clock=_Clock())

    alert = registry.emit(
        kind=AlertKind.QUEUE_BACKLOG,
        severity=AlertSeverity.WARNING,
        context=_context(),
        message_code="queue.backlog",
        dimension="provider-outbox",
        attributes={"depth": 20},
    )

    assert alert is None
