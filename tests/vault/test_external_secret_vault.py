from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from kordena_fiscal.control_plane import SecretReference, SecretReferenceKind
from kordena_fiscal.domain import ExecutionScope, FiscalEnvironment
from kordena_fiscal.vault import (
    EphemeralCertificateMaterial,
    ExternalFiscalSecretVault,
    ExternalSecretBackendUnavailable,
    ExternalSecretPermissionDenied,
    ExternalSecretRecord,
    SecretAccessAuditEvent,
    SecretAuthorizationError,
    SecretMaterialTypeError,
    SecretResolutionContext,
    SecretUnavailableError,
    SecretUsagePurpose,
)

NOW = datetime(2026, 9, 16, 16, 20, tzinfo=UTC)
REFERENCE_ID = "ref:fm-fiscal/tenant-cl03/unit-cl03/prod-certificate"


def _reference() -> SecretReference:
    return SecretReference(
        reference_id=REFERENCE_ID,
        kind=SecretReferenceKind.CERTIFICATE,
        tenant_id="tenant-cl03",
        unit_id="unit-cl03",
        environment=FiscalEnvironment.PRODUCTION,
    )


def _context(*, tenant_id: str = "tenant-cl03") -> SecretResolutionContext:
    return SecretResolutionContext(
        scope=ExecutionScope(
            host_namespace="nfcore",
            tenant_id=tenant_id,
            unit_id="unit-cl03",
            environment=FiscalEnvironment.PRODUCTION,
            correlation_id="corr-cl03",
        ),
        purpose=SecretUsagePurpose.DOCUMENT_SIGNING,
        kind=SecretReferenceKind.CERTIFICATE,
        workload_id="nfcore-runtime",
    )


class _Clock:
    def now(self) -> datetime:
        return NOW


class _Audit:
    def __init__(self) -> None:
        self.events: list[SecretAccessAuditEvent] = []

    def record(self, event: SecretAccessAuditEvent) -> None:
        self.events.append(event)


class _Client:
    def __init__(self, records: list[ExternalSecretRecord | None]) -> None:
        self.records = list(records)
        self.references: list[str] = []

    def fetch(self, reference_id: str) -> ExternalSecretRecord | None:
        self.references.append(reference_id)
        if not self.records:
            raise AssertionError("unexpected secret fetch")
        return self.records.pop(0)


class _DeniedClient:
    def fetch(self, reference_id: str) -> ExternalSecretRecord | None:
        del reference_id
        raise ExternalSecretPermissionDenied("provider detail must not escape")


class _UnavailableClient:
    def fetch(self, reference_id: str) -> ExternalSecretRecord | None:
        del reference_id
        raise ExternalSecretBackendUnavailable("endpoint detail must not escape")


def _record(*, version: str, material: bytes = b"SYNTHETIC-PKCS12") -> ExternalSecretRecord:
    return ExternalSecretRecord(
        reference_id=REFERENCE_ID,
        kind=SecretReferenceKind.CERTIFICATE,
        material=material,
        password=b"SYNTHETIC-PASSWORD",
        version_id=version,
        expires_at=NOW + timedelta(days=30),
    )


def test_external_vault_resolves_ephemeral_material_and_records_metadata_only() -> None:
    audit = _Audit()
    client = _Client([_record(version="v1")])
    vault = ExternalFiscalSecretVault(client=client, audit=audit, clock=_Clock())

    material = vault.resolve(_reference(), _context())

    assert isinstance(material, EphemeralCertificateMaterial)
    assert material.pkcs12_bytes == b"SYNTHETIC-PKCS12"
    assert client.references == [REFERENCE_ID]
    assert len(audit.events) == 1
    event = audit.events[0]
    assert event.outcome == "resolved"
    assert event.version_id == "v1"
    assert "SYNTHETIC-PKCS12" not in repr(event)
    assert "SYNTHETIC-PASSWORD" not in repr(event)
    assert "SYNTHETIC" not in repr(_record(version="v1"))


