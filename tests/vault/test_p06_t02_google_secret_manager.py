from __future__ import annotations

import json
import os
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock

import google_crc32c
import psycopg
import pytest
from google.api_core import exceptions
from google.auth.credentials import AnonymousCredentials
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
    build_gsm_worker_webhook_dependencies,
)
from kordena_fiscal.security.human_identity import AuthenticatedHuman, HumanAccount, PortalRole
from kordena_fiscal.security.secret_binding import SecretBinding
from kordena_fiscal.security.secrets import SecretReference, SecretResolutionError, SecretScope
from kordena_fiscal.vault import SecretResolutionContext, SecretUsagePurpose
from kordena_fiscal.vault.external import (
    ExternalSecretBackendUnavailable,
    ExternalSecretPermissionDenied,
    NullSecretAccessAuditSink,
)
from kordena_fiscal.vault.google_secret_manager import (
    DurableGsmReader,
    GoogleSdkSecretAccess,
    GsmPayload,
    build_google_sdk_access,
    encode_gsm_envelope,
)

NOW = datetime(2026, 10, 9, tzinfo=UTC)
SCOPE = SecretScope("tenant-synthetic", "unit-synthetic", "webhook-signing")
BINDING = SecretBinding(
    "sec_synthetic_reference_01",
    SCOPE.tenant_id,
    SCOPE.unit_id,
    SCOPE.purpose,
    "staging",
    None,
    "nfcore",
    "nfcore-worker",
    "signature",
    3,
    "projects/nfcore-synthetic/secrets/signature-synthetic",
    "9",
    not_after=NOW + timedelta(days=1),
)
KEY = b"synthetic-test-only-material-0123456789"


@pytest.fixture(params=["sqlite", "postgres"])
def database(request, tmp_path):
    if request.param == "sqlite":
        database = SqliteFiscalDatabase(tmp_path / "synthetic.db")
    else:
        dsn = os.environ.get("NFCORE_TEST_POSTGRES_DSN")
        if not dsn:
            pytest.skip("NFCORE_TEST_POSTGRES_DSN required for real PostgreSQL CI")
        with psycopg.connect(dsn, autocommit=True) as conn:
            conn.execute("DROP SCHEMA public CASCADE")
            conn.execute("CREATE SCHEMA public")
        database = PostgresFiscalDatabase(dsn)
    database.initialize()
    try:
        yield database
    finally:
        if isinstance(database, PostgresFiscalDatabase):
            database.close()


def actor(*, admin=True, enabled=True):
    account = HumanAccount(
        "synthetic-admin",
        "admin@example.test",
        "synthetic-hash",
        "tenant-synthetic",
        PortalRole.OWNER,
        platform_admin=admin,
        enabled=enabled,
    )
    return AuthenticatedHuman(
        account, "session-synthetic", "synthetic-csrf", NOW + timedelta(days=1)
    )


def put(database, binding=BINDING, revision=0):
    SecretBindingAdministration(database, clock=lambda: NOW).put(
        actor=actor(),
        binding=binding,
        expected_revision=revision,
        correlation_id="synthetic-corr",
    )


class Access:
    def __init__(self, binding=BINDING):
        self.calls = []
        data = encode_gsm_envelope(binding, KEY)
        self.payload = GsmPayload(binding.version_name, data, google_crc32c.value(data))
        self.error = None
        self.callback = None

    def access(self, name):
        self.calls.append(name)
        if self.callback:
            self.callback()
        if self.error:
            raise self.error
        return self.payload


def compose(database, access, binding=BINDING, **kwargs):
    reader = DurableGsmReader(
        uow_factory=database,
        access=access,
        environment=kwargs.get("environment", "staging"),
        workload_id=kwargs.get("workload", binding.workload_id),
        allowed_resources=kwargs.get("resources", frozenset({binding.resource})),
        clock=lambda: NOW,
    )
    return build_gsm_secret_composition(
        reader=reader,
        signature_provider_id="nfcore",
        fiscal_audit=NullSecretAccessAuditSink(),
        signature_audit=lambda _e: None,
        clock=lambda: NOW,
    )


