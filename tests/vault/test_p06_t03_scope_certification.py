"""Scope certification through real persistence and canonical resolver boundaries.

Provider payloads are synthetic: this certifies local authority, not cloud IAM.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta

import google_crc32c
import psycopg
import pytest

from kordena_fiscal.control_plane import SecretReference as FiscalReference
from kordena_fiscal.control_plane import SecretReferenceKind
from kordena_fiscal.domain import ExecutionScope, FiscalEnvironment
from kordena_fiscal.persistence.postgres import PostgresFiscalDatabase
from kordena_fiscal.persistence.sqlite import SqliteFiscalDatabase
from kordena_fiscal.runtime.secret_manager import (
    SecretBindingAdministration,
    build_gsm_secret_composition,
)
from kordena_fiscal.security.human_identity import AuthenticatedHuman, HumanAccount, PortalRole
from kordena_fiscal.security.secret_binding import SecretBinding
from kordena_fiscal.security.secrets import SecretReference, SecretResolutionError, SecretScope
from kordena_fiscal.vault import SecretResolutionContext, SecretUsagePurpose
from kordena_fiscal.vault.contracts import SecretAuthorizationError
from kordena_fiscal.vault.external import ExternalFiscalSecretVault
from kordena_fiscal.vault.google_secret_manager import (
    DurableGsmReader,
    GoogleFiscalSecretClient,
    GsmPayload,
    encode_gsm_envelope,
)

NOW = datetime(2026, 10, 10, 12, tzinfo=UTC)
MATERIAL = b"synthetic-scope-certification-material-only"
KINDS = ("signature", "certificate", "csc", "credentials")
PURPOSE = {
    "signature": "webhook-signing",
    "certificate": "document-signing",
    "csc": "csc-authentication",
    "credentials": "provider-authentication",
}


@pytest.fixture(params=["sqlite", "postgres"])
def database(request, tmp_path):
    if request.param == "sqlite":
        db = SqliteFiscalDatabase(tmp_path / "scope-synthetic.db")
    else:
        dsn = os.environ.get("NFCORE_TEST_POSTGRES_DSN")
        if not dsn:
            pytest.skip("NFCORE_TEST_POSTGRES_DSN required for real PostgreSQL CI")
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
        reference_id="sec_scope_synthetic_01" if kind == "signature" else f"ref:scope/{kind}",
        tenant_id="scope-tenant",
        unit_id="scope-unit",
        purpose=PURPOSE[kind],
        runtime_environment="staging",
        fiscal_environment=None if kind == "signature" else "homologation",
        provider_id=None if kind == "certificate" else "scope-provider",
        workload_id="nfcore-worker" if kind == "signature" else "nfcore-api",
        kind=kind,
        canonical_version=3 if kind == "signature" else "fiscal-v3",
        resource=f"projects/nfcore-synthetic/secrets/scope-{kind}",
        cloud_version="9",
        not_after=NOW + timedelta(hours=1),
    )


def put(db, binding, expected_revision=0):
    account = HumanAccount(
        "scope-admin",
        "scope-admin@example.test",
        "synthetic-hash",
        "scope-tenant",
        PortalRole.OWNER,
        platform_admin=True,
    )
    actor = AuthenticatedHuman(
        account, "synthetic-session", "synthetic-csrf", NOW + timedelta(days=1)
    )
    SecretBindingAdministration(db, clock=lambda: NOW).put(
        actor=actor,
        binding=binding,
        expected_revision=expected_revision,
        correlation_id="scope-certification-synthetic",
    )


class SyntheticAccess:
    def __init__(self, binding):
        self.calls = []
        self.callback = lambda: None
        self.set_data(encode_gsm_envelope(binding, MATERIAL), binding.version_name)

    def set_data(self, data, name):
        self.payload = GsmPayload(name, data, google_crc32c.value(data))

    def access(self, name):
        self.calls.append(name)
        self.callback()
        return self.payload


class Audit:
    def __init__(self):
        self.events = []

    def record(self, event):
        self.events.append(event)


class Clock:
    def __init__(self, current):
        self.current = current

    def now(self):
        return self.current()


def composition(db, binding, access, *, now=None):
    audit = Audit()
    signature_events = []
    clock = now or (lambda: NOW)
    reader = DurableGsmReader(
        uow_factory=db,
        access=access,
        environment="staging",
        workload_id=binding.workload_id,
        allowed_resources=frozenset({binding.resource}),
        clock=clock,
    )
    result = build_gsm_secret_composition(
        reader=reader,
        signature_provider_id="scope-provider",
        fiscal_audit=audit,
        signature_audit=signature_events.append,
        clock=clock,
    )
    # The existing fiscal vault has its own clock port. Pin both boundaries so
    # certification never depends on when CI is executed.
    result = replace(
        result,
        fiscal_vault=ExternalFiscalSecretVault(
            client=GoogleFiscalSecretClient(reader), audit=audit, clock=Clock(clock)
        ),
    )
    return result, audit, signature_events


def resolve(comp, binding):
    if binding.kind == "signature":
        return comp.signature_resolver.resolve(
            SecretReference(binding.reference_id, binding.canonical_version),
            scope=SecretScope(binding.tenant_id, binding.unit_id, binding.purpose),
        )
    scope = ExecutionScope(
        binding.tenant_id,
        binding.unit_id,
        FiscalEnvironment(binding.fiscal_environment),
        "scope-certification",
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
    return comp.fiscal_vault.resolve(reference, context)


@pytest.mark.parametrize("kind", KINDS)
def test_exact_scope_resolves_and_audits_without_material(database, kind):
    binding = binding_for(kind)
    put(database, binding)
    access = SyntheticAccess(binding)
    comp, audit, signature_events = composition(database, binding, access)
    material = resolve(comp, binding)
    if kind == "signature":
        with material:
            assert material.reveal() == MATERIAL
        events = signature_events
    else:
        value = getattr(
            material,
            {"certificate": "pkcs12_bytes", "csc": "code", "credentials": "credential_bytes"}[kind],
        )
        assert value == MATERIAL
        events = audit.events
        assert events[0].version_id == "fiscal-v3"
    assert access.calls == [binding.version_name]
    assert [event.outcome for event in events] == ["resolved"]
    serialized = json.dumps([asdict(event) for event in events], default=str)
    assert MATERIAL.decode() not in serialized
    assert MATERIAL.decode() not in repr(material)
    with database() as uow:
        assert uow.secret_bindings.get(binding.reference_id) == binding
        assert len(uow.control_plane.list_audit()) == 1


@pytest.mark.parametrize("kind", ("certificate", "csc", "credentials"))
@pytest.mark.parametrize(
    "dimension", ("tenant", "unit", "fiscal-environment", "runtime", "workload")
)
def test_fiscal_binding_mismatch_denied_before_cloud_io(database, kind, dimension):
    binding = binding_for(kind)
    stored = {
        "tenant": replace(binding, tenant_id="other-tenant"),
        "unit": replace(binding, unit_id="other-unit"),
        "fiscal-environment": replace(binding, fiscal_environment="production"),
        "runtime": replace(binding, runtime_environment="production"),
        "workload": replace(binding, workload_id="other-workload"),
    }[dimension]
    put(database, stored)
    access = SyntheticAccess(stored)
    comp, audit, _ = composition(database, binding, access)
    with pytest.raises(SecretAuthorizationError):
        resolve(comp, binding)
    assert access.calls == []
    assert [event.outcome for event in audit.events] == ["permission_denied"]


@pytest.mark.parametrize("kind", ("csc", "credentials"))
def test_fiscal_provider_partition_denied_before_cloud_io(database, kind):
    binding = binding_for(kind)
    put(database, replace(binding, provider_id="other-provider"))
    access = SyntheticAccess(binding)
    comp, audit, _ = composition(database, binding, access)
    with pytest.raises(SecretAuthorizationError):
        resolve(comp, binding)
    assert access.calls == []
    assert audit.events[0].outcome == "permission_denied"


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize(
    "dimension",
    (
        "tenant_id",
        "unit_id",
        "purpose",
        "runtime_environment",
        "fiscal_environment",
        "provider_id",
        "workload_id",
        "kind",
        "canonical_version",
        "cloud_version",
        "not_after",
    ),
)
def test_tampered_envelope_cannot_cross_any_scope_dimension(database, kind, dimension):
    binding = binding_for(kind)
    put(database, binding)
    access = SyntheticAccess(binding)
    envelope = json.loads(access.payload.data)
    original = envelope["binding"][dimension]
    envelope["binding"][dimension] = "other-synthetic" if original != "other-synthetic" else None
    access.set_data(json.dumps(envelope).encode(), binding.version_name)
    comp, audit, signature_events = composition(database, binding, access)
    error = SecretResolutionError if kind == "signature" else SecretAuthorizationError
    with pytest.raises(error) as exc:
        resolve(comp, binding)
    assert access.calls == [binding.version_name]
    events = signature_events if kind == "signature" else audit.events
    assert len(events) == 1 and events[0].outcome != "resolved"
    assert MATERIAL.decode() not in str(exc.value)
    assert exc.value.__cause__ is None


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("moment", ("before", "exact", "during"))
def test_expiration_boundary_and_expiry_during_cloud_access(database, kind, moment):
    binding = binding_for(kind)
    put(database, binding)
    current = [binding.not_after - timedelta(microseconds=1)]
    if moment == "exact":
        current[0] = binding.not_after
    access = SyntheticAccess(binding)
    if moment == "during":
        access.callback = lambda: current.__setitem__(0, binding.not_after)
    comp, _, _ = composition(database, binding, access, now=lambda: current[0])
    if moment == "before":
        material = resolve(comp, binding)
        if kind == "signature":
            material.close()
        assert access.calls == [binding.version_name]
    else:
        error = SecretResolutionError if kind == "signature" else SecretAuthorizationError
        with pytest.raises(error):
            resolve(comp, binding)
        assert access.calls == ([] if moment == "exact" else [binding.version_name])


@pytest.mark.parametrize(
    "dimension,value",
    (
        ("tenant_id", "other-tenant"),
        ("unit_id", "other-unit"),
        ("purpose", "other-purpose"),
        ("runtime_environment", "production"),
        ("provider_id", "other-provider"),
        ("workload_id", "other-workload"),
    ),
)
def test_platform_admin_cannot_rebind_existing_signature_identity(database, dimension, value):
    binding = binding_for("signature")
    put(database, binding)
    with pytest.raises(SecretResolutionError, match="cannot change scope"):
        put(database, replace(binding, revision=2, **{dimension: value}), 1)
    with database() as uow:
        assert uow.secret_bindings.get(binding.reference_id) == binding
        assert len(uow.control_plane.list_audit()) == 1


@pytest.mark.parametrize("dimension", ("tenant", "unit", "environment", "provider", "kind"))
def test_reference_context_disagreement_rejected_by_vault_before_io(database, dimension):
    binding = binding_for("credentials")
    put(database, binding)
    access = SyntheticAccess(binding)
    comp, audit, _ = composition(database, binding, access)
    scope = ExecutionScope(
        binding.tenant_id,
        binding.unit_id,
        FiscalEnvironment.HOMOLOGATION,
        "synthetic",
        host_namespace="nfcore",
    )
    context = SecretResolutionContext(
        scope,
        SecretUsagePurpose.PROVIDER_AUTHENTICATION,
        SecretReferenceKind.CREDENTIALS,
        binding.workload_id,
        binding.provider_id,
    )
    reference = FiscalReference(
        binding.reference_id,
        context.kind,
        scope.tenant_id,
        scope.unit_id,
        scope.environment,
        context.provider_id,
    )
    changes = {
        "tenant": {"tenant_id": "other-tenant"},
        "unit": {"unit_id": "other-unit"},
        "environment": {"environment": FiscalEnvironment.PRODUCTION},
        "provider": {"provider_id": "other-provider"},
        "kind": {"kind": SecretReferenceKind.CSC},
    }[dimension]
    with pytest.raises(SecretAuthorizationError):
        comp.fiscal_vault.resolve(replace(reference, **changes), context)
    assert access.calls == []
    assert audit.events == []  # Boundary rejects before provider/audit access.


@pytest.mark.parametrize(
    "dimension,value",
    (
        ("tenant_id", "other-tenant"),
        ("unit_id", "other-unit"),
        ("runtime_environment", "production"),
        ("fiscal_environment", "production"),
        ("provider_id", "other-provider"),
        ("workload_id", "other-workload"),
    ),
)
def test_platform_admin_cannot_rebind_existing_fiscal_identity(database, dimension, value):
    binding = binding_for("credentials")
    put(database, binding)
    with pytest.raises(SecretResolutionError, match="cannot change scope"):
        put(database, replace(binding, revision=2, **{dimension: value}), 1)
    with database() as uow:
        assert uow.secret_bindings.get(binding.reference_id) == binding
        assert len(uow.control_plane.list_audit()) == 1


@pytest.mark.parametrize("kind", KINDS)
def test_unscoped_access_never_reads_provider(database, kind):
    from kordena_fiscal.vault.external import ExternalSecretPermissionDenied
    from kordena_fiscal.vault.google_secret_manager import (
        GoogleSignatureSecretBackend,
    )

    binding = binding_for(kind)
    put(database, binding)
    access = SyntheticAccess(binding)
    reader = DurableGsmReader(
        uow_factory=database,
        access=access,
        environment="staging",
        workload_id=binding.workload_id,
        allowed_resources=frozenset({binding.resource}),
        clock=lambda: NOW,
    )
    if kind == "signature":
        with pytest.raises(SecretResolutionError, match="explicit scope"):
            GoogleSignatureSecretBackend(reader, provider_id=binding.provider_id).resolve(
                SecretReference(binding.reference_id)
            )
    else:
        with pytest.raises(ExternalSecretPermissionDenied, match="explicit context"):
            GoogleFiscalSecretClient(reader).fetch(binding.reference_id)
    assert access.calls == []
