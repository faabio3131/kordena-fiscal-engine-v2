from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from kordena_fiscal.application import BackgroundCycleResult
from kordena_fiscal.application.webhook_delivery import (
    WebhookDeliveryRequest,
    WebhookDeliveryResponse,
    WebhookDestination,
)
from kordena_fiscal.runtime.api import create_runtime_app
from kordena_fiscal.runtime.config import RuntimeSettings
from kordena_fiscal.runtime.observability import (
    MetricsRegistry,
    SafeTracer,
    StructuredLogger,
    TraceContext,
    TraceRecord,
    WorkerObservability,
    redact,
)
from kordena_fiscal.runtime.worker_composition import _TracedWebhookTransport

SECRET = "never-expose-this-secret"
NOW = datetime(2026, 9, 14, 23, 30, tzinfo=UTC)


def _settings() -> RuntimeSettings:
    return RuntimeSettings.from_mapping(
        {
            "NFCORE_ENVIRONMENT": "test",
            "NFCORE_PERSISTENCE_BACKEND": "sqlite",
            "NFCORE_SECRET_BACKEND": "memory",
            "NFCORE_REQUIRE_HTTPS": "false",
        }
    )


def test_recursive_redaction_covers_headers_tokens_certs_and_bytes() -> None:
    source = {
        "Authorization": f"Bearer {SECRET}",
        "nested": {
            "password": SECRET,
            "safe": "ok",
            "certificate_pem": "-----BEGIN CERTIFICATE-----\nabc",
        },
        "blob": b"raw-private-material",
    }
    result = redact(source)
    text = json.dumps(result)
    assert SECRET not in text
    assert "raw-private-material" not in text
    assert result["nested"]["safe"] == "ok"


def test_structured_logger_never_emits_secret_material() -> None:
    output: list[str] = []
    logger = StructuredLogger(service="nfcore-test", environment="test", sink=output.append)
    logger.emit(
        "INFO",
        "security_event",
        correlation_id="corr-1",
        password=SECRET,
        authorization=f"Bearer {SECRET}",
        payload={"token": SECRET, "safe": "visible"},
    )
    assert len(output) == 1
    assert SECRET not in output[0]
    decoded = json.loads(output[0])
    assert decoded["password"] == "<redacted>"
    assert decoded["payload"]["safe"] == "visible"


def test_metrics_reject_high_cardinality_labels() -> None:
    metrics = MetricsRegistry()
    try:
        metrics.increment("bad_metric", tenant_id="tenant-a")
    except ValueError as exc:
        assert "high-cardinality" in str(exc)
    else:
        raise AssertionError("tenant_id metric label unexpectedly accepted")


def test_safe_tracer_redacts_and_observability_failure_does_not_break_execution() -> None:
    records: list[TraceRecord] = []

    class Sink:
        def record(self, trace: TraceRecord) -> None:
            records.append(trace)

    tracer = SafeTracer(Sink())
    tracer.record(
        operation="issue",
        context=TraceContext("trace-1", "corr-1", "cause-1"),
        started_at=NOW,
        elapsed_seconds=0.2,
        outcome="ok",
        attributes={"token": SECRET, "provider": "test-provider"},
    )
    assert records[0].attributes["token"] == "<redacted>"
    assert records[0].context.correlation_id == "corr-1"
    assert records[0].context.causation_id == "cause-1"

    class ExplodingSink:
        def record(self, trace: TraceRecord) -> None:
            del trace
            raise RuntimeError(SECRET)

    SafeTracer(ExplodingSink()).record(
        operation="query",
        context=TraceContext("trace-2", "corr-2"),
        started_at=NOW,
        elapsed_seconds=0.1,
        outcome="ok",
    )


def test_worker_observer_records_cycle_and_dead_letter_metrics_without_secrets() -> None:
    metrics = MetricsRegistry()
    output: list[str] = []
    observer = WorkerObservability(
        metrics=metrics,
        logger=StructuredLogger(service="nfcore-worker", environment="test", sink=output.append),
    )
    observer.cycle_completed(
        BackgroundCycleResult(
            claimed=3,
            succeeded=1,
            retry_wait=1,
            dead_letter=1,
            elapsed_seconds=0.5,
        )
    )
    samples = {
        sample.labels: sample.value
        for sample in metrics.snapshot()
        if sample.name == "nfcore_worker_jobs_total"
    }
    assert (("outcome", "dead_letter"),) in samples
    assert samples[(("outcome", "dead_letter"),)] == 1.0
    assert output and SECRET not in output[0]


def test_runtime_http_observability_propagates_correlation_and_exposes_safe_metrics() -> None:
    metrics = MetricsRegistry()
    logs: list[str] = []
    app = create_runtime_app(
        _settings(),
        metrics=metrics,
        logger=StructuredLogger(service="nfcore-api", environment="test", sink=logs.append),
    )
    with TestClient(app) as client:
        response = client.get(
            "/health/live",
            headers={
                "X-Correlation-Id": "corr-http-1",
                "Authorization": f"Bearer {SECRET}",
            },
        )
        assert response.status_code == 200
        assert response.headers["X-Correlation-Id"] == "corr-http-1"
        metrics_response = client.get("/internal/metrics")
        assert metrics_response.status_code == 200
        body = metrics_response.text
    assert SECRET not in "\n".join(logs)
    assert SECRET not in body
    assert any("corr-http-1" in entry for entry in logs)