def test_signature_roundtrip_durable_no_material_cache(database):
    put(database)
    access = Access()
    resolver = compose(database, access).signature_resolver
    for _ in range(2):
        with resolver.resolve(SecretReference(BINDING.reference_id, 3), scope=SCOPE) as material:
            assert material.reveal() == KEY
            assert KEY.decode() not in repr(material)
        with pytest.raises(SecretResolutionError):
            material.reveal()
    assert access.calls == [BINDING.version_name] * 2
    with database() as uow:
        assert uow.secret_bindings.get(BINDING.reference_id) == BINDING
        assert len(uow.control_plane.list_audit()) == 1
    assert KEY.decode() not in json.dumps(BINDING.metadata())


@pytest.mark.parametrize(
    "scope",
    [
        replace(SCOPE, tenant_id="other"),
        replace(SCOPE, unit_id="other"),
        replace(SCOPE, unit_id=None),
        replace(SCOPE, purpose="other-signing"),
    ],
)
def test_scope_denied_before_provider_io(database, scope):
    put(database)
    access = Access()
    with pytest.raises(SecretResolutionError):
        compose(database, access).signature_resolver.resolve(
            SecretReference(BINDING.reference_id),
            scope=scope,
        )
    assert access.calls == []


@pytest.mark.parametrize(
    "variant",
    ["environment", "workload", "resource", "version", "expired", "revoked", "provider", "missing"],
)
def test_binding_denials_do_not_read_payload(database, variant):
    binding = BINDING
    opts = {}
    version = 3
    if variant == "environment":
        opts["environment"] = "production"
    if variant == "workload":
        opts["workload"] = "nfcore-api"
    if variant == "resource":
        opts["resources"] = frozenset({"projects/other-synthetic/secrets/other"})
    if variant == "version":
        version = 9  # cloud9 is not canonical3
    if variant == "expired":
        binding = replace(binding, not_after=NOW)
    if variant == "revoked":
        binding = replace(binding, state="revoked")
    if variant == "provider":
        binding = replace(binding, provider_id="other")
    if variant != "missing":
        put(database, binding)
    access = Access(binding)
    with pytest.raises(SecretResolutionError):
        compose(database, access, binding, **opts).signature_resolver.resolve(
            SecretReference(BINDING.reference_id, version),
            scope=SCOPE,
        )
    assert not access.calls


@pytest.mark.parametrize(
    "variant",
    [
        "crc",
        "returned-version",
        "schema",
        "envelope-scope",
        "material",
        "oversize",
        "duplicate",
        "password",
    ],
)
def test_payload_validation_is_sanitized(database, variant):
    put(database)
    access = Access()
    payload = access.payload
    envelope = json.loads(payload.data)
    if variant == "crc":
        access.payload = replace(payload, crc32c=0)
    elif variant == "returned-version":
        access.payload = replace(payload, name=payload.name.replace("/9", "/10"))
    else:
        if variant == "schema":
            envelope["schema"] = True
        if variant == "envelope-scope":
            envelope["binding"]["tenant_id"] = "other"
        if variant == "material":
            envelope["material"] = "%%%synthetic-invalid"
        if variant == "password":
            envelope["password"] = "eA=="
        data = json.dumps(envelope).encode()
        if variant == "oversize":
            data = b"x" * 65537
        if variant == "duplicate":
            data = b'{"schema":1,"schema":1}'
        access.payload = replace(payload, data=data, crc32c=google_crc32c.value(data))
    with pytest.raises(SecretResolutionError) as exc:
        compose(database, access).signature_resolver.resolve(
            SecretReference(BINDING.reference_id), scope=SCOPE
        )
    assert KEY.decode() not in str(exc.value)
    assert exc.value.__cause__ is None


