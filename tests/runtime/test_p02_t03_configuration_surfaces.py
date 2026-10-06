from __future__ import annotations

import importlib.util
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import Mock

import psycopg
import pytest
from fastapi.testclient import TestClient

from kordena_fiscal.application import (
    DurableFiscalOutboxWorker,
    SignedWebhookOutboxHandler,
    WebhookDeliveryResponse,
)
from kordena_fiscal.contingency import FiscalOutboxService, FiscalOutboxStatus, FiscalRetryPolicy
from kordena_fiscal.control_plane.webhook_policy import (
    DurableWebhookEgressPolicy,
    WebhookPolicyDenied,
    normalize_webhook_url,
)
from kordena_fiscal.domain import FiscalEnvironment
from kordena_fiscal.gateway.webhook_transport import PinnedWebhookTransport, _PinnedHttpsConnection
from kordena_fiscal.persistence import SqliteFiscalDatabase
from kordena_fiscal.persistence.postgres import PostgresFiscalDatabase
from kordena_fiscal.persistence.sqlite_control_plane import SqliteControlPlaneStore
from kordena_fiscal.runtime.webhook_destination import DurableWebhookDestinationResolver
from kordena_fiscal.security import InMemoryWebhookKeyRing, WebhookSecurity
from kordena_fiscal.security.human_identity import (
    HumanAccount,
    InMemoryHumanAccountRepository,
    PortalRole,
    ScryptPasswordHasher,
)
from kordena_fiscal.web import create_app
from kordena_fiscal.web.human_auth import CSRF_COOKIE, CSRF_HEADER
from kordena_fiscal.web.portal_runtime import DurableHumanPortalExecutor

ROOT = Path(__file__).parents[1]


def load_fixture(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "support" / (name + ".py"))
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fiscal = load_fixture("p02_fiscal_fixture")
configuration = load_fixture("p02_configuration_fixture")
SURFACES = ("certificates", "providers", "webhooks", "integrations", "settings")


@pytest.fixture(params=("sqlite", "postgres"))
def database(request, tmp_path):
    if request.param == "postgres":
        dsn = os.environ.get("NFCORE_TEST_POSTGRES_DSN", "")
        if not dsn:
            pytest.skip("real PostgreSQL DSN required; remote CI supplies it")
        with psycopg.connect(dsn, autocommit=True) as connection:
            connection.execute("DROP SCHEMA public CASCADE")
            connection.execute("CREATE SCHEMA public")
        db = PostgresFiscalDatabase(dsn)
    else:
        db = SqliteFiscalDatabase(tmp_path / "p03.sqlite3")
    db.initialize()
    fiscal.seed(db)
    configuration.seed(db)
    try:
        yield db
    finally:
        if isinstance(db, PostgresFiscalDatabase):
            db.close()


def app(database):
    accounts = InMemoryHumanAccountRepository()
    identity = fiscal.identity(accounts)
    hasher = ScryptPasswordHasher()
    for name, role in (("admin", PortalRole.ADMIN), ("restricted", PortalRole.OWNER)):
        accounts.save(
            HumanAccount(
                account_id="synthetic-" + name,
                email=name + "@example.com",
                password_hash=hasher.hash(fiscal.PASSWORD),
                tenant_id="tenant-a",
                role=role,
                unit_ids=frozenset({"unit-a"}),
            )
        )
    accounts.save(
        HumanAccount(
            account_id="synthetic-platform",
            email="platform@example.com",
            password_hash=hasher.hash(fiscal.PASSWORD),
            tenant_id="tenant-a",
            role=PortalRole.OWNER,
            platform_admin=True,
        )
    )
    return create_app(human_identity=identity, portal_executor=DurableHumanPortalExecutor(database))


def client(database, name="owner"):
    http = TestClient(app(database), base_url="https://nfcore.test")
    response = http.post(
        "/v1/auth/login", json={"email": name + "@example.com", "password": fiscal.PASSWORD}
    )
    assert response.status_code == 200
    return http