def test_health_payload_never_contains_database_url_or_secret_profile_material() -> None:
    app = create_runtime_app(_settings())
    with TestClient(app) as client:
        live = client.get("/health/live")
        ready = client.get("/health/ready")
    payload = live.text + ready.text
    assert "DATABASE_URL" not in payload
    assert SECRET not in payload


def test_p09_http_tracing_uses_existing_runtime_sink_and_correlation() -> None:
    records: list[TraceRecord] = []

    class Sink:
        def record(self, trace: TraceRecord) -> None:
            records.append(trace)

    app = create_runtime_app(_settings(), tracer=SafeTracer(Sink()))
    with TestClient(app) as client:
        response = client.get(
            "/health/live",
            headers={"X-Correlation-Id": "p09-api-correlation",
                     "Authorization": f"Bearer {SECRET}"},
        )
    assert response.status_code == 200
    assert response.headers["X-Correlation-Id"] == "p09-api-correlation"
    assert len(records) == 1
    trace = records[0]
    assert trace.operation == "http.request"
    assert trace.context.correlation_id == "p09-api-correlation"
    assert len(trace.context.trace_id) == 32
    assert trace.outcome == "success"
    assert trace.attributes == {"method": "GET", "status_class": "2xx"}
    assert SECRET not in repr(records)
    assert "health/live" not in repr(records)


def test_p09_http_tracing_sink_failure_never_breaks_health() -> None:
    class FailingSink:
        def record(self, trace: TraceRecord) -> None:
            del trace
            raise RuntimeError(SECRET)

    app = create_runtime_app(_settings(), tracer=SafeTracer(FailingSink()))
    with TestClient(app) as client:
        assert client.get("/health/live").status_code == 200


@pytest.mark.parametrize("status_code", [302, 503])
def test_p09_canonical_webhook_transport_emits_safe_outcomes(status_code: int) -> None:
    records: list[TraceRecord] = []

    class Sink:
        def record(self, trace: TraceRecord) -> None:
            records.append(trace)

    class FakeTransport:
        def deliver(self, request: WebhookDeliveryRequest) -> WebhookDeliveryResponse:
            assert request.body == SECRET.encode()
            return WebhookDeliveryResponse(status_code=status_code, error_detail=SECRET)

    request = WebhookDeliveryRequest(
        destination=WebhookDestination("synthetic-destination", "https://example.org/hook"),
        body=SECRET.encode(),
        headers=(("Content-Type", "application/json"),),
        outbox_entry_id="outbox-synthetic-1",
        attempt_count=1,
    )
    traced = _TracedWebhookTransport(FakeTransport(), SafeTracer(Sink()))
    response = traced.deliver(request)
    assert response.status_code == status_code and response.error_detail == SECRET
    assert len(records) == 1
    assert records[0].operation == "external.webhook"
    assert records[0].outcome == "error"
    assert records[0].attributes == {"status_class": f"{status_code // 100}xx"}
    assert records[0].context.causation_id == "outbox-synthetic-1"
    assert SECRET not in repr(records)
    assert "example.org" not in repr(records)


def test_p09_webhook_transport_preserves_exception_and_observes_failure() -> None:
    records: list[TraceRecord] = []

    class Sink:
        def record(self, trace: TraceRecord) -> None:
            records.append(trace)

    class FailingTransport:
        def deliver(self, request: WebhookDeliveryRequest) -> WebhookDeliveryResponse:
            del request
            raise RuntimeError(SECRET)

    request = WebhookDeliveryRequest(
        destination=WebhookDestination("synthetic-destination", "https://example.org/hook"),
        body=b"synthetic",
        headers=(("Content-Type", "application/json"),),
        outbox_entry_id="outbox-synthetic-2",
        attempt_count=1,
    )
    with pytest.raises(RuntimeError, match=SECRET):
        _TracedWebhookTransport(FailingTransport(), SafeTracer(Sink())).deliver(request)
    assert len(records) == 1 and records[0].outcome == "error"
    assert SECRET not in repr(records)


def test_p09_untrusted_correlation_header_does_not_escape_into_trace() -> None:
    records: list[TraceRecord] = []

    class Sink:
        def record(self, trace: TraceRecord) -> None:
            records.append(trace)

    app = create_runtime_app(
        _settings(),
        tracer=SafeTracer(Sink()),
        logger=StructuredLogger(service="nfcore-api", environment="test", sink=lambda _: None),
    )
    with TestClient(app) as client:
        response = client.get(
            "/health/live",
            headers={"X-Correlation-Id": f"Bearer {SECRET}",
                     "X-Causation-Id": f"Bearer {SECRET}"},
        )
    assert response.status_code == 200
    assert len(records) == 1
    assert records[0].context.causation_id is None
    assert len(records[0].context.correlation_id) == 32
    assert SECRET not in repr(records)


def test_p09_webhook_trace_does_not_replace_canonical_response_validation() -> None:
    records: list[TraceRecord] = []
    malformed = object()

    class Sink:
        def record(self, trace: TraceRecord) -> None:
            records.append(trace)

    class MalformedTransport:
        def deliver(self, request: WebhookDeliveryRequest) -> object:
            del request
            return malformed

    request = WebhookDeliveryRequest(
        destination=WebhookDestination("synthetic-destination", "https://example.org/hook"),
        body=b"synthetic",
        headers=(("Content-Type", "application/json"),),
        outbox_entry_id="outbox-synthetic-malformed",
        attempt_count=1,
    )
    response = _TracedWebhookTransport(MalformedTransport(), SafeTracer(Sink())).deliver(
        request
    )
    assert response is malformed
    assert len(records) == 1 and records[0].outcome == "error"
    assert records[0].attributes == {}