def test_binding_changes_during_access_fail_closed(database):
    put(database)
    access = Access()
    access.callback = lambda: put(database, replace(BINDING, revision=2, state="revoked"), 1)
    with pytest.raises(SecretResolutionError):
        compose(database, access).signature_resolver.resolve(
            SecretReference(BINDING.reference_id), scope=SCOPE
        )


def test_platform_only_cas_replay_rollback_and_scope_immutability(database):
    admin = SecretBindingAdministration(database, clock=lambda: NOW)
    for a in (actor(admin=False), actor(enabled=False), replace(actor(), expires_at=NOW)):
        with pytest.raises(SecretResolutionError):
            admin.put(actor=a, binding=BINDING, expected_revision=0, correlation_id="test")
    put(database)
    put(database)  # exact replay is idempotent
    with database() as uow:
        uow.secret_bindings.put(replace(BINDING, revision=2), expected_revision=1)
        # no commit
    with database() as uow:
        assert uow.secret_bindings.get(BINDING.reference_id) == BINDING
        assert len(uow.control_plane.list_audit()) == 1
    with pytest.raises(PersistenceConflictError):
        put(database, replace(BINDING, revision=2, cloud_version="10"), 0)
    with pytest.raises(SecretResolutionError):
        put(database, replace(BINDING, revision=2, tenant_id="other"), 1)
    put(database, replace(BINDING, revision=2, cloud_version="10", canonical_version=4), 1)
    access = Access(replace(BINDING, revision=2, cloud_version="10", canonical_version=4))
    with compose(database, access).signature_resolver.resolve(
        SecretReference(BINDING.reference_id),
        scope=SCOPE,
    ) as value:
        assert value.reveal() == KEY
    assert access.calls == [BINDING.resource + "/versions/10"]


def test_fiscal_and_worker_use_existing_boundaries(database):
    fiscal = SecretBinding(
        "ref:synthetic/certificate",
        "tenant-synthetic",
        "unit-synthetic",
        "document-signing",
        "staging",
        "homologation",
        None,
        "nfcore-api",
        "certificate",
        "certificate-v2",
        "projects/nfcore-synthetic/secrets/cert",
        "7",
        not_after=NOW + timedelta(days=365),
    )
    put(database, fiscal)
    access = Access(fiscal)
    access.payload = replace(
        access.payload, data=encode_gsm_envelope(fiscal, KEY, password=b"test")
    )
    access.payload = replace(access.payload, crc32c=google_crc32c.value(access.payload.data))
    vault = compose(database, access, fiscal).fiscal_vault
    scope = ExecutionScope(
        "tenant-synthetic",
        "unit-synthetic",
        FiscalEnvironment.HOMOLOGATION,
        "test",
        host_namespace="nfcore",
    )
    context = SecretResolutionContext(
        scope, SecretUsagePurpose.DOCUMENT_SIGNING, SecretReferenceKind.CERTIFICATE, "nfcore-api"
    )
    ref = FiscalReference(
        fiscal.reference_id, context.kind, scope.tenant_id, scope.unit_id, scope.environment
    )
    material = vault.resolve(ref, context)
    assert material.pkcs12_bytes == KEY and material.password == b"test"
    assert access.calls == [fiscal.version_name]
    put(database)
    signature_access = Access()
    resolver = compose(database, signature_access).signature_resolver
    dep = build_gsm_worker_webhook_dependencies(
        resolver=resolver,
        reference=SecretReference(BINDING.reference_id),
        scope=SCOPE,
        destination_id="synthetic",
    )
    with pytest.raises(SecretResolutionError):
        dep.security.assert_dispatch_scope(replace(scope, tenant_id="other"))
    assert not signature_access.calls
    dep.security.assert_dispatch_scope(scope)
    assert dep.security.sign(b"synthetic-event", now=NOW).key_id == BINDING.reference_id
    assert signature_access.calls == [BINDING.version_name]