@pytest.mark.parametrize("surface", SURFACES)
def test_configuration_is_persisted_scoped_sanitized_and_not_promoted(database, surface):
    http = client(database)
    response = http.get(
        "/v1/portal/surfaces/" + surface + "?unit_id=unit-a",
        headers={"X-FM-Tenant-Id": "tenant-b"},
    )
    assert response.status_code == 200, response.text
    rows = response.json()["rows"]
    assert rows and all(row["unit_id"] == "unit-a" for row in rows)
    assert all(row["environment"] == "homologation" for row in rows)
    assert all(row["operational_verification"] == "not_confirmed" for row in rows)
    for forbidden in (
        configuration.PROTECTED_QUERY,
        "callback.example.invalid",
        "secret_sha256",
        "binding-other",
        "policy-other",
        "events-other",
        "module-other",
        "ref:synthetic-other",
        "ref:synthetic-prod",
        "events-prod",
        "policy-prod",
    ):
        assert forbidden not in response.text
    assert "governed_configuration" in response.text
    # New executor/client after HTTP recomposition reads the same persisted configuration.
    restarted = client(database).get("/v1/portal/surfaces/" + surface + "?unit_id=unit-a")
    assert restarted.json() == response.json()


@pytest.mark.parametrize("surface", SURFACES)
def test_existing_roles_and_unit_environment_authority_are_preserved(database, surface):
    endpoint = "/v1/portal/surfaces/" + surface
    anonymous = TestClient(app(database), base_url="https://nfcore.test")
    assert anonymous.get(endpoint).status_code == 401
    for role in ("operator", "auditor", "billing"):
        assert client(database, role).get(endpoint + "?unit_id=unit-a").status_code == 403
    for role in ("admin", "restricted"):
        http = client(database, role)
        assert http.get(endpoint + "?unit_id=unit-a").status_code == 200
        assert http.get(endpoint + "?unit_id=unit-b").status_code == 403
    owner = client(database)
    assert owner.get(endpoint).status_code == 409
    assert owner.get(endpoint + "?unit_id=missing").status_code == 409
    assert owner.get(endpoint + "?unit_id=unit-b").status_code == 200
    assert owner.get(endpoint + "?unit_id=unit-a&environment=production").status_code == 200
    with database() as uow:
        unit = uow.control_plane.get_unit("tenant-a", "unit-a")
    assert unit is not None and FiscalEnvironment.PRODUCTION in unit.enabled_environments
    # This only proves a read of existing production-labelled metadata, not production execution.


def test_pages_are_bounded_and_cannot_change_configuration(database):
    http = client(database)
    endpoint = "/v1/portal/surfaces/certificates?unit_id=unit-a"
    first = http.get(endpoint + "&limit=1&offset=0").json()["rows"]
    second = http.get(endpoint + "&limit=1&offset=1").json()["rows"]
    assert len(first) == len(second) == 1 and first != second
    assert http.get(endpoint + "&limit=101").status_code == 400
    assert http.get(endpoint + "&offset=-1").status_code == 400
    assert http.post("/v1/portal/operations/setWebhookDestination", json={}).status_code == 404
    assert http.post("/v1/portal/surfaces/webhooks", json={}).status_code == 405
    rows = http.get("/v1/portal/surfaces/webhooks?unit_id=unit-a").json()["rows"]
    assert rows[0]["destination_id"] == "events-a"


