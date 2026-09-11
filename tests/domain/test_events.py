from datetime import UTC, datetime

import pytest

from kordena_fiscal.domain import (
    ExecutionScope,
    FiscalDomainEvent,
    FiscalEnvironment,
    FiscalValidationError,
    SourceReference,
)


def _scope() -> ExecutionScope:
    return ExecutionScope(
        tenant_id="tenant-a",
        unit_id="unit-1",
        environment=FiscalEnvironment.HOMOLOGATION,
        correlation_id="corr-123",
    )


def test_fiscal_domain_event_is_immutable_and_timezone_aware() -> None:
    event = FiscalDomainEvent(
        event_id="evt-1",
        event_type="fiscal.document.requested",
        aggregate_id="doc-1",
        source=SourceReference("sale", "order-42"),
        scope=_scope(),
        occurred_at=datetime(2026, 9, 10, 21, 0, tzinfo=UTC),
    )

    assert event.schema_version == 1
    assert event.source.canonical_tuple == ("sale", "order-42")
    assert event.scope.partition_key == (
        "tenant-a",
        "unit-1",
        FiscalEnvironment.HOMOLOGATION,
    )


def test_fiscal_domain_event_rejects_naive_timestamp() -> None:
    with pytest.raises(FiscalValidationError, match="timezone-aware"):
        FiscalDomainEvent(
            event_id="evt-1",
            event_type="fiscal.document.requested",
            aggregate_id="doc-1",
            source=SourceReference("sale", "order-42"),
            scope=_scope(),
            occurred_at=datetime(2026, 9, 10, 21, 0),
        )


def test_fiscal_domain_event_rejects_invalid_schema_version() -> None:
    with pytest.raises(FiscalValidationError, match="schema_version"):
        FiscalDomainEvent(
            event_id="evt-1",
            event_type="fiscal.document.requested",
            aggregate_id="doc-1",
            source=SourceReference("sale", "order-42"),
            scope=_scope(),
            occurred_at=datetime(2026, 9, 10, 21, 0, tzinfo=UTC),
            schema_version=0,
        )
