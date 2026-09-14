"""Operational and compliance alert contracts for V2-13."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Protocol

from kordena_fiscal.domain import BrazilianJurisdiction, FiscalValidationError

from .events import (
    ObservabilityClock,
    ObservabilityContext,
    SystemObservabilityClock,
    sanitize_observability_attributes,
)

_MESSAGE_CODE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
_DIMENSION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")


class AlertKind(StrEnum):
    CERTIFICATE_EXPIRY = "certificate-expiry"
    CERTIFICATE_UNAVAILABLE = "certificate-unavailable"
    QUEUE_BACKLOG = "queue-backlog"
    DEAD_LETTER = "dead-letter"
    REJECTION_RATE = "rejection-rate"
    SEQUENCE_GAP = "sequence-gap"
    CONTINGENCY_PROLONGED = "contingency-prolonged"
    UNKNOWN_PROVIDER_OUTCOME = "unknown-provider-outcome"


class AlertSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertSink(Protocol):
    def publish(self, alert: ComplianceOperationalAlert) -> None: ...


def _safe_dimension(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not _DIMENSION.fullmatch(normalized):
        raise FiscalValidationError(f"{field_name} must be a bounded safe token")
    return normalized


def _jurisdiction_token(jurisdiction: BrazilianJurisdiction | None) -> str:
    if jurisdiction is None:
        return "none"
    municipality = jurisdiction.municipality_ibge_code or "none"
    return f"{jurisdiction.state_code}:{municipality}"


def _dedup_key(
    *,
    kind: AlertKind,
    context: ObservabilityContext,
    jurisdiction: BrazilianJurisdiction | None,
    dimension: str,
) -> str:
    parts = (
        kind.value,
        context.host_namespace,
        context.tenant_id,
        context.unit_id,
        context.environment.value,
        context.document_kind.value if context.document_kind is not None else "none",
        context.operation or "none",
        context.provider_id or "none",
        _jurisdiction_token(jurisdiction),
        dimension,
    )
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class ComplianceOperationalAlert:
    kind: AlertKind
    severity: AlertSeverity
    context: ObservabilityContext
    detected_at: datetime
    deduplication_key: str
    message_code: str
    jurisdiction: BrazilianJurisdiction | None = None
    attributes: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.kind, AlertKind):
            raise FiscalValidationError("kind must be AlertKind")
        if not isinstance(self.severity, AlertSeverity):
            raise FiscalValidationError("severity must be AlertSeverity")
        if not isinstance(self.context, ObservabilityContext):
            raise FiscalValidationError("context must be ObservabilityContext")
        if self.detected_at.tzinfo is None or self.detected_at.utcoffset() is None:
            raise FiscalValidationError("detected_at must be timezone-aware")
        object.__setattr__(self, "detected_at", self.detected_at.astimezone(UTC))
        if not re.fullmatch(r"[0-9a-f]{64}", self.deduplication_key):
            raise FiscalValidationError("deduplication_key must be sha256 hex")
        message_code = self.message_code.strip().lower()
        if not _MESSAGE_CODE.fullmatch(message_code):
            raise FiscalValidationError("message_code must be a safe lowercase token")
        object.__setattr__(self, "message_code", message_code)
        if self.jurisdiction is not None and not isinstance(
            self.jurisdiction,
            BrazilianJurisdiction,
        ):
            raise FiscalValidationError("jurisdiction must be BrazilianJurisdiction")
        object.__setattr__(
            self,
            "attributes",
            sanitize_observability_attributes(self.attributes),
        )


@dataclass(slots=True)
class InMemoryAlertSink:
    _alerts: list[ComplianceOperationalAlert] = field(default_factory=list, repr=False)

    def publish(self, alert: ComplianceOperationalAlert) -> None:
        if not isinstance(alert, ComplianceOperationalAlert):
            raise FiscalValidationError("alert must be ComplianceOperationalAlert")
        self._alerts.append(alert)

    @property
    def alerts(self) -> tuple[ComplianceOperationalAlert, ...]:
        return tuple(self._alerts)


class AlertRegistry:
    """Best-effort active-alert deduplication without creating fiscal state."""

    def __init__(
        self,
        *,
        sink: AlertSink,
        clock: ObservabilityClock | None = None,
    ) -> None:
        self._sink = sink
        self._clock = clock or SystemObservabilityClock()
        self._active: set[str] = set()

    def emit(
        self,
        *,
        kind: AlertKind,
        severity: AlertSeverity,
        context: ObservabilityContext,
        message_code: str,
        jurisdiction: BrazilianJurisdiction | None = None,
        dimension: str = "default",
        attributes: Mapping[str, object] | None = None,
    ) -> ComplianceOperationalAlert | None:
        try:
            normalized_dimension = _safe_dimension(dimension, "dimension")
            key = _dedup_key(
                kind=kind,
                context=context,
                jurisdiction=jurisdiction,
                dimension=normalized_dimension,
            )
            if key in self._active:
                return None
            alert = ComplianceOperationalAlert(
                kind=kind,
                severity=severity,
                context=context,
                detected_at=self._clock.now(),
                deduplication_key=key,
                message_code=message_code,
                jurisdiction=jurisdiction,
                attributes=attributes or {},
            )
            self._sink.publish(alert)
            self._active.add(key)
            return alert
        except Exception:
            return None

    def resolve(self, deduplication_key: str) -> bool:
        if deduplication_key in self._active:
            self._active.remove(deduplication_key)
            return True
        return False

    def is_active(self, deduplication_key: str) -> bool:
        return deduplication_key in self._active


class OperationalAlertEvaluator:
    """Deterministic threshold evaluators that only emit operational signals."""

    def __init__(
        self,
        *,
        registry: AlertRegistry,
        clock: ObservabilityClock | None = None,
    ) -> None:
        self._registry = registry
        self._clock = clock or SystemObservabilityClock()

    def certificate_expiry(
        self,
        *,
        context: ObservabilityContext,
        expires_at: datetime,
        warning_window: timedelta = timedelta(days=30),
        critical_window: timedelta = timedelta(days=7),
        certificate_reference_id: str,
    ) -> ComplianceOperationalAlert | None:
        now = self._clock.now()
        if expires_at.tzinfo is None or expires_at.utcoffset() is None:
            return None
        remaining = expires_at.astimezone(UTC) - now.astimezone(UTC)
        if remaining > warning_window:
            return None
        severity = AlertSeverity.CRITICAL if remaining <= critical_window else AlertSeverity.WARNING
        return self._registry.emit(
            kind=AlertKind.CERTIFICATE_EXPIRY,
            severity=severity,
            context=context,
            message_code="certificate.expiry",
            dimension=_safe_dimension(certificate_reference_id, "certificate_reference_id"),
            attributes={
                "certificate_reference_id": certificate_reference_id,
                "expires_at": expires_at,
                "remaining_seconds": remaining.total_seconds(),
            },
        )

    def certificate_unavailable(
        self,
        *,
        context: ObservabilityContext,
        certificate_reference_id: str,
    ) -> ComplianceOperationalAlert | None:
        return self._registry.emit(
            kind=AlertKind.CERTIFICATE_UNAVAILABLE,
            severity=AlertSeverity.CRITICAL,
            context=context,
            message_code="certificate.unavailable",
            dimension=_safe_dimension(certificate_reference_id, "certificate_reference_id"),
            attributes={"certificate_reference_id": certificate_reference_id},
        )

    def queue_backlog(
        self,
        *,
        context: ObservabilityContext,
        queue: str,
        depth: int,
        threshold: int,
    ) -> ComplianceOperationalAlert | None:
        if threshold < 1 or depth < threshold:
            return None
        return self._registry.emit(
            kind=AlertKind.QUEUE_BACKLOG,
            severity=AlertSeverity.WARNING,
            context=context,
            message_code="queue.backlog",
            dimension=_safe_dimension(queue, "queue"),
            attributes={"queue": queue, "depth": depth, "threshold": threshold},
        )

    def dead_letter(
        self,
        *,
        context: ObservabilityContext,
        queue: str,
        count: int,
    ) -> ComplianceOperationalAlert | None:
        if count < 1:
            return None
        return self._registry.emit(
            kind=AlertKind.DEAD_LETTER,
            severity=AlertSeverity.CRITICAL,
            context=context,
            message_code="queue.dead_letter",
            dimension=_safe_dimension(queue, "queue"),
            attributes={"queue": queue, "count": count},
        )

    def rejection_rate(
        self,
        *,
        context: ObservabilityContext,
        jurisdiction: BrazilianJurisdiction,
        rejected: int,
        total: int,
        threshold: float,
    ) -> ComplianceOperationalAlert | None:
        if total <= 0 or rejected < 0 or rejected > total or not 0 <= threshold <= 1:
            return None
        rate = rejected / total
        if rate < threshold:
            return None
        return self._registry.emit(
            kind=AlertKind.REJECTION_RATE,
            severity=AlertSeverity.WARNING,
            context=context,
            message_code="fiscal.rejection_rate",
            jurisdiction=jurisdiction,
            dimension="rejection-rate",
            attributes={"rejected": rejected, "total": total, "rate": rate},
        )

    def sequence_gap(
        self,
        *,
        context: ObservabilityContext,
        jurisdiction: BrazilianJurisdiction,
        expected: int,
        observed: int,
    ) -> ComplianceOperationalAlert | None:
        if expected < 0 or observed <= expected:
            return None
        return self._registry.emit(
            kind=AlertKind.SEQUENCE_GAP,
            severity=AlertSeverity.CRITICAL,
            context=context,
            message_code="fiscal.sequence_gap",
            jurisdiction=jurisdiction,
            dimension="sequence-gap",
            attributes={"expected": expected, "observed": observed, "gap": observed - expected},
        )

    def contingency_prolonged(
        self,
        *,
        context: ObservabilityContext,
        jurisdiction: BrazilianJurisdiction,
        started_at: datetime,
        threshold: timedelta,
        mode: str,
    ) -> ComplianceOperationalAlert | None:
        if started_at.tzinfo is None or started_at.utcoffset() is None or threshold <= timedelta(0):
            return None
        elapsed = self._clock.now().astimezone(UTC) - started_at.astimezone(UTC)
        if elapsed < threshold:
            return None
        return self._registry.emit(
            kind=AlertKind.CONTINGENCY_PROLONGED,
            severity=AlertSeverity.CRITICAL,
            context=context,
            message_code="fiscal.contingency_prolonged",
            jurisdiction=jurisdiction,
            dimension=_safe_dimension(mode, "mode"),
            attributes={"contingency_mode": mode, "elapsed_seconds": elapsed.total_seconds()},
        )

    def unknown_provider_outcome(
        self,
        *,
        context: ObservabilityContext,
        jurisdiction: BrazilianJurisdiction,
        outcome_reference: str,
    ) -> ComplianceOperationalAlert | None:
        return self._registry.emit(
            kind=AlertKind.UNKNOWN_PROVIDER_OUTCOME,
            severity=AlertSeverity.CRITICAL,
            context=context,
            message_code="provider.unknown_outcome",
            jurisdiction=jurisdiction,
            dimension=_safe_dimension(outcome_reference, "outcome_reference"),
            attributes={"outcome_reference": outcome_reference, "requires_reconciliation": True},
        )