def test_read_cannot_enable_or_cross_an_environment(database):
    http = client(database)
    created = http.post(
        "/v1/portal/operations/onboardUnit",
        json={"unit_id": "hml-only", "display_name": "Synthetic HML only"},
        headers={
            CSRF_HEADER: http.cookies.get(CSRF_COOKIE),
            "Idempotency-Key": "synthetic-hml-unit-t03",
        },
    )
    assert created.status_code == 200, created.text
    for surface in SURFACES:
        endpoint = "/v1/portal/surfaces/" + surface + "?unit_id=hml-only"
        assert http.get(endpoint + "&environment=homologation").status_code == 200
        assert http.get(endpoint + "&environment=production").status_code == 409
    with database() as uow:
        unit = uow.control_plane.get_unit("tenant-a", "hml-only")
    assert unit is not None
    assert unit.enabled_environments == frozenset({FiscalEnvironment.HOMOLOGATION})


# Internal approved-policy certification. Every DNS address, credential and endpoint
# below is synthetic; transport is intercepted before any network operation.
PUBLIC_URL = "https://consumer.example.test/fiscal/webhooks"


def mutate(
    http,
    operation,
    values,
    version=0,
    key="synthetic-command",
    unit="unit-a",
    environment="homologation",
    csrf=True,
):
    headers = {"Idempotency-Key": key}
    if csrf:
        headers[CSRF_HEADER] = http.cookies.get(CSRF_COOKIE)
    return http.post(
        "/v1/portal/operations/" + operation,
        headers=headers,
        json={
            "unit_id": unit,
            "environment": environment,
            "expected_version": version,
            "values": values,
        },
    )


def request_destination(database, destination="approved-events", name="owner"):
    http = client(database, name)
    response = mutate(
        http,
        "configureWebhooks",
        {"destination_id": destination, "url": PUBLIC_URL, "enabled": True},
        key="request-" + destination,
    )
    assert response.status_code == 200, response.text
    assert response.json()["approval_status"] == "pending"
    return http


def decide(
    database,
    decision="approved",
    destination="approved-events",
    version=1,
    name="platform",
    url=PUBLIC_URL,
    expires=None,
    key="approve-events",
    csrf=True,
):
    http = client(database, name)
    headers = {"Idempotency-Key": key}
    if csrf:
        headers[CSRF_HEADER] = http.cookies.get(CSRF_COOKIE)
    return http.post(
        f"/v1/portal/egress/tenant-a/unit-a/homologation/{destination}/{decision}",
        headers=headers,
        json={
            "expected_version": version,
            "url": url,
            "expires_at": expires or (datetime.now(UTC) + timedelta(days=1)).isoformat(),
        },
    )


COMMANDS = [
    (
        "configureCertificates",
        {"reference_id": "ref:synthetic-rotated", "kind": "certificate"},
        "certificates",
        "certificate:",
    ),
    (
        "configureProviders",
        {
            "binding_id": "binding-a",
            "document_kind": "nfe",
            "state_code": "SP",
            "operation": "authorize",
            "provider_id": "synthetic-new",
            "enabled": True,
        },
        "providers",
        "binding-a",
    ),
    (
        "configureIntegrations",
        {"module_id": "synthetic-module", "enabled": True},
        "integrations",
        "synthetic-module",
    ),
    (
        "configureSettings",
        {
            "policy_id": "policy-new",
            "provider_id": "synthetic-new",
            "connect_timeout_seconds": 2,
            "read_timeout_seconds": 3,
            "max_attempts": 2,
            "base_delay_seconds": 1,
            "max_delay_seconds": 5,
            "jitter_ratio": 0.1,
            "circuit_failure_threshold": 3,
            "circuit_recovery_seconds": 10,
        },
        "settings",
        "synthetic-new",
    ),
    (
        "configureWebhooks",
        {"destination_id": "new-events", "url": PUBLIC_URL, "enabled": True},
        "webhooks",
        "new-events",
    ),
]