@pytest.mark.parametrize(
    "error",
    [
        exceptions.PermissionDenied("synthetic-private-value"),
        exceptions.DeadlineExceeded("synthetic-private-value"),
        exceptions.NotFound("synthetic-private-value"),
        RuntimeError("synthetic-private-value"),
    ],
)
def test_official_sdk_error_mapping_and_bounded_call(error):
    client = Mock(spec=secretmanager_v1.SecretManagerServiceClient)
    client.access_secret_version.side_effect = error
    access = GoogleSdkSecretAccess(client, timeout_seconds=2)
    with pytest.raises(
        (ExternalSecretPermissionDenied, ExternalSecretBackendUnavailable, SecretResolutionError)
    ) as exc:
        access.access(BINDING.version_name)
    assert "synthetic-private-value" not in str(exc.value)
    assert exc.value.__cause__ is None
    client.access_secret_version.assert_called_once_with(
        request={"name": BINDING.version_name},
        retry=None,
        timeout=2,
    )


def test_official_sdk_payload_contract_and_expired_bootstrap():
    client = Mock(spec=secretmanager_v1.SecretManagerServiceClient)
    data = encode_gsm_envelope(BINDING, KEY)
    client.access_secret_version.return_value = secretmanager_v1.AccessSecretVersionResponse(
        name=BINDING.version_name,
        payload=secretmanager_v1.SecretPayload(data=data, data_crc32c=google_crc32c.value(data)),
    )
    result = GoogleSdkSecretAccess(client).access(BINDING.version_name)
    assert result.data == data and result.crc32c == google_crc32c.value(data)
    assert KEY.decode() not in repr(result)
    client.reset_mock()
    with pytest.raises(SecretResolutionError):
        GoogleSdkSecretAccess(client, bootstrap_not_after=NOW, clock=lambda: NOW).access(
            BINDING.version_name
        )
    client.access_secret_version.assert_not_called()
    client.access_secret_version.return_value = secretmanager_v1.AccessSecretVersionResponse(
        name=BINDING.version_name,
        payload=secretmanager_v1.SecretPayload(data=data),
    )
    with pytest.raises(ExternalSecretBackendUnavailable):
        GoogleSdkSecretAccess(client).access(BINDING.version_name)


def test_no_ambient_identity_alias_or_unbounded_payload():
    with pytest.raises(SecretResolutionError):
        build_google_sdk_access(credentials=AnonymousCredentials(), environment="staging")
    for version in ("latest", "alias", "0", "09", "../9"):
        with pytest.raises(SecretResolutionError):
            replace(BINDING, cloud_version=version)
    for version in (True, "3"):
        with pytest.raises(SecretResolutionError):
            replace(BINDING, canonical_version=version)
    with pytest.raises(SecretResolutionError):
        encode_gsm_envelope(BINDING, b"x" * 65536)
    with pytest.raises(SecretResolutionError):
        replace(BINDING, not_after=NOW.replace(tzinfo=None))


def test_migration17_upgrade_preserves_binding_and_is_idempotent(database):
    put(database)
    assert database.initialize() == ()
    assert 17 in database.applied_migrations()
    # Simulate an existing schema before additive17; only synthetic test data.
    with (
        database.connection()
        if isinstance(database, PostgresFiscalDatabase)
        else database._connect()
    ) as c:
        c.execute("DROP TABLE fm_secret_bindings")
        c.execute("DELETE FROM fm_schema_migrations WHERE version=17")
        c.commit()
    assert database.initialize() == (17,)
    assert database.initialize() == ()
    put(database)
    with database() as uow:
        assert uow.secret_bindings.get(BINDING.reference_id) == BINDING


