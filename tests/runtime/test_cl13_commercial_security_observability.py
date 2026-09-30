from __future__ import annotations

import json

import pytest

from kordena_fiscal.runtime.commercial_observability import (
    CommercialTelemetry,
    CommercialTelemetryEvent,
    CommercialTelemetryOutcome,
)
from kordena_fiscal.runtime.observability import MetricsRegistry, StructuredLogger, redact


def test_commercial_pii_is_redacted_by_key() -> None:
    source = {
        "buyer_email": "owner@example.com",
        "legal_name": "ACME LTDA",
        "external_customer_id": "customer-123",
        "safe": "visible",
    }

    redacted = redact(source)
    rendered = json.dumps(redacted)

    assert "owner@example.com" not in rendered
    assert "ACME LTDA" not in rendered
    assert "customer-123" not in rendered
    assert redacted["safe"] == "visible"


def test_commercial_telemetry_uses_bounded_low_cardinality_dimensions() -> None:
    output: list[str] = []
    metrics = MetricsRegistry()
    telemetry = CommercialTelemetry(
        metrics=metrics,
        logger=StructuredLogger(
            service="nfcore-commercial",
            environment="test",
            sink=output.append,
        ),
    )

    telemetry.record(
        CommercialTelemetryEvent.PROVISIONING,
        CommercialTelemetryOutcome.SUCCEEDED,
        reason_code="owner_created",
    )
    telemetry.record(
        CommercialTelemetryEvent.PROVIDER_DRIFT,
        CommercialTelemetryOutcome.DRIFT,
        count=2,
        reason_code="subscription_mismatch",
    )

    points = [
        sample
        for sample in metrics.snapshot()
        if sample.name == "nfcore_commercial_events_total"
    ]
    assert len(points) == 2
    assert {
        dict(point.labels)["operation"] for point in points
    } == {"provisioning", "provider_drift"}
    assert all("tenant_id" not in dict(point.labels) for point in points)

    rendered = "\n".join(output)
    assert "commercial_chain_event" in rendered
    assert "subscription_mismatch" in rendered


def test_commercial_telemetry_rejects_free_form_reason_and_invalid_count() -> None:
    telemetry = CommercialTelemetry(
        metrics=MetricsRegistry(),
        logger=StructuredLogger(
            service="nfcore-commercial",
            environment="test",
            sink=lambda _line: None,
        ),
    )

    with pytest.raises(ValueError, match="reason_code"):
        telemetry.record(
            CommercialTelemetryEvent.FAILURE,
            CommercialTelemetryOutcome.FAILED,
            reason_code="email=owner@example.com",
        )

    with pytest.raises(ValueError, match="non-negative"):
        telemetry.record(
            CommercialTelemetryEvent.BACKLOG,
            CommercialTelemetryOutcome.PENDING,
            count=-1,
        )
