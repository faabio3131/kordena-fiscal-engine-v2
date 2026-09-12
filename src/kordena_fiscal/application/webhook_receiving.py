"""Signed webhook receiving boundary coupled transactionally to the durable inbox."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from kordena_fiscal.domain import ExecutionScope, FiscalEnvironment, FiscalValidationError
from kordena_fiscal.events import (
    FiscalInboxEntry,
    FiscalInboxService,
    FiscalInboxStatus,
)
from kordena_fiscal.persistence.ports import FiscalUnitOfWork, FiscalUnitOfWorkFactory
from kordena_fiscal.security import WebhookSecurity, WebhookSignature


class FiscalWebhookConsumer(Protocol):
    """Apply one inbound event using the receiver's local transaction boundary."""

    def process(self, entry: FiscalInboxEntry, uow: FiscalUnitOfWork) -> str | None: ...


@dataclass(frozen=True, slots=True)
class SignedWebhookReceiveResult:
    entry: FiscalInboxEntry
    replay: bool
    consumer_invoked: bool


class SignedWebhookInboxReceiver:
    """Verify first, then atomically deduplicate, consume and mark processed.

    Signature verification always precedes durable acceptance. A fresh message, or
    a replay that is still only RECEIVED, is processed inside the same Unit of Work
    that transitions the inbox to PROCESSED. A duplicate already terminal message
    is a deterministic no-op, preventing duplicate fiscal effect.
    """

    def __init__(
        self,
        *,
        security: WebhookSecurity,
        uow_factory: FiscalUnitOfWorkFactory,
        producer: str,
        consumer: FiscalWebhookConsumer,
    ) -> None:
        if not isinstance(security, WebhookSecurity):
            raise FiscalValidationError("security must be WebhookSecurity")
        normalized_producer = producer.strip().lower()
        if not normalized_producer or len(normalized_producer) > 128:
            raise FiscalValidationError("producer must contain 1..128 characters")
        self._security = security
        self._uow_factory = uow_factory
        self._producer = normalized_producer
        self._consumer = consumer

    def receive(
        self,
        *,
        body: bytes,
        signature_header: str,
        correlation_id: str,
        received_at: datetime,
    ) -> SignedWebhookReceiveResult:
        if not isinstance(body, bytes) or not body:
            raise FiscalValidationError("body must be non-empty bytes")
        signature = WebhookSignature.parse(signature_header)
        self._security.verify(body, signature, now=received_at)
        envelope = self._parse_envelope(body, correlation_id=correlation_id)

        with self._uow_factory() as uow:
            received = FiscalInboxService(uow.inbox).receive(
                scope=envelope.scope,
                producer=self._producer,
                event_id=envelope.event_id,
                event_type=envelope.event_type,
                payload=body,
                occurred_at=envelope.occurred_at,
                received_at=received_at,
                causation_id=envelope.causation_id,
                idempotency_key=envelope.idempotency_key,
            )
            current = received.entry
            if received.replay and current.status is not FiscalInboxStatus.RECEIVED:
                uow.commit()
                return SignedWebhookReceiveResult(
                    entry=current,
                    replay=True,
                    consumer_invoked=False,
                )

            processing = uow.inbox.begin_processing(
                current.entry_id,
                expected_version=current.version,
            )
            outcome_reference = self._consumer.process(processing, uow)
            processed = uow.inbox.mark_processed(
                processing.entry_id,
                expected_version=processing.version,
                processed_at=received_at,
                outcome_reference=outcome_reference,
            )
            uow.commit()
            return SignedWebhookReceiveResult(
                entry=processed,
                replay=received.replay,
                consumer_invoked=True,
            )

    @staticmethod
    def _parse_envelope(body: bytes, *, correlation_id: str) -> _WebhookEnvelope:
        correlation = correlation_id.strip()
        if not correlation or len(correlation) > 256:
            raise FiscalValidationError("correlation_id must contain 1..256 characters")
        try:
            raw = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise FiscalValidationError("webhook body must be valid UTF-8 JSON") from exc
        if not isinstance(raw, dict):
            raise FiscalValidationError("webhook event envelope must be a JSON object")
        if raw.get("contract_version") != "1.0.0":
            raise FiscalValidationError("unsupported webhook contract_version")
        payload_correlation = _required_text(raw, "correlation_id", 256)
        if payload_correlation != correlation:
            raise FiscalValidationError("webhook correlation header does not match payload")
        scope_raw = raw.get("scope")
        if not isinstance(scope_raw, dict):
            raise FiscalValidationError("webhook scope must be an object")
        try:
            environment = FiscalEnvironment(_required_text(scope_raw, "environment", 32))
        except ValueError as exc:
            raise FiscalValidationError("webhook scope environment is invalid") from exc
        scope = ExecutionScope(
            host_namespace=_required_text(scope_raw, "host_namespace", 64),
            tenant_id=_required_text(scope_raw, "tenant_id", 128),
            unit_id=_required_text(scope_raw, "unit_id", 128),
            environment=environment,
            correlation_id=payload_correlation,
        )
        occurred_at_raw = _required_text(raw, "occurred_at", 64)
        try:
            occurred_at = datetime.fromisoformat(occurred_at_raw.replace("Z", "+00:00"))
        except ValueError as exc:
            raise FiscalValidationError("webhook occurred_at must be ISO-8601") from exc
        if occurred_at.tzinfo is None or occurred_at.utcoffset() is None:
            raise FiscalValidationError("webhook occurred_at must be timezone-aware")
        return _WebhookEnvelope(
            scope=scope,
            event_id=_required_text(raw, "event_id", 256),
            event_type=_required_text(raw, "event_type", 128).lower(),
            occurred_at=occurred_at,
            causation_id=_optional_text(raw, "causation_id", 256),
            idempotency_key=_optional_text(raw, "idempotency_key", 256),
        )


@dataclass(frozen=True, slots=True)
class _WebhookEnvelope:
    scope: ExecutionScope
    event_id: str
    event_type: str
    occurred_at: datetime
    causation_id: str | None
    idempotency_key: str | None


def _required_text(raw: dict[str, object], field_name: str, max_length: int) -> str:
    value = raw.get(field_name)
    if not isinstance(value, str):
        raise FiscalValidationError(f"{field_name} must be a string")
    normalized = value.strip()
    if not normalized or len(normalized) > max_length:
        raise FiscalValidationError(f"{field_name} must contain 1..{max_length} characters")
    return normalized


def _optional_text(
    raw: dict[str, object],
    field_name: str,
    max_length: int,
) -> str | None:
    value = raw.get(field_name)
    if value is None:
        return None
    if not isinstance(value, str):
        raise FiscalValidationError(f"{field_name} must be string or null")
    normalized = value.strip()
    if not normalized or len(normalized) > max_length:
        raise FiscalValidationError(f"{field_name} must contain 1..{max_length} characters")
    return normalized
