"""Internal registry certification; synthetic signing/transport never proves egress."""

import os
from datetime import UTC, datetime
from types import MappingProxyType

import pytest

from kordena_fiscal.application.background_runtime import BackgroundWorkerRuntime
from kordena_fiscal.application.webhook_delivery import SignedWebhookOutboxHandler
from kordena_fiscal.contingency import FiscalDispatchStatus, FiscalOutboxService, FiscalOutboxStatus
from kordena_fiscal.domain import ExecutionScope, FiscalEnvironment
from kordena_fiscal.persistence import SqliteFiscalDatabase
from kordena_fiscal.runtime.config import RuntimeConfigurationError
from kordena_fiscal.runtime.worker_composition import (
    WorkerWebhookDependencies,
    build_canonical_worker_handlers,
    build_production_worker_runtime,
)
from kordena_fiscal.runtime.worker_main import run
from kordena_fiscal.security import InMemoryWebhookKeyRing, WebhookSecurity

NOW = datetime(2026, 10, 9, tzinfo=UTC)


def _configure_staging_worker(monkeypatch):
    dsn = os.environ.get("NFCORE_TEST_POSTGRES_DSN", "").strip()
    if not dsn:
        pytest.skip("NFCORE_TEST_POSTGRES_DSN is required for entrypoint certification")
    monkeypatch.setenv("NFCORE_ENVIRONMENT", "staging")
    monkeypatch.setenv("NFCORE_PERSISTENCE_BACKEND", "postgres")
    monkeypatch.setenv("DATABASE_URL", dsn)
    monkeypatch.setenv("NFCORE_SECRET_BACKEND", "external")
    monkeypatch.setenv("NFCORE_REQUIRE_HTTPS", "true")


def dependencies():
    ring = InMemoryWebhookKeyRing(active_key_id="synthetic", keys={"synthetic": b"x" * 32})
    return WorkerWebhookDependencies(
        security=WebhookSecurity(key_resolver=ring, signing_key_id="synthetic"),
        destination_id="events",
    )


@pytest.fixture
def database(tmp_path):
    db = SqliteFiscalDatabase(tmp_path / "registry.sqlite3")
    db.initialize()
    return db


def enqueue(db, *, operation="deliver_webhook", tenant="tenant-registry"):
    scope = ExecutionScope(
        host_namespace="nfcore",
        tenant_id=tenant,
        unit_id="unit-registry",
        environment=FiscalEnvironment.HOMOLOGATION,
        correlation_id="corr-registry",
    )
    with db() as uow:
        entry = (
            FiscalOutboxService(uow.outbox)
            .enqueue(
                scope=scope,
                operation=operation,
                deduplication_key="registry-" + operation,
                payload=b'{"event":"synthetic"}',
                created_at=NOW,
            )
            .entry
        )
        uow.commit()
    return entry


def test_registry_registers_only_existing_concrete_handler_and_is_immutable(database):
    handlers = build_canonical_worker_handlers(uow_factory=database, webhook=dependencies())
    assert isinstance(handlers, MappingProxyType)
    assert set(handlers) == {"deliver_webhook"}
    assert isinstance(handlers["deliver_webhook"], SignedWebhookOutboxHandler)
    with pytest.raises(TypeError):
        handlers["authorize"] = handlers["deliver_webhook"]


@pytest.mark.parametrize("value", [None, object()])
def test_missing_dependencies_reject_before_claim_without_changing_outbox(database, value):
    entry = enqueue(database)
    with pytest.raises(RuntimeConfigurationError, match="canonical webhook signing"):
        build_canonical_worker_handlers(uow_factory=database, webhook=value)
    with database() as uow:
        current = uow.outbox.get(entry.entry_id)
        assert current.status is FiscalOutboxStatus.PENDING
        assert current.attempt_count == 0
        assert uow.delivery_audit.list_for_entry(entry.entry_id) == ()


