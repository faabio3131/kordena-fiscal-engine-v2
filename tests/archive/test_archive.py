from dataclasses import replace
from datetime import UTC, datetime, timedelta
from threading import Thread

import pytest

from kordena_fiscal.archive import (
    ArchiveConflictError,
    ArchiveIntegrityError,
    FiscalArchiveEntry,
    FiscalArchiveKind,
    FiscalArchiveVerifier,
    InMemoryFiscalArchiveStore,
    RetentionPolicyMetadata,
)
from kordena_fiscal.domain import ExecutionScope, FiscalEnvironment, FiscalValidationError


def _instant() -> datetime:
    return datetime(2026, 9, 11, 4, 0, tzinfo=UTC)


def _scope(*, unit: str = "unit-a") -> ExecutionScope:
    return ExecutionScope(
        tenant_id="tenant-a",
        unit_id=unit,
        environment=FiscalEnvironment.HOMOLOGATION,
        correlation_id="corr-archive-1",
    )


def _retention() -> RetentionPolicyMetadata:
    return RetentionPolicyMetadata(
        policy_id="legal-retention-policy",
        policy_version=3,
        retain_until=_instant() + timedelta(days=3650),
        legal_basis_reference="POLICY-CONFIGURED-OUTSIDE-ENGINE",
    )


def _entry(
    *,
    scope: ExecutionScope | None = None,
    kind: FiscalArchiveKind = FiscalArchiveKind.AUTHORIZED_XML,
    content: bytes = b"<synthetic-authorized-xml />",
    previous_manifest_sha256: str | None = None,
) -> FiscalArchiveEntry:
    return FiscalArchiveEntry.build(
        scope=scope or _scope(),
        document_reference="nfce:synthetic:77",
        kind=kind,
        content=content,
        media_type="application/xml",
        archived_at=_instant(),
        retention=_retention(),
        previous_manifest_sha256=previous_manifest_sha256,
    )


def test_entry_identity_and_manifest_are_deterministic() -> None:
    first = _entry()
    second = _entry()
    verifier = FiscalArchiveVerifier()

    first_manifest = verifier.verify_entry(first)
    second_manifest = verifier.verify_entry(second)
    assert first.entry_id == second.entry_id
    assert first.content_sha256 == second.content_sha256
    assert first_manifest.manifest_sha256 == second_manifest.manifest_sha256


def test_store_is_append_only_and_exact_replay_is_safe() -> None:
    store = InMemoryFiscalArchiveStore()
    entry = _entry()

    assert store.append(entry) == entry
    assert store.append(entry) == entry
    assert store.get(entry.entry_id) == entry

    forged = replace(entry, media_type="application/octet-stream")
    with pytest.raises(ArchiveConflictError, match="other content"):
        store.append(forged)


def test_document_listing_is_isolated_by_scope() -> None:
    store = InMemoryFiscalArchiveStore()
    first = _entry()
    other = _entry(scope=_scope(unit="unit-b"), content=b"<other-unit />")
    store.append(first)
    store.append(other)

    assert store.list_for_document(_scope(), "nfce:synthetic:77") == (first,)
    assert store.list_for_document(_scope(unit="unit-b"), "nfce:synthetic:77") == (other,)


def test_manifest_chain_verifies_multiple_artifacts() -> None:
    verifier = FiscalArchiveVerifier()
    xml = _entry()
    first_manifest = verifier.verify_entry(xml)
    protocol = _entry(
        kind=FiscalArchiveKind.AUTHORIZATION_PROTOCOL,
        content=b"synthetic-protocol-77",
        previous_manifest_sha256=first_manifest.manifest_sha256,
    )
    second_manifest = verifier.verify_entry(protocol)
    event = _entry(
        kind=FiscalArchiveKind.FISCAL_EVENT,
        content=b"synthetic-event-cancel",
        previous_manifest_sha256=second_manifest.manifest_sha256,
    )

    manifests = verifier.verify_chain((xml, protocol, event))

    assert len(manifests) == 3
    assert manifests[-1].previous_manifest_sha256 == manifests[-2].manifest_sha256


def test_manifest_chain_rejects_reordering_or_missing_link() -> None:
    verifier = FiscalArchiveVerifier()
    first = _entry()
    second = _entry(
        kind=FiscalArchiveKind.PROVIDER_RESPONSE,
        content=b"provider-response",
        previous_manifest_sha256="f" * 64,
    )

    with pytest.raises(ArchiveIntegrityError, match="not contiguous"):
        verifier.verify_chain((first, second))


def test_entry_rejects_wrong_content_digest() -> None:
    entry = _entry()
    with pytest.raises(FiscalValidationError, match="does not match"):
        replace(entry, content_sha256="0" * 64)


def test_retention_is_metadata_not_a_hardcoded_legal_period() -> None:
    open_ended = RetentionPolicyMetadata(
        policy_id="external-legal-review",
        policy_version=1,
        retain_until=None,
    )
    entry = FiscalArchiveEntry.build(
        scope=_scope(),
        document_reference="nfce:synthetic:88",
        kind=FiscalArchiveKind.DANFE,
        content=b"synthetic-danfe",
        media_type="text/html",
        archived_at=_instant(),
        retention=open_ended,
    )

    assert entry.retention.retain_until is None


def test_concurrent_append_of_same_artifact_creates_one_identity() -> None:
    store = InMemoryFiscalArchiveStore()
    entry = _entry()
    results: list[str] = []

    def append() -> None:
        results.append(store.append(entry).entry_id)

    threads = [Thread(target=append) for _ in range(32)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(results) == 32
    assert set(results) == {entry.entry_id}
    assert store.list_for_document(_scope(), "nfce:synthetic:77") == (entry,)