@pytest.mark.parametrize("operation,values,surface,target", COMMANDS)
def test_all_configuration_commands_survive_restart_and_replay_exactly(
    database, operation, values, surface, target
):
    http = client(database)
    first = mutate(http, operation, values)
    assert first.status_code == 200, first.text
    assert first.json()["version"] == 1
    replay = mutate(client(database), operation, values)
    assert replay.json() == first.json()
    assert mutate(http, operation, values, version=1).status_code == 409
    assert mutate(http, operation, values, key="stale-distinct").status_code == 409
    update = mutate(http, operation, values, version=1, key="update-distinct")
    assert update.status_code == 200, update.text
    with database() as uow:
        assert uow.commercial.configuration_version(fiscal.scope(), surface, target) == 2
        audits = uow.control_plane.list_audit(tenant_id="tenant-a")
    changed = [event for event in audits if event.action.value == "customer_configuration.changed"]
    assert len(changed) == 2
    assert all(
        PUBLIC_URL not in repr(event)
        and "ref:synthetic-rotated" not in repr(event)
        and "synthetic-command" not in repr(event)
        for event in changed
    )
    rows = client(database).get(f"/v1/portal/surfaces/{surface}?unit_id=unit-a").json()["rows"]
    assert any(row.get("version") == 2 for row in rows)


@pytest.mark.parametrize("name", ["operator", "auditor", "billing", "restricted"])
def test_configuration_mutations_deny_role_or_unit(database, name):
    http = client(database, name)
    assert (
        mutate(
            http, "configureIntegrations", {"module_id": "x", "enabled": True}, unit="unit-b"
        ).status_code
        == 403
    )


def test_command_csrf_browser_authority_missing_key_and_environment_fail_closed(database):
    http = client(database)
    values = {"destination_id": "events", "url": PUBLIC_URL, "enabled": True}
    assert mutate(http, "configureWebhooks", values, csrf=False).status_code == 403
    assert mutate(http, "configureWebhooks", values, key="").status_code == 400
    for authority_field in ["tenant_id", "platform_admin", "role", "headers", "approval_status"]:
        assert (
            mutate(http, "configureWebhooks", {**values, authority_field: "spoof"}).status_code
            == 400
        )
    assert (
        mutate(http, "configureWebhooks", values, environment="not-an-environment").status_code
        == 400
    )
    assert mutate(http, "configureWebhooks", values, version=True).status_code == 400
    assert mutate(http, "configureWebhooks", values, unit="missing").status_code in (400, 403)


def test_audit_failure_rolls_back_value_version_and_command_receipt(database, monkeypatch):
    http = client(database)
    values = {"module_id": "rollback-module", "enabled": True}
    original = SqliteControlPlaneStore.append_audit

    def fail(_self, _event):
        raise RuntimeError("synthetic audit failure")

    monkeypatch.setattr(SqliteControlPlaneStore, "append_audit", fail)
    with pytest.raises(RuntimeError, match="synthetic audit failure"):
        mutate(http, "configureIntegrations", values, key="atomic-command")
    with database() as uow:
        assert (
            uow.commercial.configuration_version(fiscal.scope(), "integrations", "rollback-module")
            == 0
        )
        assert not any(
            row.module_id == "rollback-module"
            for row in uow.commercial.list_module_bindings(
                tenant_id="tenant-a", unit_id="unit-a", environment=FiscalEnvironment.HOMOLOGATION
            )
        )
    monkeypatch.setattr(SqliteControlPlaneStore, "append_audit", original)
    assert mutate(http, "configureIntegrations", values, key="atomic-command").status_code == 200


def test_concurrent_expected_version_has_one_winner(database):
    # Sessions are independent; both contend on the same canonical partition.
    clients = [client(database), client(database)]

    def update(index):
        return mutate(
            clients[index],
            "configureIntegrations",
            {"module_id": "concurrent-module", "enabled": True},
            key="concurrent-" + str(index),
        ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(update, (0, 1)))
    assert sorted(statuses) == [200, 409]