@pytest.mark.parametrize("destination", ["", "  ", "x" * 257, "events\n"])
def test_invalid_destination_reference_rejected_without_echoing_input(destination):
    with pytest.raises(RuntimeConfigurationError, match="destination reference is invalid"):
        WorkerWebhookDependencies(security=dependencies().security, destination_id=destination)


def test_invalid_signing_dependency_rejected():
    with pytest.raises(RuntimeConfigurationError, match="signing dependency is invalid"):
        WorkerWebhookDependencies(security=object(), destination_id="events")


def test_dependency_repr_excludes_security_material():
    assert repr(dependencies()) == "WorkerWebhookDependencies(destination_id='events')"


def test_unknown_operation_and_missing_destination_fail_closed_on_canonical_outbox(database):
    known = enqueue(database)
    unknown = enqueue(database, operation="authorize")
    runtime = build_production_worker_runtime(
        uow_factory=database,
        handlers=build_canonical_worker_handlers(uow_factory=database, webhook=dependencies()),
        environment="test",
    )
    result = runtime.runtime.run_cycle()
    assert result.claimed == result.dead_letter == 2
    with database() as uow:
        assert uow.outbox.get(known.entry_id).last_error == "webhook destination is not configured"
        assert (
            uow.outbox.get(unknown.entry_id).last_error
            == "unsupported background operation: authorize"
        )
        assert len(uow.delivery_audit.list_for_entry(known.entry_id)) == 1


def test_handler_does_not_borrow_another_tenants_destination(database):
    from kordena_fiscal.control_plane import FiscalOrganization, FiscalUnitRegistration
    from kordena_fiscal.control_plane.commercial import WebhookDestinationConfig

    with database() as uow:
        uow.control_plane.add_organization(
            FiscalOrganization(tenant_id="other", legal_name="Synthetic Other")
        )
        uow.control_plane.add_unit(
            FiscalUnitRegistration(
                tenant_id="other",
                unit_id="unit-registry",
                display_name="Synthetic Unit",
                enabled_environments=frozenset({FiscalEnvironment.HOMOLOGATION}),
            )
        )
        uow.commercial.put_webhook_destination(
            WebhookDestinationConfig(
                destination_id="events",
                tenant_id="other",
                unit_id="unit-registry",
                environment=FiscalEnvironment.HOMOLOGATION,
                url="https://callback.example.invalid/path",
            )
        )
        uow.commit()
    entry = enqueue(database)
    handler = build_canonical_worker_handlers(uow_factory=database, webhook=dependencies())[
        "deliver_webhook"
    ]
    result = handler.dispatch(entry)
    assert result.status is FiscalDispatchStatus.FATAL_FAILURE
    assert result.error == "webhook destination is not configured"


def test_entrypoint_uses_canonical_registry_with_real_postgres(monkeypatch):
    _configure_staging_worker(monkeypatch)
    monkeypatch.delenv("NFCORE_WORKER_ONESHOT", raising=False)
    seen = []

    def inspect(runtime, stop):
        seen.append(runtime._worker._handler.operations)
        stop.set()

    monkeypatch.setattr(BackgroundWorkerRuntime, "run_forever", inspect)
    assert run(webhook=dependencies()) == 0
    assert seen == [frozenset({"deliver_webhook"})]


def test_entrypoint_rejects_ambiguous_composition_before_factory(monkeypatch):
    _configure_staging_worker(monkeypatch)
    monkeypatch.delenv("NFCORE_WORKER_ONESHOT", raising=False)

    def forbidden(*args):
        raise AssertionError("ambiguous source must not run")

    with pytest.raises(RuntimeConfigurationError, match="one handler composition source"):
        run(handler_factory=forbidden, webhook=dependencies())


