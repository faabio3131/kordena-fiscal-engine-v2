from __future__ import annotations

import json
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from kordena_fiscal.application import BackgroundCycleResult
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
    samples = {sample.labels: sample.value for sample in metrics.snapshot() if sample.name == "nfcore_worker_jobs_total"}
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