def test_explicit_identity_policies_without_cloud_access(monkeypatch):
    from google.auth.external_account import Credentials as FederatedCredentials
    from google.oauth2.service_account import Credentials as ServiceAccountCredentials

    factory = Mock()
    monkeypatch.setattr(secretmanager_v1, "SecretManagerServiceClient", factory)
    key = Mock(spec=ServiceAccountCredentials)
    for environment, expiry in (
        ("production", NOW + timedelta(days=1)),
        ("staging", None),
        ("staging", NOW),
        ("staging", NOW + timedelta(days=31)),
    ):
        with pytest.raises(SecretResolutionError):
            build_google_sdk_access(
                credentials=key, environment=environment, bootstrap_not_after=expiry, now=NOW
            )
    factory.assert_not_called()
    build_google_sdk_access(
        credentials=key,
        environment="staging",
        bootstrap_not_after=NOW + timedelta(days=30),
        now=NOW,
    )
    assert factory.call_args.kwargs["credentials"] is key
    assert (
        factory.call_args.kwargs["client_options"]["api_endpoint"] == "secretmanager.googleapis.com"
    )
    factory.reset_mock()
    identity = Mock(spec=FederatedCredentials)
    build_google_sdk_access(credentials=identity, environment="production", now=NOW)
    assert factory.call_args.kwargs["credentials"] is identity


def test_envelope_limit_is_inclusive_and_counts_password():
    # Base64 grows in groups of four; whitespace brings valid JSON to exact limit.
    client = Mock(spec=secretmanager_v1.SecretManagerServiceClient)
    for timeout in (0, -1, 31, float("nan"), float("inf")):
        with pytest.raises(SecretResolutionError):
            GoogleSdkSecretAccess(client, timeout_seconds=timeout)
    with pytest.raises(SecretResolutionError):
        encode_gsm_envelope(BINDING, b"synthetic", password=b"synthetic")


def test_backend_exception_is_not_retained_in_public_cause(database):
    put(database)
    access = Access()
    access.error = RuntimeError("synthetic-sensitive-sdk-detail")
    with pytest.raises(SecretResolutionError) as exc:
        compose(database, access).signature_resolver.resolve(
            SecretReference(BINDING.reference_id), scope=SCOPE
        )
    assert "synthetic-sensitive-sdk-detail" not in str(exc.value)
    assert exc.value.__cause__ is None


@pytest.mark.parametrize("extra", [0, 1])
def test_read_payload_size_exact_boundary(database, extra):
    put(database)
    access = Access()
    data = access.payload.data
    data += b" " * (65536 - len(data) + extra)
    access.payload = replace(access.payload, data=data, crc32c=google_crc32c.value(data))
    resolver = compose(database, access).signature_resolver
    if extra:
        with pytest.raises(SecretResolutionError):
            resolver.resolve(SecretReference(BINDING.reference_id), scope=SCOPE)
    else:
        with resolver.resolve(SecretReference(BINDING.reference_id), scope=SCOPE) as material:
            assert material.reveal() == KEY


def test_concurrent_binding_updates_have_one_winner(database):
    from concurrent.futures import ThreadPoolExecutor

    put(database)

    def update(version):
        try:
            put(
                database,
                replace(BINDING, revision=2, cloud_version=str(version), canonical_version=version),
                1,
            )
            return True
        except PersistenceConflictError:
            return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(update, [10, 11])) == [False, True]
    with database() as uow:
        assert uow.secret_bindings.get(BINDING.reference_id).revision == 2
        assert len(uow.control_plane.list_audit()) == 2


def test_binding_survives_new_database_handle(database):
    put(database)
    if isinstance(database, SqliteFiscalDatabase):
        restarted = SqliteFiscalDatabase(database.path)
    else:
        restarted = PostgresFiscalDatabase(os.environ["NFCORE_TEST_POSTGRES_DSN"])
    try:
        assert restarted.initialize() == ()
        with restarted() as uow:
            assert uow.secret_bindings.get(BINDING.reference_id) == BINDING
    finally:
        if isinstance(restarted, PostgresFiscalDatabase):
            restarted.close()