def test_rotation_is_visible_without_process_cache() -> None:
    client = _Client(
        [
            _record(version="v1", material=b"CERTIFICATE-V1"),
            _record(version="v2", material=b"CERTIFICATE-V2"),
        ]
    )
    audit = _Audit()
    vault = ExternalFiscalSecretVault(client=client, audit=audit, clock=_Clock())

    first = vault.resolve(_reference(), _context())
    second = vault.resolve(_reference(), _context())

    assert isinstance(first, EphemeralCertificateMaterial)
    assert isinstance(second, EphemeralCertificateMaterial)
    assert first.pkcs12_bytes == b"CERTIFICATE-V1"
    assert second.pkcs12_bytes == b"CERTIFICATE-V2"
    assert [event.version_id for event in audit.events] == ["v1", "v2"]
    assert client.references == [REFERENCE_ID, REFERENCE_ID]


def test_expired_missing_permission_and_backend_fail_closed_without_provider_detail() -> None:
    expired = ExternalSecretRecord(
        reference_id=REFERENCE_ID,
        kind=SecretReferenceKind.CERTIFICATE,
        material=b"EXPIRED-CERTIFICATE",
        expires_at=NOW,
    )
    audit = _Audit()
    vault = ExternalFiscalSecretVault(client=_Client([expired]), audit=audit, clock=_Clock())
    with pytest.raises(SecretUnavailableError, match="expired"):
        vault.resolve(_reference(), _context())
    assert audit.events[-1].outcome == "expired"

    missing_audit = _Audit()
    missing = ExternalFiscalSecretVault(
        client=_Client([None]), audit=missing_audit, clock=_Clock()
    )
    with pytest.raises(SecretUnavailableError, match="unavailable"):
        missing.resolve(_reference(), _context())
    assert missing_audit.events[-1].outcome == "missing"

    denied = ExternalFiscalSecretVault(client=_DeniedClient(), audit=_Audit(), clock=_Clock())
    with pytest.raises(SecretAuthorizationError) as denied_error:
        denied.resolve(_reference(), _context())
    assert "provider detail" not in str(denied_error.value)

    unavailable = ExternalFiscalSecretVault(
        client=_UnavailableClient(), audit=_Audit(), clock=_Clock()
    )
    with pytest.raises(SecretUnavailableError) as unavailable_error:
        unavailable.resolve(_reference(), _context())
    assert "endpoint detail" not in str(unavailable_error.value)


def test_external_vault_revalidates_exact_scope_even_when_used_directly() -> None:
    vault = ExternalFiscalSecretVault(
        client=_Client([_record(version="v1")]),
        audit=_Audit(),
        clock=_Clock(),
    )

    with pytest.raises(SecretAuthorizationError, match="tenant mismatch"):
        vault.resolve(_reference(), _context(tenant_id="other-tenant"))


def test_external_record_type_mismatch_and_invalid_password_metadata_fail_closed() -> None:
    mismatched = ExternalSecretRecord(
        reference_id=REFERENCE_ID,
        kind=SecretReferenceKind.CSC,
        material=b"CSC",
    )
    vault = ExternalFiscalSecretVault(
        client=_Client([mismatched]),
        audit=_Audit(),
        clock=_Clock(),
    )
    with pytest.raises(SecretMaterialTypeError, match="does not match"):
        vault.resolve(_reference(), _context())

    csc_reference = SecretReference(
        reference_id="ref:fm-fiscal/tenant-cl03/unit-cl03/provider-csc",
        kind=SecretReferenceKind.CSC,
        tenant_id="tenant-cl03",
        unit_id="unit-cl03",
        environment=FiscalEnvironment.PRODUCTION,
        provider_id="provider-a",
    )
    csc_context = SecretResolutionContext(
        scope=_context().scope,
        purpose=SecretUsagePurpose.CSC_AUTHENTICATION,
        kind=SecretReferenceKind.CSC,
        workload_id="nfcore-runtime",
        provider_id="provider-a",
    )
    invalid_csc = ExternalSecretRecord(
        reference_id=csc_reference.reference_id,
        kind=SecretReferenceKind.CSC,
        material=b"CSC",
        password=b"NOT-ALLOWED",
    )
    invalid = ExternalFiscalSecretVault(
        client=_Client([invalid_csc]),
        audit=_Audit(),
        clock=_Clock(),
    )
    with pytest.raises(SecretMaterialTypeError, match="certificate"):
        invalid.resolve(csc_reference, csc_context)