def test_oneshot_never_builds_canonical_registry(monkeypatch):
    import kordena_fiscal.runtime.worker_main as main

    _configure_staging_worker(monkeypatch)
    monkeypatch.setenv("NFCORE_WORKER_ONESHOT", "true")

    def forbidden(**kwargs):
        raise AssertionError("probe must never compose delivery")

    monkeypatch.setattr(main, "build_canonical_worker_handlers", forbidden)
    assert run(webhook=dependencies()) == 0


@pytest.mark.parametrize("approved", [False, True])
def test_registry_resolves_durable_approval_before_signed_transport(
    database, monkeypatch, approved
):
    import hashlib
    from datetime import timedelta

    from kordena_fiscal.application.webhook_delivery import (
        FM_WEBHOOK_SIGNATURE_HEADER,
        WebhookDeliveryResponse,
    )
    from kordena_fiscal.control_plane import FiscalOrganization, FiscalUnitRegistration
    from kordena_fiscal.control_plane.commercial import WebhookDestinationConfig
    from kordena_fiscal.control_plane.webhook_policy import SystemWebhookDnsResolver
    from kordena_fiscal.gateway.webhook_transport import PinnedWebhookTransport
    from kordena_fiscal.security import WebhookSignature

    entry = enqueue(database)
    url = "https://callback.example.invalid/path"
    with database() as uow:
        uow.control_plane.add_organization(
            FiscalOrganization(tenant_id=entry.scope.tenant_id, legal_name="Synthetic Registry")
        )
        uow.control_plane.add_unit(
            FiscalUnitRegistration(
                tenant_id=entry.scope.tenant_id,
                unit_id=entry.scope.unit_id,
                display_name="Synthetic Registry",
                enabled_environments=frozenset({entry.scope.environment}),
            )
        )
        uow.commercial.put_webhook_destination(
            WebhookDestinationConfig(
                destination_id="events",
                tenant_id=entry.scope.tenant_id,
                unit_id=entry.scope.unit_id,
                environment=entry.scope.environment,
                url=url,
            )
        )
        if approved:
            version = uow.commercial.advance_configuration_version(
                entry.scope, "webhooks", "events", 0
            )
            uow.commercial.record_webhook_approval(
                entry.scope,
                "events",
                status="approved",
                version=version,
                expires_at=(datetime.now(UTC) + timedelta(hours=1)).isoformat(),
                url_sha256=hashlib.sha256(url.encode()).hexdigest(),
                requested_by="synthetic-owner",
                approved_by="synthetic-platform",
            )
        uow.commit()
    dependency = dependencies()
    delivered = []
    monkeypatch.setattr(
        SystemWebhookDnsResolver, "addresses", lambda self, hostname: ("93.184.216.34",)
    )

    def deliver(transport, request):
        assert request.approved_connection is not None
        assert request.scope == entry.scope
        assert request.body == entry.payload
        signature = WebhookSignature.parse(request.header(FM_WEBHOOK_SIGNATURE_HEADER))
        dependency.security.verify(request.body, signature, now=datetime.now(UTC))
        delivered.append(request.destination.url)
        return WebhookDeliveryResponse(204)

    monkeypatch.setattr(PinnedWebhookTransport, "deliver", deliver)
    handler = build_canonical_worker_handlers(uow_factory=database, webhook=dependency)[
        "deliver_webhook"
    ]
    # Claimed attempts are normally set by the durable worker before dispatch.
    from dataclasses import replace

    result = handler.dispatch(replace(entry, attempt_count=1))
    if approved:
        assert result.status is FiscalDispatchStatus.SUCCEEDED
        assert delivered == [url]
        with database() as uow:
            uow.commercial.record_webhook_approval(
                entry.scope,
                "events",
                status="revoked",
                version=None,
                expires_at=None,
                url_sha256=None,
            )
            uow.commit()
        assert handler.dispatch(replace(entry, attempt_count=1)).error == "WEBHOOK_POLICY_DENIED"
        assert delivered == [url]
    else:
        assert result.error == "WEBHOOK_POLICY_DENIED"
        assert delivered == []
