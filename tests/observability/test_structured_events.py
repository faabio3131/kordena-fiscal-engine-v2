from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Mapping

import pytest

from kordena_fiscal.domain import ExecutionScope, FiscalDocumentKind, FiscalEnvironment
from kordena_fiscal.observability import (
    InMemoryStructuredEventSink,
    ObservabilityCategory,
    ObservabilityContext,
    ObservabilitySeverity,
    StructuredObservabilityEvent,
    StructuredObservabilityService,
    sanitize_observability_attributes,
    sanitize_observability_value,
)

NOW = datetime(2026, 9, 13, 15, 0, tzinfo=UTC)


class _Clock:
    def now(self) -> datetime:
        return NOW


class _FailingSink:
    def publish(self, event: StructuredObservabilityEvent) -> None:
        raise RuntimeError("synthetic sink unavailable")


class _ExplosiveRepr:
    def __repr__(self) -> str:
        raise AssertionError("repr must never be called by sanitizer")


def _scope() -> ExecutionScope:
    return ExecutionScope(
        host_namespace="fm.kordena",
        tenant_id="tenant-observability",
        unit_id="unit-observability",
        environment=FiscalEnvironment.HOMOLOGATION,
        correlation_id="corr-observability-001",
    )


def _context() -> ObservabilityContext:
    return ObservabilityContext(
        scope=_scope(),
        document_kind=FiscalDocumentKind.NFE,
        provider_id="synthetic-sp",
        operation="authorize",
    )


def test_emits_structured_scope_without_payload_data() -> None:
    sink = InMemoryStructuredEventSink()
    service = StructuredObservabilityService(sink=sink, clock=_Clock())

    emitted = service.emit(
        event_name="provider.authorize.completed",
        severity=ObservabilitySeverity.INFO,
        category=ObservabilityCategory.PROVIDER,
        context=_context(),
        message="provider request completed",
        attributes={
            "status": "accepted",
            "provider_request_id": "req-synthetic-001",
            "payload_sha256": "a" * 64,
        },
    )

    assert emitted is True
    assert len(sink.events) == 1
    event = sink.events[0]
    assert event.event_name == "provider.authorize.completed"
    assert event.occurred_at == NOW
    assert event.context.host_namespace == "fm.kordena"
    assert event.context.tenant_id == "tenant-observability"
    assert event.context.unit_id == "unit-observability"
    assert event.context.environment is FiscalEnvironment.HOMOLOGATION
    assert event.context.correlation_id == "corr-observability-001"
    assert event.context.document_kind is FiscalDocumentKind.NFE
    assert event.context.provider_id == "synthetic-sp"
    assert event.context.operation == "authorize"
    assert event.attributes["status"] == "accepted"
    assert event.attributes["payload_sha256"] == "a" * 64


def test_sensitive_keys_are_redacted_recursively_but_references_and_hashes_survive() -> None:
    attributes = sanitize_observability_attributes(
        {
            "password": "never-store",
            "provider_credentials": "never-store",
            "credential_reference_id": "ref:provider/credential",
            "certificate_reference_id": "ref:certificate/001",
            "payload_sha256": "b" * 64,
            "nested": {
                "authorization": "Bearer never-store",
                "safe_code": "135",
            },
        }
    )

    assert attributes["password"] == "[REDACTED]"
    assert attributes["provider_credentials"] == "[REDACTED]"
    assert attributes["credential_reference_id"] == "ref:provider/credential"
    assert attributes["certificate_reference_id"] == "ref:certificate/001"
    assert attributes["payload_sha256"] == "b" * 64
    nested = attributes["nested"]
    assert isinstance(nested, Mapping)
    assert nested["authorization"] == "[REDACTED]"
    assert nested["safe_code"] == "135"


def test_bytes_and_unknown_objects_are_fail_closed_without_repr() -> None:
    assert sanitize_observability_value(b"raw-secret") == "[REDACTED]"
    assert sanitize_observability_value(bytearray(b"raw-secret")) == "[REDACTED]"
    assert sanitize_observability_value(memoryview(b"raw-secret")) == "[REDACTED]"
    assert sanitize_observability_value(_ExplosiveRepr()) == "[REDACTED]"


def test_sensitive_free_form_message_is_redacted() -> None:
    sink = InMemoryStructuredEventSink()
    service = StructuredObservabilityService(sink=sink, clock=_Clock())

    assert service.emit(
        event_name="provider.authentication.failed",
        severity=ObservabilitySeverity.ERROR,
        category=ObservabilityCategory.SECURITY,
        context=_context(),
        message="Bearer top-secret-token",
    )
    assert sink.events[0].message == "[REDACTED]"


def test_xml_like_message_is_redacted() -> None:
    sink = InMemoryStructuredEventSink()
    service = StructuredObservabilityService(sink=sink, clock=_Clock())

    assert service.emit(
        event_name="document.validation.failed",
        severity=ObservabilitySeverity.WARNING,
        category=ObservabilityCategory.APPLICATION,
        context=_context(),
        message="<?xml version='1.0'?><NFe>synthetic</NFe>",
    )
    assert sink.events[0].message == "[REDACTED]"


def test_long_safe_text_is_bounded() -> None:
    sanitized = sanitize_observability_value("x" * 1500)
    assert isinstance(sanitized, str)
    assert len(sanitized) < 1100
    assert sanitized.endswith("…[TRUNCATED]")


def test_collection_size_is_bounded() -> None:
    sanitized = sanitize_observability_value(list(range(100)))
    assert isinstance(sanitized, tuple)
    assert len(sanitized) == 65
    assert sanitized[-1] == "…[TRUNCATED]"


def test_sink_failure_is_best_effort_and_does_not_escape_to_fiscal_execution() -> None:
    service = StructuredObservabilityService(sink=_FailingSink(), clock=_Clock())

    emitted = service.emit(
        event_name="provider.authorize.completed",
        severity=ObservabilitySeverity.INFO,
        category=ObservabilityCategory.PROVIDER,
        context=_context(),
        attributes={"status": "accepted"},
    )

    assert emitted is False


def test_direct_event_requires_aware_timestamp() -> None:
    with pytest.raises(Exception, match="timezone-aware"):
        StructuredObservabilityEvent(
            event_name="application.invalid",
            severity=ObservabilitySeverity.ERROR,
            category=ObservabilityCategory.APPLICATION,
            occurred_at=datetime(2026, 9, 13, 15, 0),
            context=_context(),
        )


def test_domain_does_not_depend_on_observability_package() -> None:
    root = Path(__file__).resolve().parents[2]
    domain = root / "src" / "kordena_fiscal" / "domain"
    domain_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in domain.rglob("*.py")
    )
    assert "kordena_fiscal.observability" not in domain_text