def test_platform_approval_scope_independence_expiry_and_revocation(database):
    request_destination(database)
    for name in ("owner", "admin", "operator", "auditor", "billing"):
        assert decide(database, name=name).status_code == 403
    assert decide(database, csrf=False).status_code == 403
    assert decide(database, url="https://consumer.example.test/changed").status_code == 403
    assert (
        decide(database, expires=(datetime.now(UTC) - timedelta(seconds=1)).isoformat()).status_code
        == 400
    )
    approved = decide(database)
    assert approved.status_code == 200, approved.text
    assert approved.json()["version"] == 2
    revoked = decide(database, decision="revoked", version=2, key="revoke-events")
    assert revoked.status_code == 200
    assert revoked.json()["approval_status"] == "revoked"
    request_destination(database, destination="self-events", name="platform")
    assert decide(database, destination="self-events", key="self-approval").status_code == 403
    assert (
        client(database).get("/v1/portal/egress/tenant-b/unit-a/homologation/events").status_code
        == 403
    )


class SyntheticDns:
    def __init__(self, addresses=("93.184.216.34",)):
        self.result = addresses
        self.calls = 0

    def addresses(self, hostname):
        assert hostname == "consumer.example.test"
        self.calls += 1
        return self.result


@pytest.mark.parametrize(
    "url",
    [
        "http://consumer.example.test/path",
        "https://consumer.example.test:444/path",
        "https://127.0.0.1/path",
        "https://[2606:4700:4700::1111]/path",
        "https://localhost/path",
        "https://metadata.internal/path",
        "https://server.local/path",
        "https://user:pass@consumer.example.test/path",
        "https://consumer.example.test",
        "https://consumer.example.test/path?",
        "https://consumer.example.test/path?token=x",
        "https://consumer.example.test/path#",
        "https://consumer.example.test/path#x",
        "https://consumer.example.test./path",
        "https://consumer.example.test/%0d%0aInjected",
        "https://consumer.example.test/path\\evil",
        " https://consumer.example.test/path",
    ],
)
def test_url_policy_rejects_unsafe_shapes(url):
    with pytest.raises(WebhookPolicyDenied):
        normalize_webhook_url(url)


@pytest.mark.parametrize(
    "address",
    [
        "127.0.0.1",
        "10.0.0.1",
        "172.16.0.1",
        "192.168.1.1",
        "169.254.169.254",
        "100.64.0.1",
        "224.0.0.1",
        "240.0.0.1",
        "0.0.0.0",
        "::1",
        "::",
        "fe80::1",
        "fc00::1",
        "ff02::1",
        "::ffff:8.8.8.8",
        "2002:0808:0808::1",
    ],
)
def test_any_forbidden_dns_answer_denies_the_whole_attempt(database, address):
    request_destination(database)
    assert decide(database).status_code == 200
    policy = DurableWebhookEgressPolicy(database, SyntheticDns(("93.184.216.34", address)))
    with pytest.raises(WebhookPolicyDenied):
        policy.authorize(fiscal.scope(), "approved-events", PUBLIC_URL, datetime.now(UTC))


def test_pending_revoked_expired_changed_scope_and_dns_rebinding_are_denied(database):
    http = request_destination(database)
    dns = SyntheticDns()
    policy = DurableWebhookEgressPolicy(database, dns)

    def authorize(scope=None, at=None):
        return policy.authorize(
            scope or fiscal.scope(), "approved-events", PUBLIC_URL, at or datetime.now(UTC)
        )

    with pytest.raises(WebhookPolicyDenied):
        authorize()
    assert dns.calls == 0
    assert decide(database).status_code == 200
    assert authorize().address == "93.184.216.34"
    dns.result = ("169.254.169.254",)
    with pytest.raises(WebhookPolicyDenied):
        authorize()
    dns.result = ("93.184.216.34",)
    for partition in (
        fiscal.scope(tenant="tenant-b"),
        fiscal.scope(unit="unit-b"),
        fiscal.scope(environment=FiscalEnvironment.PRODUCTION),
    ):
        with pytest.raises(WebhookPolicyDenied):
            authorize(partition)
    with pytest.raises(WebhookPolicyDenied):
        authorize(at=datetime.now(UTC) + timedelta(days=2))
    assert (
        mutate(
            http,
            "configureWebhooks",
            {"destination_id": "approved-events", "url": PUBLIC_URL + "/changed", "enabled": True},
            version=2,
            key="change-destination",
        ).status_code
        == 200
    )
    with pytest.raises(WebhookPolicyDenied):
        authorize()
    with database() as uow:
        assert (
            uow.commercial.webhook_approval(fiscal.scope(), "approved-events")["approval_status"]
            == "pending"
        )


