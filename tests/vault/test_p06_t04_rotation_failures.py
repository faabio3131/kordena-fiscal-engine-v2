"""NFV1-P06-T04: rotation/failure contracts with durable SQL; synthetic GSM only.

No cloud credentials, IAM, secret creation, staging access or real material.
A positive result here does not certify the real external provider.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock

import google_crc32c
import psycopg
import pytest
from google.api_core import exceptions
from google.cloud import secretmanager_v1

from kordena_fiscal.control_plane import SecretReference as FiscalReference
from kordena_fiscal.control_plane import SecretReferenceKind
from kordena_fiscal.domain import ExecutionScope, FiscalEnvironment
from kordena_fiscal.persistence.ports import PersistenceConflictError
from kordena_fiscal.persistence.postgres import PostgresFiscalDatabase
from kordena_fiscal.persistence.sqlite import SqliteFiscalDatabase
from kordena_fiscal.runtime.secret_manager import (
    SecretBindingAdministration,
    build_gsm_secret_composition,
)
from kordena_fiscal.security.human_identity import AuthenticatedHuman, HumanAccount, PortalRole
from kordena_fiscal.security.secret_binding import SecretBinding
from kordena_fiscal.security.secrets import (
    SecretBackendUnavailable,
    SecretReference,
    SecretResolutionError,
    SecretScope,
)
from kordena_fiscal.vault import SecretResolutionContext, SecretUsagePurpose
from kordena_fiscal.vault.contracts import SecretAuthorizationError, SecretUnavailableError
from kordena_fiscal.vault.external import (
    ExternalFiscalSecretVault,
    ExternalSecretPermissionDenied,
)
from kordena_fiscal.vault.google_secret_manager import (
    DurableGsmReader,
    GoogleFiscalSecretClient,
    GoogleSdkSecretAccess,
    GsmPayload,
    encode_gsm_envelope,
)

NOW = datetime(2026, 10, 10, 12, tzinfo=UTC)
SECRET = b"synthetic-rotation-only-unique-value"
KINDS = ("signature", "certificate", "csc", "credentials")
PURPOSES = {
    "signature": "webhook-signing",
    "certificate": "document-signing",
    "csc": "csc-authentication",
    "credentials": "provider-authentication",
}


@pytest.fixture(params=("sqlite", "postgres"))
def database(request, tmp_path):
    if request.param == "sqlite":
        db = SqliteFiscalDatabase(tmp_path / "rotation-synthetic.db")
    else:
        dsn = os.environ.get("NFCORE_TEST_POSTGRES_DSN")
        if not dsn:
            pytest.skip("NFCORE_TEST_POSTGRES_DSN required for PostgreSQL CI")
        with psycopg.connect(dsn, autocommit=True) as connection:
            connection.execute("DROP SCHEMA public CASCADE")
            connection.execute("CREATE SCHEMA public")
        db = PostgresFiscalDatabase(dsn)
    db.initialize()
    try:
        yield db
    finally:
        if isinstance(db, PostgresFiscalDatabase):
            db.close()


def binding_for(kind):
    return SecretBinding(
        reference_id="sec_rotation_synthetic_01" if kind == "signature" else f"ref:rotation/{kind}",
        tenant_id="tenant-rotation-synthetic",
        unit_id="unit-rotation-synthetic",
        purpose=PURPOSES[kind],
        runtime_environment="staging",
        fiscal_environment=None if kind == "signature" else "homologation",
        provider_id=None if kind == "certificate" else "nfcore-test",
        workload_id="nfcore-worker" if kind == "signature" else "nfcore-api",
        kind=kind,
        canonical_version=3 if kind == "signature" else "fiscal-v3",
        resource=f"projects/nfcore-synthetic/secrets/rotation-{kind}",
        cloud_version="9",
        not_after=NOW + timedelta(hours=1),
    )


def put(database, binding, expected_revision=0):
    admin = HumanAccount(
        "synthetic-platform-admin",
        "synthetic@example.test",
        "synthetic-hash",
        binding.tenant_id,
        PortalRole.OWNER,
        platform_admin=True,
    )
    actor = AuthenticatedHuman(
        admin, "synthetic-session", "synthetic-csrf", NOW + timedelta(days=1)
    )
    SecretBindingAdministration(database, clock=lambda: NOW).put(
        actor=actor,
        binding=binding,
        expected_revision=expected_revision,
        correlation_id="synthetic-rotation-audit",
    )


class Access:
    def __init__(self, binding):
        self.calls = []
        self.callback = lambda: None
        self.error = None
        self.set_binding(binding)

    def set_binding(self, binding):
        data = encode_gsm_envelope(binding, SECRET)
        self.payload = GsmPayload(binding.version_name, data, google_crc32c.value(data))

    def access(self, name):
        self.calls.append(name)
        self.callback()
        if self.error is not None:
            raise self.error
        return self.payload


class Audit:
    def __init__(self):
        self.events = []

    def record(self, event):
        self.events.append(event)


class Clock:
    def now(self):
        return NOW


def compose(database, binding, access):
    audit = Audit()
    signature_events = []
    reader = DurableGsmReader(
        uow_factory=database,
        access=access,
        environment="staging",
        workload_id=binding.workload_id,
        allowed_resources=frozenset({binding.resource}),
        clock=lambda: NOW,
    )
    composition = build_gsm_secret_composition(
        reader=reader,
        signature_provider_id="nfcore-test",
        fiscal_audit=audit,
        signature_audit=signature_events.append,
        clock=lambda: NOW,
    )
    return (
        replace(
            composition,
            fiscal_vault=ExternalFiscalSecretVault(
                client=GoogleFiscalSecretClient(reader), audit=audit, clock=Clock()
            ),
        ),
        audit,
        signature_events,
    )


def resolve(composition, binding, *, signature_version=None):
    if binding.kind == "signature":
        version = binding.canonical_version if signature_version is None else signature_version
        return composition.signature_resolver.resolve(
            SecretReference(binding.reference_id, version),
            scope=SecretScope(binding.tenant_id, binding.unit_id, binding.purpose),
        )
    scope = ExecutionScope(
        binding.tenant_id,
        binding.unit_id,
        FiscalEnvironment.HOMOLOGATION,
        "synthetic-rotation",
        host_namespace="nfcore",
    )
    context = SecretResolutionContext(
        scope,
        SecretUsagePurpose(binding.purpose),
        SecretReferenceKind(binding.kind),
        binding.workload_id,
        binding.provider_id,
    )
    reference = FiscalReference(
        binding.reference_id,
        context.kind,
        scope.tenant_id,
        scope.unit_id,
        scope.environment,
        binding.provider_id,
    )
    return composition.fiscal_vault.resolve(reference, context)


def assert_material(material, kind):
    if kind == "signature":
        with material:
            assert material.reveal() == SECRET
        with pytest.raises(SecretResolutionError):
            material.reveal()
    else:
        field = {
            "certificate": "pkcs12_bytes",
            "csc": "code",
            "credentials": "credential_bytes",
        }[kind]
        assert getattr(material, field) == SECRET
    assert SECRET.decode() not in repr(material)


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize(
    "failure",
    (
        "missing",
        "revoked",
        "expired",
        "permission_denied",
        "backend_unavailable",
        "version_missing",
        "timeout",
    ),
)
def test_failure_matrix_fails_closed_without_secret_leaks(database, kind, failure):
    binding = binding_for(kind)
    stored = binding
    if failure == "revoked":
        stored = replace(binding, state="revoked")
    if failure == "expired":
        stored = replace(binding, not_after=NOW)
    if failure != "missing":
        put(database, stored)
    access = Access(binding)
    if failure == "permission_denied":
        access.error = ExternalSecretPermissionDenied("synthetic-provider-private-detail")
    elif failure == "backend_unavailable":
        access.error = RuntimeError("synthetic-provider-private-detail")
    elif failure == "version_missing":
        access.error = SecretResolutionError("synthetic-provider-private-detail")
    elif failure == "timeout":
        access.error = TimeoutError("synthetic-provider-private-detail")
    composition, audit, signature_events = compose(database, binding, access)
    error = (
        SecretResolutionError
        if kind == "signature"
        else (SecretAuthorizationError, SecretUnavailableError)
    )
    with pytest.raises(error) as exc:
        resolve(composition, binding)
    assert SECRET.decode() not in str(exc.value)
    assert "synthetic-provider-private-detail" not in str(exc.value)
    assert exc.value.__cause__ is None
    expected_calls = [] if failure in {"missing", "revoked", "expired"} else [binding.version_name]
    assert access.calls == expected_calls
    events = signature_events if kind == "signature" else audit.events
    assert len(events) == 1 and events[0].outcome != "resolved"
    assert SECRET.decode() not in json.dumps([asdict(event) for event in events], default=str)
    with database() as uow:
        assert uow.secret_bindings.get(binding.reference_id) == (
            None if failure == "missing" else stored
        )


@pytest.mark.parametrize("kind", KINDS)
def test_rotation_switches_pinned_version_and_rejects_stale_payload(database, kind):
    binding = binding_for(kind)
    put(database, binding)
    access = Access(binding)
    composition, audit, signature_events = compose(database, binding, access)
    assert_material(resolve(composition, binding), kind)
    rotated = replace(
        binding,
        revision=2,
        cloud_version="10",
        canonical_version=4 if kind == "signature" else "fiscal-v4",
    )
    put(database, rotated, expected_revision=1)
    # A stale pinned provider payload must never be served as a current secret.
    with pytest.raises(SecretResolutionError if kind == "signature" else SecretAuthorizationError):
        resolve(composition, rotated)
    if kind == "signature":
        calls = len(access.calls)
        with pytest.raises(SecretResolutionError):
            resolve(composition, rotated, signature_version=3)
        assert len(access.calls) == calls  # canonical version rejection before provider I/O
    access.set_binding(rotated)
    assert_material(resolve(composition, rotated), kind)
    assert access.calls == [
        binding.version_name,
        rotated.version_name,
        rotated.version_name,
    ]
    events = signature_events if kind == "signature" else audit.events
    assert [event.outcome for event in events] == [
        "resolved", "denied" if kind == "signature" else "permission_denied",
        * (["denied"] if kind == "signature" else []),
        "resolved",
    ]
    with database() as uow:
        assert uow.secret_bindings.get(binding.reference_id) == rotated
        assert len(uow.control_plane.list_audit()) == 2
    assert SECRET.decode() not in json.dumps([asdict(event) for event in events], default=str)


@pytest.mark.parametrize("kind", KINDS)
def test_rotation_or_revocation_during_provider_read_denies_in_flight_result(database, kind):
    binding = binding_for(kind)
    put(database, binding)
    access = Access(binding)
    composition, audit, signature_events = compose(database, binding, access)
    changed = replace(binding, revision=2, state="revoked")
    access.callback = lambda: put(database, changed, expected_revision=1)
    with pytest.raises(SecretResolutionError if kind == "signature" else SecretAuthorizationError):
        resolve(composition, binding)
    assert access.calls == [binding.version_name]
    events = signature_events if kind == "signature" else audit.events
    assert len(events) == 1 and events[0].outcome != "resolved"
    with database() as uow:
        assert uow.secret_bindings.get(binding.reference_id) == changed
        assert len(uow.control_plane.list_audit()) == 2


@pytest.mark.parametrize("kind", KINDS)
def test_revision_conflict_cannot_override_rotated_binding(database, kind):
    binding = binding_for(kind)
    put(database, binding)
    rotated = replace(binding, revision=2, cloud_version="10")
    put(database, rotated, expected_revision=1)
    with pytest.raises(PersistenceConflictError):
        put(database, replace(binding, revision=2, state="revoked"), expected_revision=1)
    with database() as uow:
        assert uow.secret_bindings.get(binding.reference_id) == rotated
        assert len(uow.control_plane.list_audit()) == 2


@pytest.mark.parametrize(
    "sdk_error,expected",
    [
        (
            exceptions.PermissionDenied("synthetic-private-sdk-detail"),
            ExternalSecretPermissionDenied,
        ),
        (exceptions.NotFound("synthetic-private-sdk-detail"), SecretResolutionError),
        (exceptions.ServiceUnavailable("synthetic-private-sdk-detail"), SecretBackendUnavailable),
        (exceptions.DeadlineExceeded("synthetic-private-sdk-detail"), SecretBackendUnavailable),
        (exceptions.FailedPrecondition("synthetic-private-sdk-detail"), SecretBackendUnavailable),
    ],
)
def test_sdk_failures_are_sanitized_and_use_bounded_pinned_access(sdk_error, expected):
    from kordena_fiscal.vault.external import ExternalSecretBackendUnavailable

    client = Mock(spec=secretmanager_v1.SecretManagerServiceClient)
    client.access_secret_version.side_effect = sdk_error
    reader = GoogleSdkSecretAccess(client, timeout_seconds=3)
    expected_type = (
        ExternalSecretBackendUnavailable if expected is SecretBackendUnavailable else expected
    )
    with pytest.raises(expected_type) as exc:
        reader.access(binding_for("signature").version_name)
    assert "synthetic-private-sdk-detail" not in str(exc.value)
    assert exc.value.__cause__ is None
    client.access_secret_version.assert_called_once_with(
        request={"name": binding_for("signature").version_name},
        retry=None,
        timeout=3,
    )
