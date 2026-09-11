from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest

from kordena_fiscal.archive import (
    FiscalArchiveEntry,
    FiscalArchiveKind,
    FiscalArchiveManifest,
    InMemoryFiscalArchiveStore,
    RetentionPolicyMetadata,
)
from kordena_fiscal.contingency import FiscalOutboxService, InMemoryFiscalOutboxStore
from kordena_fiscal.domain import (
    ElectronicInvoiceModel,
    ExecutionScope,
    FiscalDocumentKind,
    FiscalDomainEvent,
    FiscalEnvironment,
    Money,
    SourceReference,
)
from kordena_fiscal.lifecycle import FiscalDocumentState, build_issuance_key
from kordena_fiscal.numbering import FiscalSequenceManager, InMemoryFiscalSequenceStore
from kordena_fiscal.reconciliation import (
    FiscalReconciliationCandidate,
    FiscalReconciliationEngine,
    HostSettlementSnapshot,
    ReconciliationContractError,
)

_HOSTS = ("fm.kordena", "fm.iron", "fm.vendedor-ia", "fm.campaia")
_NOW = datetime(2026, 9, 11, 15, 0, tzinfo=UTC)


def _scope(host_namespace: str) -> ExecutionScope:
    return ExecutionScope(
        tenant_id="facc-shared",
        unit_id="funit-shared",
        environment=FiscalEnvironment.HOMOLOGATION,
        correlation_id=f"corr-{host_namespace}",
        host_namespace=host_namespace,
    )


def test_execution_identity_partition_separates_all_fm_products() -> None:
    scopes = tuple(_scope(host) for host in _HOSTS)

    assert len({scope.identity_partition_key for scope in scopes}) == len(_HOSTS)
    assert {scope.host_namespace for scope in scopes} == set(_HOSTS)
    assert all(
        scope.partition_key
        == ("facc-shared", "funit-shared", FiscalEnvironment.HOMOLOGATION)
        for scope in scopes
    )


def test_sequence_manager_keeps_same_local_ids_independent_per_host() -> None:
    manager = FiscalSequenceManager(InMemoryFiscalSequenceStore())

    reservations = tuple(
        manager.reserve(scope, model=ElectronicInvoiceModel.NFCE, series=1)
        for scope in (_scope(host) for host in _HOSTS)
    )

    assert [reservation.number for reservation in reservations] == [1, 1, 1, 1]
    assert len({reservation.key.canonical_material for reservation in reservations}) == 4
    assert len({reservation.reservation_token for reservation in reservations}) == 4


def test_idempotency_key_is_partitioned_by_host_namespace() -> None:
    source = SourceReference("subscription", "same-source-id")
    documents = tuple(
        SimpleNamespace(
            scope=_scope(host),
            source=source,
            document_kind=FiscalDocumentKind.NFCE,
        )
        for host in _HOSTS
    )

    keys = tuple(build_issuance_key(document) for document in documents)  # type: ignore[arg-type]

    assert len({key.value for key in keys}) == 4


def test_outbox_deduplication_identity_is_partitioned_by_host_namespace() -> None:
    store = InMemoryFiscalOutboxStore()
    service = FiscalOutboxService(store)

    results = tuple(
        service.enqueue(
            scope=_scope(host),
            operation="issue",
            deduplication_key="same-operation-key",
            payload=b'{"same":"payload"}',
            created_at=_NOW,
        )
        for host in _HOSTS
    )

    assert all(result.replay is False for result in results)
    assert len({result.entry.entry_id for result in results}) == 4


def test_archive_identity_and_audit_manifest_are_partitioned_by_host_namespace() -> None:
    retention = RetentionPolicyMetadata(policy_id="synthetic-policy", policy_version=1)
    store = InMemoryFiscalArchiveStore()
    entries = tuple(
        FiscalArchiveEntry.build(
            scope=_scope(host),
            document_reference="same-document-reference",
            kind=FiscalArchiveKind.AUTHORIZED_XML,
            content=b"<nfe>same-content</nfe>",
            media_type="application/xml",
            archived_at=_NOW,
            retention=retention,
        )
        for host in _HOSTS
    )

    for entry in entries:
        store.append(entry)

    manifests = tuple(FiscalArchiveManifest.from_entry(entry) for entry in entries)

    assert len({entry.entry_id for entry in entries}) == 4
    assert len({manifest.scope_partition for manifest in manifests}) == 4
    assert {manifest.scope_partition[0] for manifest in manifests} == set(_HOSTS)
    for entry in entries:
        assert store.list_for_document(entry.scope, entry.document_reference) == (entry,)


def test_domain_event_audit_metadata_retains_host_namespace() -> None:
    events = tuple(
        FiscalDomainEvent(
            event_id=f"event-{index}",
            event_type="fiscal.synthetic",
            aggregate_id="aggregate-shared",
            source=SourceReference("service", "same-source"),
            scope=_scope(host),
            occurred_at=_NOW,
        )
        for index, host in enumerate(_HOSTS, start=1)
    )

    assert {event.scope.host_namespace for event in events} == set(_HOSTS)
    assert len({event.scope.identity_partition_key for event in events}) == 4


def test_reconciliation_fails_closed_on_cross_host_spoofing() -> None:
    source = SourceReference("sale", "same-sale")
    host = HostSettlementSnapshot(
        scope=_scope("fm.kordena"),
        source=source,
        sale_amount=Money(Decimal("100.00")),
        payment_amount=Money(Decimal("100.00")),
        change_amount=Money.zero(),
        settled_at=_NOW,
    )
    spoofed_candidate = FiscalReconciliationCandidate(
        document_id="doc-iron",
        scope=_scope("fm.iron"),
        source=source,
        state=FiscalDocumentState.AUTHORIZED,
        net_amount=Money(Decimal("100.00")),
        payment_amount=Money(Decimal("100.00")),
        change_amount=Money.zero(),
    )

    with pytest.raises(ReconciliationContractError, match="identity scope"):
        FiscalReconciliationEngine().reconcile(host, (spoofed_candidate,))


def test_reconciliation_fingerprint_is_different_for_each_host() -> None:
    source = SourceReference("subscription", "same-operation")
    engine = FiscalReconciliationEngine()
    results = tuple(
        engine.reconcile(
            HostSettlementSnapshot(
                scope=_scope(host),
                source=source,
                sale_amount=Money(Decimal("10.00")),
                payment_amount=Money(Decimal("10.00")),
                change_amount=Money.zero(),
                settled_at=_NOW,
            ),
            (),
        )
        for host in _HOSTS
    )

    assert len({result.fingerprint for result in results}) == 4