def test_revocation_during_dns_resolution_denies_before_connection(database):
    request_destination(database)
    assert decide(database).status_code == 200

    class RevokingDns(SyntheticDns):
        def addresses(self, hostname):
            assert (
                decide(database, decision="revoked", version=2, key="dns-revoke").status_code == 200
            )
            return super().addresses(hostname)

    with pytest.raises(WebhookPolicyDenied, match="CHANGED"):
        DurableWebhookEgressPolicy(database, RevokingDns()).authorize(
            fiscal.scope(), "approved-events", PUBLIC_URL, datetime.now(UTC)
        )


def test_worker_revalidates_approval_on_retry_and_missing_policy_never_delivers(database):
    request_destination(database)
    assert decide(database).status_code == 200
    now = datetime.now(UTC)
    with database() as uow:
        entry = (
            FiscalOutboxService(uow.outbox)
            .enqueue(
                scope=fiscal.scope(),
                operation="webhook_event",
                deduplication_key="synthetic-approved-event",
                payload=b'{"synthetic":true}',
                created_at=now,
            )
            .entry
        )
        uow.commit()
    ring = InMemoryWebhookKeyRing(active_key_id="synthetic", keys={"synthetic": b"x" * 32})
    security = WebhookSecurity(key_resolver=ring, signing_key_id="synthetic")
    transport = Mock()
    transport.deliver.return_value = WebhookDeliveryResponse(
        429, error_detail=PUBLIC_URL + "?secret=x"
    )
    resolver = DurableWebhookDestinationResolver(database, "approved-events")
    clock = Mock()
    clock.now.return_value = now
    handler = SignedWebhookOutboxHandler(
        security=security,
        destination_resolver=resolver,
        transport=transport,
        clock=clock,
        policy=DurableWebhookEgressPolicy(database, SyntheticDns()),
    )
    worker = DurableFiscalOutboxWorker(
        uow_factory=database,
        handler=handler,
        retry_policy=FiscalRetryPolicy(initial_delay_seconds=1),
    )
    first = worker.run_once(now=now)[0]
    assert first.status is FiscalOutboxStatus.RETRY_WAIT
    assert first.last_error == "WEBHOOK_HTTP_429"
    assert transport.deliver.call_count == 1
    assert decide(database, decision="revoked", version=2, key="worker-revoke").status_code == 200
    clock.now.return_value = now + timedelta(seconds=2)
    final = worker.run_once(now=now + timedelta(seconds=2))[0]
    assert final.status is FiscalOutboxStatus.DEAD_LETTER
    assert final.last_error == "WEBHOOK_POLICY_DENIED"
    assert transport.deliver.call_count == 1
    missing = SignedWebhookOutboxHandler(
        security=security, destination_resolver=resolver, transport=transport, clock=clock
    )
    assert missing.dispatch(replace(entry, attempt_count=1)).error == "WEBHOOK_POLICY_REQUIRED"
    assert transport.deliver.call_count == 1


