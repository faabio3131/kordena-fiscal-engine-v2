from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest

from kordena_fiscal.security.secrets import (
    CallableProductionSecretBackend,
    InMemorySecretBackend,
    SecretAuditEvent,
    SecretBackendUnavailable,
    SecretReference,
    SecretResolutionError,
    SecretResolver,
    SecretScope,
    StoredSecret,
)

NOW = datetime(2026, 9, 14, 22, 30, tzinfo=UTC)
REF = "sec_0123456789abcdef"
SCOPE = SecretScope("tenant-a", "unit-a", "certificate.pfx")
VALUE = b"super-sensitive-material-never-log-this"


def _resolver(backend: InMemorySecretBackend, events: list[SecretAuditEvent]) -> SecretResolver:
    return SecretResolver(
        backend,
        environment="test",
        audit_sink=events.append,
        clock=lambda: NOW,
    )


def test_resolve_is_scoped_redacted_audited_and_zeroizable() -> None:
    backend = InMemorySecretBackend()
    reference = backend.put(reference_id=REF, scope=SCOPE, value=VALUE)
    events: list[SecretAuditEvent] = []
    resolver = _resolver(backend, events)

    material = resolver.resolve(reference, scope=SCOPE)
    assert material.reveal() == VALUE
    assert VALUE.decode() not in repr(material)
    material.close()
    with pytest.raises(SecretResolutionError, match="no longer available"):
        material.reveal()

    assert len(events) == 1
    assert events[0].outcome == "resolved"
    assert VALUE.decode() not in repr(events[0])


def test_rotation_keeps_versions_explicit_and_latest_moves_forward() -> None:
    backend = InMemorySecretBackend()
    v1 = backend.put(reference_id=REF, scope=SCOPE, value=b"first-version")
    v2 = backend.put(reference_id=REF, scope=SCOPE, value=b"second-version")
    resolver = _resolver(backend, [])

    with resolver.resolve(v1, scope=SCOPE) as first:
        assert first.reveal() == b"first-version"
    with resolver.resolve(v2, scope=SCOPE) as second:
        assert second.reveal() == b"second-version"
    with resolver.resolve(SecretReference(REF), scope=SCOPE) as latest:
        assert latest.reveal() == b"second-version"
    assert v1.version == 1
    assert v2.version == 2


def test_concurrent_rotation_and_resolution_remain_version_safe() -> None:
    backend = InMemorySecretBackend()

    def rotate(index: int) -> SecretReference:
        return backend.put(reference_id=REF, scope=SCOPE, value=f"value-{index}".encode())

    with ThreadPoolExecutor(max_workers=8) as executor:
        references = list(executor.map(rotate, range(1, 17)))

    versions = sorted(
        reference.version for reference in references if reference.version is not None
    )
    assert versions == list(range(1, 17))
    resolver = _resolver(backend, [])
    with resolver.resolve(SecretReference(REF), scope=SCOPE) as latest:
        assert latest.reveal().startswith(b"value-")


def test_tenant_unit_and_purpose_are_authority_not_browser_metadata() -> None:
    backend = InMemorySecretBackend()
    reference = backend.put(reference_id=REF, scope=SCOPE, value=VALUE)
    resolver = _resolver(backend, [])

    for scope in (
        SecretScope("tenant-b", "unit-a", "certificate.pfx"),
        SecretScope("tenant-a", "unit-b", "certificate.pfx"),
        SecretScope("tenant-a", "unit-a", "provider.token"),
    ):
        with pytest.raises(SecretResolutionError, match="not authorized"):
            resolver.resolve(reference, scope=scope)


def test_missing_revoked_and_expired_fail_closed_without_material_in_error() -> None:
    backend = InMemorySecretBackend()
    missing = SecretReference("sec_aaaaaaaaaaaaaaaa")
    resolver = _resolver(backend, [])
    with pytest.raises(SecretResolutionError) as missing_error:
        resolver.resolve(missing, scope=SCOPE)
    assert VALUE.decode() not in str(missing_error.value)

    revoked = backend.put(reference_id=REF, scope=SCOPE, value=VALUE)
    backend.revoke(revoked)
    with pytest.raises(SecretResolutionError, match="revoked") as revoked_error:
        resolver.resolve(revoked, scope=SCOPE)
    assert VALUE.decode() not in str(revoked_error.value)

    expired_ref = "sec_expired0123456789"
    expired = backend.put(
        reference_id=expired_ref,
        scope=SCOPE,
        value=VALUE,
        not_after=NOW - timedelta(seconds=1),
    )
    with pytest.raises(SecretResolutionError, match="expired") as expired_error:
        resolver.resolve(expired, scope=SCOPE)
    assert VALUE.decode() not in str(expired_error.value)


def test_reference_rejects_paths_urls_and_traversal() -> None:
    invalid = (
        "../secret",
        "../../etc/passwd",
        "secret://provider/path",
        "/absolute/secret",
        "sec_short",
        "sec_abcdefghijklmnop/child",
        "sec_abcdefghijklmnop?version=2",
    )
    for value in invalid:
        with pytest.raises(SecretResolutionError, match="invalid opaque"):
            SecretReference(value)


def test_staging_and_production_reject_development_backend() -> None:
    backend = InMemorySecretBackend()
    for environment in ("staging", "production"):
        with pytest.raises(SecretResolutionError, match="secure external"):
            SecretResolver(backend, environment=environment)


def test_vendor_neutral_production_adapter_resolves_without_choosing_cloud() -> None:
    stored = StoredSecret(
        reference=SecretReference(REF, 7),
        scope=SCOPE,
        value=VALUE,
    )
    backend = CallableProductionSecretBackend(lambda _reference: stored)
    resolver = SecretResolver(backend, environment="production", clock=lambda: NOW)

    with resolver.resolve(SecretReference(REF, 7), scope=SCOPE) as material:
        assert material.reveal() == VALUE
        assert VALUE.decode() not in repr(material)


def test_provider_failure_is_normalized_without_leaking_exception_payload() -> None:
    def explode(_reference: SecretReference) -> StoredSecret:
        raise RuntimeError(f"provider exploded with {VALUE.decode()}")

    backend = CallableProductionSecretBackend(explode)
    resolver = SecretResolver(backend, environment="production", clock=lambda: NOW)
    with pytest.raises(SecretBackendUnavailable) as error:
        resolver.resolve(SecretReference(REF), scope=SCOPE)
    assert str(error.value) == "secret backend is unavailable"
    assert VALUE.decode() not in str(error.value)


def test_audit_denial_contains_metadata_only() -> None:
    backend = InMemorySecretBackend()
    reference = backend.put(reference_id=REF, scope=SCOPE, value=VALUE)
    events: list[SecretAuditEvent] = []
    resolver = _resolver(backend, events)

    with pytest.raises(SecretResolutionError):
        resolver.resolve(reference, scope=SecretScope("tenant-other", "unit-a", "certificate.pfx"))

    assert len(events) == 1
    assert events[0].outcome == "denied"
    assert VALUE.decode() not in repr(events[0])
