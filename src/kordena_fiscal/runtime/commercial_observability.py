"""Low-cardinality commercial telemetry for the NFCore acquisition chain."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from kordena_fiscal.runtime.observability import MetricsRegistry, StructuredLogger


class CommercialTelemetryEvent(StrEnum):
    ACQUISITION = "acquisition"
    SALE_EVENT = "sale_event"
    CLAIM = "claim"
    PROVISIONING = "provisioning"
    ACTIVATION = "activation"
    BILLING_TRANSITION = "billing_transition"
    PROVIDER_DRIFT = "provider_drift"
    BACKLOG = "backlog"
    FAILURE = "failure"


class CommercialTelemetryOutcome(StrEnum):
    SUCCEEDED = "succeeded"
    REPLAY = "replay"
    REJECTED = "rejected"
    RETRY = "retry"
    DRIFT = "drift"
    PENDING = "pending"
    FAILED = "failed"


@dataclass(slots=True)
class CommercialTelemetry:
    """Emit only bounded operational facts; never PII/provider payloads."""

    metrics: MetricsRegistry
    logger: StructuredLogger

    def record(
        self,
        event: CommercialTelemetryEvent,
        outcome: CommercialTelemetryOutcome,
        *,
        count: int = 1,
        reason_code: str | None = None,
    ) -> None:
        if not isinstance(event, CommercialTelemetryEvent):
            raise ValueError("event must be CommercialTelemetryEvent")
        if not isinstance(outcome, CommercialTelemetryOutcome):
            raise ValueError("outcome must be CommercialTelemetryOutcome")
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            raise ValueError("count must be a non-negative integer")

        self.metrics.increment(
            "nfcore_commercial_events_total",
            count,
            operation=event.value,
            outcome=outcome.value,
        )
        fields: dict[str, object] = {
            "operation": event.value,
            "outcome": outcome.value,
            "count": count,
        }
        if reason_code is not None:
            normalized = reason_code.strip().lower()
            allowed = "abcdefghijklmnopqrstuvwxyz0123456789._-"
            if (
                not normalized
                or len(normalized) > 96
                or any(character not in allowed for character in normalized)
            ):
                raise ValueError("reason_code must be a bounded safe token")
            fields["reason_code"] = normalized
        self.logger.emit("INFO", "commercial_chain_event", **fields)


__all__ = [
    "CommercialTelemetry",
    "CommercialTelemetryEvent",
    "CommercialTelemetryOutcome",
]