def test_pinned_transport_revalidates_preserves_host_and_never_follows_redirect(
    database, monkeypatch
):
    request_destination(database)
    assert decide(database).status_code == 200
    policy = DurableWebhookEgressPolicy(database, SyntheticDns())
    scope = fiscal.scope()
    target = policy.authorize(scope, "approved-events", PUBLIC_URL, datetime.now(UTC))
    from kordena_fiscal.application.webhook_delivery import (
        WebhookDeliveryRequest,
        WebhookDestination,
    )

    request = WebhookDeliveryRequest(
        WebhookDestination("approved-events", PUBLIC_URL),
        b'{"synthetic":true}',
        (("Content-Type", "application/json"),),
        "synthetic-entry",
        1,
        scope,
        target,
    )
    connection = Mock()
    connection.getresponse.return_value.status = 302
    constructor = Mock(return_value=connection)
    monkeypatch.setattr(
        "kordena_fiscal.gateway.webhook_transport._PinnedHttpsConnection", constructor
    )
    assert PinnedWebhookTransport(policy).deliver(request).status_code == 302
    constructor.assert_called_once()
    actual = constructor.call_args.args[0]
    assert actual.address == "93.184.216.34" and actual.hostname == "consumer.example.test"
    connection.request.assert_called_once_with(
        "POST", "/fiscal/webhooks", body=request.body, headers={"Content-Type": "application/json"}
    )
    connection.close.assert_called_once()
    assert (
        decide(database, decision="revoked", version=2, key="transport-revoke").status_code == 200
    )
    with pytest.raises(WebhookPolicyDenied):
        PinnedWebhookTransport(policy).deliver(request)
    assert constructor.call_count == 1


@pytest.mark.parametrize("address", ["93.184.216.34", "2606:4700:4700::1111"])
def test_socket_connects_numeric_ip_and_tls_verifies_original_hostname(monkeypatch, address):
    import ssl

    from kordena_fiscal.control_plane.webhook_policy import ApprovedWebhookConnection

    tls = ssl.create_default_context()
    assert tls.check_hostname and tls.verify_mode == ssl.CERT_REQUIRED
    tls_mock = Mock(wraps=tls)
    tls_mock.wrap_socket = Mock(return_value=Mock())
    monkeypatch.setattr(
        "kordena_fiscal.gateway.webhook_transport.ssl.create_default_context", lambda: tls_mock
    )
    raw = Mock()
    monkeypatch.setattr(
        "kordena_fiscal.gateway.webhook_transport.socket.socket", Mock(return_value=raw)
    )
    target = ApprovedWebhookConnection(
        PUBLIC_URL, "consumer.example.test", "/fiscal/webhooks", address, 2
    )
    connection = _PinnedHttpsConnection(target, 3)
    connection.connect()
    raw.connect.assert_called_once_with((address, 443))
    tls_mock.wrap_socket.assert_called_once_with(raw, server_hostname="consumer.example.test")


def test_additive_migration_14_preserves_legacy_and_defaults_to_pending(database):
    # Reconstruct the exact previous schema in an isolated synthetic database.
    with database() as uow:
        sql = uow.commercial._connection
        sql.execute("DROP TABLE fm_configuration_commands")
        sql.execute("DROP TABLE fm_configuration_revisions")
        for column in (
            "approval_status",
            "approved_version",
            "approved_until",
            "approved_url_sha256",
            "requested_by",
            "approved_by",
        ):
            sql.execute("ALTER TABLE fm_commercial_webhook_destinations DROP COLUMN " + column)
        sql.execute("DELETE FROM fm_schema_migrations WHERE version = 14")
        uow.commit()
    assert database.initialize() == (14,)
    assert database.initialize() == ()
    with database() as uow:
        record = uow.commercial.webhook_approval(fiscal.scope(), "events-a")
        assert configuration.PROTECTED_QUERY in record["url"]
        assert record["approval_status"] == "pending"
        assert record["approved_version"] is None and record["approved_by"] is None
        assert uow.commercial.configuration_version(fiscal.scope(), "webhooks", "events-a") == 0
    with pytest.raises(WebhookPolicyDenied):
        DurableWebhookEgressPolicy(database, SyntheticDns()).authorize(
            fiscal.scope(), "events-a", record["url"], datetime.now(UTC)
        )


@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
def test_redirect_is_not_a_confirmed_delivery(status):
    from kordena_fiscal.contingency import FiscalDispatchStatus

    entry = Mock(entry_id="synthetic-entry", attempt_count=1)
    classified = SignedWebhookOutboxHandler._classify(entry, WebhookDeliveryResponse(status))
    assert classified.status is FiscalDispatchStatus.FATAL_FAILURE
    assert classified.reference is None


def test_legacy_platform_review_and_missing_version_do_not_leak_or_mutate(database):
    review = client(database, "platform").get(
        "/v1/portal/egress/tenant-a/unit-a/homologation/events-a"
    )
    assert review.status_code == 409
    assert configuration.PROTECTED_QUERY not in review.text
    assert "callback.example.invalid" not in review.text
    http = client(database)
    response = http.post(
        "/v1/portal/operations/configureIntegrations",
        headers={CSRF_HEADER: http.cookies.get(CSRF_COOKIE), "Idempotency-Key": "missing-version"},
        json={
            "unit_id": "unit-a",
            "environment": "homologation",
            "values": {"module_id": "missing-version", "enabled": True},
        },
    )
    assert response.status_code == 400
    with database() as uow:
        assert (
            uow.commercial.configuration_version(fiscal.scope(), "integrations", "missing-version")
            == 0
        )


def test_webhook_delivery_metadata_uses_existing_outbox_and_exact_scope(database):
    now = datetime.now(UTC)
    for suffix, scope in (
        ("a", fiscal.scope()),
        ("b", fiscal.scope(unit="unit-b")),
        ("other", fiscal.scope(tenant="tenant-b")),
        ("prod", fiscal.scope(environment=FiscalEnvironment.PRODUCTION)),
        ("host", fiscal.scope(host="other-host")),
    ):
        with database() as uow:
            FiscalOutboxService(uow.outbox).enqueue(
                scope=scope,
                operation="webhook_event",
                deduplication_key="telemetry-" + suffix,
                payload=b'{"synthetic_protected":"https://example.test/?secret=synthetic"}',
                created_at=now,
            )
            uow.commit()
    response = client(database).get("/v1/portal/surfaces/webhooks?unit_id=unit-a")
    assert response.status_code == 200
    delivery = [row for row in response.json()["rows"] if row["record_type"] == "webhook_delivery"]
    assert len(delivery) == 1
    assert delivery[0]["status"] == "pending" and delivery[0]["attempt_count"] == 0
    assert delivery[0]["operational_verification"] == "not_confirmed"
    assert "synthetic_protected" not in response.text and "secret=" not in response.text
    for forbidden in ("payload", "headers", "signature", "deduplication_key", "last_error"):
        assert forbidden not in delivery[0]


def test_expiry_during_dns_resolution_is_denied_before_connect(database, monkeypatch):
    request_destination(database)
    assert decide(database).status_code == 200
    now = datetime.now(UTC)

    class ClockAfterDns(datetime):
        @classmethod
        def now(cls, tz=None):
            return now + timedelta(days=2)

    monkeypatch.setattr("kordena_fiscal.control_plane.webhook_policy.datetime", ClockAfterDns)
    with pytest.raises(WebhookPolicyDenied, match="EXPIRED"):
        DurableWebhookEgressPolicy(database, SyntheticDns()).authorize(
            fiscal.scope(), "approved-events", PUBLIC_URL, now
        )


def test_public_native_ipv6_approval_is_validated(database):
    request_destination(database)
    assert decide(database).status_code == 200
    target = DurableWebhookEgressPolicy(
        database, SyntheticDns(("2606:4700:4700::1111",))
    ).authorize(fiscal.scope(), "approved-events", PUBLIC_URL, datetime.now(UTC))
    assert target.address == "2606:4700:4700::1111" and target.hostname == "consumer.example.test"
