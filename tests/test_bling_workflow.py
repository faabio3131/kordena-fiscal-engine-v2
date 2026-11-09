"""Real database/worker/HTTP/fiscal lifecycle, simulated external transport only."""

import hashlib
import os
from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock, patch
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from kordena_fiscal.application.bling_orders import ISSUE_ORDER, PROCESS_ORDER, BlingOrders
from kordena_fiscal.application.bling_processing import BlingProcessingHandler
from kordena_fiscal.application.outbox_worker import DurableFiscalOutboxWorker
from kordena_fiscal.application.service import FiscalApplicationService
from kordena_fiscal.archive import RetentionPolicyMetadata
from kordena_fiscal.connectors.bling_api import BlingApiError
from kordena_fiscal.contingency import FiscalDispatchStatus, FiscalOutboxService, FiscalOutboxStatus
from kordena_fiscal.contingency.outbox import OutboxClaimSelection
from kordena_fiscal.domain import (
    Cnpj,
    ElectronicInvoiceModel,
    FiscalAccountBinding,
    FiscalAccountId,
    FiscalEnvironment,
    FiscalUnitId,
    HostNamespace,
    HostScope,
)
from kordena_fiscal.gateway import (
    AuthorizationRequest,
    AuthorizationResult,
    AuthorizationStatus,
    FiscalGatewayClient,
    GatewayProviderMetadata,
)
from kordena_fiscal.lifecycle import FiscalDocumentState, IdempotencyKey
from kordena_fiscal.persistence import PersistenceConflictError, SqliteFiscalDatabase
from kordena_fiscal.runtime.bling_status import build_bling_status_router
from kordena_fiscal.runtime.bling_worker import build_bling_worker
from kordena_fiscal.runtime.config import RuntimeConfigurationError
from kordena_fiscal.runtime.fiscal_runtime import (
    CanonicalBridgeSecurityBoundary,
    CanonicalFiscalOperationPath,
)
from kordena_fiscal.runtime.provider_issuance_handler import build_provider_issuance_handler
from kordena_fiscal.security.s2s import (
    CallerIdentity,
    FiscalCapability,
    HostScopeGrant,
    InMemorySecurityAuditSink,
    S2SAuthorizer,
    WorkloadAuthenticator,
    WorkloadCredentialRecord,
)
from kordena_fiscal.xml import AccessKeyInput, build_access_key

NOW = datetime.now(UTC)
RAW = {"id": 9001, "contato": {"nome": "Synthetic customer"}, "itens": []}


@contextmanager
def workflow_database(tmp_path, backend):
    if backend == "sqlite":
        database = SqliteFiscalDatabase(tmp_path / "bling-workflow.sqlite")
        database.initialize()
        yield database
        return
    import psycopg
    from psycopg.sql import SQL, Identifier

    from kordena_fiscal.persistence.postgres import PostgresFiscalDatabase

    dsn = os.environ.get("NFCORE_TEST_POSTGRES_DSN", "").strip()
    if not dsn:
        pytest.skip("isolated PostgreSQL provided by CI")
    schema = "bling_test_" + uuid4().hex
    with psycopg.connect(dsn, autocommit=True) as connection:
        connection.execute(SQL("CREATE SCHEMA {}").format(Identifier(schema)))
    uri = urlsplit(dsn)
    query = dict(parse_qsl(uri.query))
    query["options"] = f"-c search_path={schema}"
    isolated = urlunsplit(uri._replace(query=urlencode(query, quote_via=quote)))
    database = None
    try:
        database = PostgresFiscalDatabase(isolated, min_pool_size=1, max_pool_size=8)
        database.initialize()
        yield database
    finally:
        if database is not None:
            database.close()
        with psycopg.connect(dsn, autocommit=True) as connection:
            connection.execute(SQL("DROP SCHEMA {} CASCADE").format(Identifier(schema)))


@pytest.fixture(params=["sqlite", "postgres"])
def installation(tmp_path, request):
    with workflow_database(tmp_path, request.param) as db:
        yield create_installation(db)


def create_installation(db):
    host = HostScope(HostNamespace("bling"), "host-tenant", "host-unit")
    with db() as uow:
        uow.bindings.add(
            FiscalAccountBinding(
                binding_id="bling",
                host_scope=host,
                fiscal_account_id=FiscalAccountId("tenant"),
                fiscal_unit_id=FiscalUnitId("unit"),
            )
        )
        uow.commit()
    application = FiscalApplicationService(db)
    scope = application.resolve_scope(
        host,
        environment=FiscalEnvironment.HOMOLOGATION,
        correlation_id="synthetic-test",
    )
    orders = BlingOrders(db, scope, "synthetic-company")
    return db, application, orders


def prepare(application, scope, document_id="doc-test"):
    digest = hashlib.sha256(document_id.encode()).hexdigest()
    request = AuthorizationRequest(
        scope=scope,
        access_key=build_access_key(
            AccessKeyInput(
                state_ibge_code="35",
                issued_at=NOW,
                issuer_cnpj=Cnpj("12345678000195"),
                model=ElectronicInvoiceModel.NFE,
                series=1,
                invoice_number=1,
                emission_type=1,
                numeric_code=12345678,
            )
        ),
        signed_xml=b"<synthetic-test-only/>",
        idempotency_key=IdempotencyKey(digest),
        request_fingerprint=digest,
    )
    application.reserve_issuance(
        scope=scope,
        key=request.idempotency_key,
        request_fingerprint=digest,
        document_id=document_id,
        created_at=NOW,
    )
    for state in (
        FiscalDocumentState.VALIDATING,
        FiscalDocumentState.READY_TO_SIGN,
        FiscalDocumentState.SIGNING,
    ):
        application.transition_lifecycle(
            document_id,
            state,
            occurred_at=NOW,
            reason="synthetic preparation",
            correlation_id=scope.correlation_id,
        )
    application.persist_prepared_authorization(
        document_id=document_id,
        request=request,
        occurred_at=NOW,
        retention=RetentionPolicyMetadata("synthetic-test", 1),
    )
    return request


class Transport:
    def __init__(self, status=AuthorizationStatus.AUTHORIZED, fail=False):
        self.calls = 0
        self.status = status
        self.fail = fail

    def authorize(self, request):
        self.calls += 1
        if self.fail:
            raise TimeoutError("synthetic-sensitive-provider-detail")
        return AuthorizationResult(
            status=self.status,
            scope=request.scope,
            access_key=request.access_key,
            idempotency_key=request.idempotency_key,
            request_fingerprint=request.request_fingerprint,
            provider=GatewayProviderMetadata("synthetic-test", "1"),
            protocol_reference="synthetic-protocol"
            if self.status is AuthorizationStatus.AUTHORIZED
            else None,
            rejection_code="SYNTHETIC" if self.status is AuthorizationStatus.REJECTED else None,
            rejection_message="Synthetic rejection"
            if self.status is AuthorizationStatus.REJECTED
            else None,
        )


def handler_for(application, orders, transport):
    path = CanonicalFiscalOperationPath(
        application,
        handlers={
            "issueFiscalDocument": build_provider_issuance_handler(
                application,
                resolve_prepared=application.load_prepared_document_authorization,
                gateway=FiscalGatewayClient(transport),
            ),
        },
    )
    raw = orders.snapshot(9001)["raw"] if orders.get(9001) is not None else RAW
    return BlingProcessingHandler(orders, Mock(return_value=raw), path)


def approve(orders):
    row = orders.stage(9001, RAW, event_id="synthetic-event", now=NOW)
    return orders.approve_prepared(
        9001,
        snapshot_sha256=row["snapshot_sha256"],
        document_id="doc-test",
        actor_id="synthetic-operator",
        now=NOW,
    )


@pytest.mark.parametrize("status", list(AuthorizationStatus))
def test_durable_worker_handoff_and_restart_never_resend(installation, status):
    db, application, orders = installation
    prepare(application, orders.scope)
    approve(orders)
    approve(orders)  # approval retry does not enqueue twice
    transport = Transport(status)
    handler = handler_for(application, orders, transport)
    worker = DurableFiscalOutboxWorker(
        uow_factory=db,
        handler=handler,
        claim_selection=OutboxClaimSelection(orders.scope, frozenset({ISSUE_ORDER})),
    )
    (job,) = worker.run_once(now=NOW)
    assert job.status is FiscalOutboxStatus.SUCCEEDED
    state = orders.get(9001)
    assert state["document_id"] == "doc-test"
    assert state["state"] == (
        "transmitting" if status is AuthorizationStatus.PENDING else status.value
    )
    # A fresh service/handler reads durable evidence, rather than an in-memory cache.
    restarted = BlingOrders(db, orders.scope, orders.company_id)
    assert handler_for(application, restarted, transport).dispatch(job).reference == "doc-test"
    assert transport.calls == 1
    with db() as uow:
        jobs = uow.outbox.list_for_scope(orders.scope)
        assert len([job for job in jobs if job.operation == ISSUE_ORDER]) == 1
        assert len([job for job in jobs if job.operation == "deliver_webhook"]) <= 2


def test_timeout_retry_records_recovery_without_second_authorization(installation):
    db, application, orders = installation
    prepare(application, orders.scope)
    approve(orders)
    transport = Transport(fail=True)
    worker = DurableFiscalOutboxWorker(
        uow_factory=db,
        handler=handler_for(
            application,
            orders,
            transport,
        ),
    )
    (first,) = worker.run_once(now=NOW)
    assert first.status is FiscalOutboxStatus.RETRY_WAIT
    assert "sensitive" not in first.last_error
    (second,) = worker.run_once(now=NOW + timedelta(seconds=10))
    assert second.status is FiscalOutboxStatus.SUCCEEDED
    assert orders.get(9001)["recovery_required"] is True
    assert transport.calls == 1


def test_snapshot_changes_are_preserved_and_block_issuance(installation):
    db, application, orders = installation
    prepare(application, orders.scope)
    original = approve(orders)
    changed = orders.stage(9001, {**RAW, "total": "99.00"}, event_id="update", now=NOW)
    assert changed["snapshot_sha256"] == original["snapshot_sha256"]
    assert changed["changed_snapshot_sha256"] != original["snapshot_sha256"]
    with pytest.raises(PersistenceConflictError):
        orders.approve_prepared(
            9001,
            snapshot_sha256=original["snapshot_sha256"],
            document_id="doc-test",
            actor_id="operator",
            now=NOW,
        )
    transport = Transport()
    worker = DurableFiscalOutboxWorker(
        uow_factory=db,
        handler=handler_for(
            application,
            orders,
            transport,
        ),
    )
    assert worker.run_once(now=NOW)[0].status is FiscalOutboxStatus.DEAD_LETTER
    assert transport.calls == 0
    with db() as uow:
        assert len(uow.archive.list_for_document(orders.scope, orders.key(9001))) == 2


def test_document_cannot_be_bound_to_two_orders_and_other_scope_cannot_read(installation):
    db, application, orders = installation
    prepare(application, orders.scope)
    approve(orders)
    second = orders.stage(9002, {**RAW, "id": 9002}, event_id="second", now=NOW)
    with pytest.raises(PersistenceConflictError):
        orders.approve_prepared(
            9002,
            snapshot_sha256=second["snapshot_sha256"],
            document_id="doc-test",
            actor_id="operator",
            now=NOW,
        )
    other = BlingOrders(db, replace(orders.scope, tenant_id="other"), orders.company_id)
    assert other.get(9001) is None
    other_env = BlingOrders(
        db,
        replace(orders.scope, environment=FiscalEnvironment.PRODUCTION),
        orders.company_id,
    )
    assert other_env.get(9001) is None


def test_deleted_order_cannot_be_resurrected_or_issued(installation):
    db, application, orders = installation
    prepare(application, orders.scope)
    orders.mark_deleted(9001, now=NOW)
    row = orders.stage(9001, RAW, event_id="late-old-event", now=NOW)
    assert row["deleted"] is True
    with pytest.raises(PersistenceConflictError):
        orders.approve_prepared(
            9001,
            snapshot_sha256=row["snapshot_sha256"],
            document_id="doc-test",
            actor_id="operator",
            now=NOW,
        )


def test_configured_worker_claims_only_bling_partition_without_certificate(installation, tmp_path):
    db, application, orders = installation
    token = tmp_path / "synthetic-token"
    token.write_text("synthetic-oauth-token")
    env = {
        "NFCORE_BLING_COMPANY_ID": orders.company_id,
        "NFCORE_BLING_TENANT_ID": "host-tenant",
        "NFCORE_BLING_UNIT_ID": "host-unit",
        "NFCORE_BLING_ENVIRONMENT": "homologation",
        "NFCORE_BLING_ACCESS_TOKEN_FILE": str(token),
    }
    with patch(
        "kordena_fiscal.runtime.bling_worker.EncryptedA1Vault.from_environ", return_value=None
    ):
        composition = build_bling_worker(db, env)
    assert (
        composition.claim_selection.scope.identity_partition_key
        == orders.scope.identity_partition_key
    )
    assert composition.claim_selection.operations == frozenset({PROCESS_ORDER})
    handler = composition.handlers[PROCESS_ORDER]
    with (
        patch("kordena_fiscal.runtime.bling_worker.fetch_sales_order", return_value=RAW) as fetch,
        patch("kordena_fiscal.runtime.bling_worker.verify_company") as verify,
    ):
        handler.fetch(9001)
        token.write_text("rotated-synthetic-token")
        handler.fetch(9001)
        verify.side_effect = BlingApiError(200, retryable=False)
        token.write_text("synthetic-wrong-company-token")
        with pytest.raises(BlingApiError):
            handler.fetch(9001)
    assert fetch.call_count == 2
    assert fetch.call_args.args == (9001, "rotated-synthetic-token")
    assert verify.call_count == 3
    assert verify.call_args.args == ("synthetic-wrong-company-token", orders.company_id)
    with pytest.raises(RuntimeConfigurationError):
        build_bling_worker(db, {**env, "NFCORE_BLING_ENVIRONMENT": "production"})
    with pytest.raises(RuntimeConfigurationError):
        build_bling_worker(db, {**env, "NFCORE_BLING_ACCESS_TOKEN_FILE": ""})


def test_s2s_status_uses_real_auth_and_hides_order_data(installation):
    db, application, orders = installation
    orders.stage(9001, RAW, event_id="test", now=NOW)
    path = CanonicalFiscalOperationPath(application)
    caller = CallerIdentity(
        caller_id="synthetic",
        host_namespace=HostNamespace("bling"),
        capabilities=frozenset({FiscalCapability.QUERY}),
        environments=frozenset({FiscalEnvironment.HOMOLOGATION}),
        scope_grants=(HostScopeGrant(tenant_id="host-tenant", unit_id="host-unit"),),
    )
    credential = WorkloadCredentialRecord.from_secret(
        credential_id="synthetic",
        caller=caller,
        secret="s" * 40,
        valid_from=NOW - timedelta(days=1),
        expires_at=NOW + timedelta(days=1),
    )
    security = CanonicalBridgeSecurityBoundary(
        authenticator=WorkloadAuthenticator((credential,)),
        authorizer=S2SAuthorizer(bindings=path, audit_sink=InMemorySecurityAuditSink()),
    )
    app = FastAPI()
    app.include_router(build_bling_status_router(db, orders.company_id, security))
    headers = {
        "Authorization": "Bearer " + "s" * 40,
        "X-FM-Workload-Credential-Id": "synthetic",
        "X-FM-Host-Namespace": "bling",
        "X-FM-Tenant-Id": "host-tenant",
        "X-FM-Unit-Id": "host-unit",
        "X-FM-Environment": "homologation",
        "X-Correlation-Id": "test",
    }
    with TestClient(app) as client:
        url = "/v1/integrations/bling/orders/9001"
        response = client.get(url, headers=headers)
        assert response.status_code == 200
        assert response.json()["state"] == "review_required"
        assert "Synthetic customer" not in response.text
        assert response.headers["cache-control"] == "no-store"
        assert (
            client.get(url, headers={**headers, "Authorization": "Bearer wrong"}).status_code == 401
        )
        assert client.get(url, headers={**headers, "X-FM-Unit-Id": "other"}).status_code == 403
        assert (
            client.get(url, headers={**headers, "X-FM-Environment": "production"}).status_code
            == 403
        )
        assert client.get(url + "0", headers=headers).status_code == 404


def test_handler_rejects_forged_job_scope(installation):
    db, application, orders = installation
    with db() as uow:
        job = (
            FiscalOutboxService(uow.outbox)
            .enqueue(
                scope=replace(orders.scope, tenant_id="other"),
                operation=PROCESS_ORDER,
                deduplication_key="synthetic",
                payload=b"synthetic",
                created_at=NOW,
            )
            .entry
        )
        uow.commit()
    handler = handler_for(application, orders, Transport())
    assert handler.dispatch(job).status is FiscalDispatchStatus.FATAL_FAILURE
    handler.fetch.assert_not_called()


@pytest.mark.parametrize("retryable", [True, False])
def test_fetch_failure_has_safe_worker_classification(installation, retryable):
    db, application, orders = installation
    payload = b'{"companyId":"synthetic-company","data":{"id":9001}}'
    application.receive_inbox_event(
        scope=orders.scope,
        producer="bling:" + orders.company_id,
        event_id="test",
        event_type="order.created",
        payload=payload,
        occurred_at=NOW,
        received_at=NOW,
        processing_operation=PROCESS_ORDER,
    )
    handler = handler_for(application, orders, Transport())
    handler.fetch.side_effect = BlingApiError(503 if retryable else 401, retryable=retryable)
    worker = DurableFiscalOutboxWorker(uow_factory=db, handler=handler)
    (job,) = worker.run_once(now=NOW)
    assert job.status is (
        FiscalOutboxStatus.RETRY_WAIT if retryable else FiscalOutboxStatus.DEAD_LETTER
    )


def test_review_selects_archived_snapshot_without_mutating_history(installation):
    db, application, orders = installation
    first = orders.stage(9001, RAW, event_id="first", now=NOW)
    changed = orders.stage(9001, {**RAW, "total": "12.00"}, event_id="second", now=NOW)
    selected = orders.select_snapshot(
        9001,
        snapshot_sha256=changed["changed_snapshot_sha256"],
        actor_id="operator",
        now=NOW,
    )
    assert selected["snapshot_sha256"] != first["snapshot_sha256"]
    assert selected["changed_snapshot_sha256"] is None
    prepare(application, orders.scope)
    orders.approve_prepared(
        9001,
        snapshot_sha256=selected["snapshot_sha256"],
        document_id="doc-test",
        actor_id="operator",
        now=NOW,
    )
    with pytest.raises(PersistenceConflictError):
        orders.select_snapshot(
            9001,
            snapshot_sha256=first["snapshot_sha256"],
            actor_id="operator",
            now=NOW,
        )
    with db() as uow:
        assert len(uow.archive.list_for_document(orders.scope, orders.key(9001))) == 2


def test_explicit_intake_retry_after_credentials_corrected_is_durable(installation):
    db, application, orders = installation
    received = application.receive_inbox_event(
        scope=orders.scope,
        producer="bling:" + orders.company_id,
        event_id="test",
        event_type="order.created",
        payload=b'{"companyId":"synthetic-company","data":{"id":9001}}',
        occurred_at=NOW,
        received_at=NOW,
        processing_operation=PROCESS_ORDER,
    )
    handler = handler_for(application, orders, Transport())
    handler.fetch.side_effect = BlingApiError(401, retryable=False)
    worker = DurableFiscalOutboxWorker(uow_factory=db, handler=handler)
    assert worker.run_once(now=NOW)[0].status is FiscalOutboxStatus.DEAD_LETTER
    handler.fetch.side_effect = None
    entry_id = received.entry.entry_id
    job_id = orders.retry_event(entry_id, request_id="correction-1", actor_id="operator")
    assert orders.retry_event(entry_id, request_id="correction-1", actor_id="operator") == job_id
    (retried,) = worker.run_once(now=NOW)
    assert retried.status is FiscalOutboxStatus.SUCCEEDED
    assert orders.get(9001)["state"] == "review_required"
    with db() as uow:
        jobs = uow.outbox.list_for_scope(orders.scope)
        assert len(jobs) == 2
        assert sum(job.status is FiscalOutboxStatus.DEAD_LETTER for job in jobs) == 1


def test_missing_certificate_keeps_issuance_pending_without_claim(installation, tmp_path):
    db, application, orders = installation
    prepare(application, orders.scope)
    approve(orders)
    token = tmp_path / "synthetic-token"
    token.write_text("synthetic-oauth-token")
    env = {
        "NFCORE_BLING_COMPANY_ID": orders.company_id,
        "NFCORE_BLING_TENANT_ID": "host-tenant",
        "NFCORE_BLING_UNIT_ID": "host-unit",
        "NFCORE_BLING_ENVIRONMENT": "homologation",
        "NFCORE_BLING_ACCESS_TOKEN_FILE": str(token),
    }
    with patch(
        "kordena_fiscal.runtime.bling_worker.EncryptedA1Vault.from_environ", return_value=None
    ):
        composition = build_bling_worker(db, env)
    worker = DurableFiscalOutboxWorker(
        uow_factory=db,
        handler=composition.handlers[PROCESS_ORDER],
        claim_selection=composition.claim_selection,
    )
    assert worker.run_once(now=NOW) == ()
    with db() as uow:
        assert uow.outbox.list_for_scope(orders.scope)[0].status is FiscalOutboxStatus.PENDING
        assert uow.lifecycle.get("doc-test").state is FiscalDocumentState.READY_TO_TRANSMIT


def test_worker_entrypoint_selects_connector_explicitly(monkeypatch):
    from kordena_fiscal.runtime import worker_main

    monkeypatch.setenv("NFCORE_WORKER_CONNECTOR", "bling")
    monkeypatch.delenv("NFCORE_WORKER_GSM_MODE", raising=False)
    monkeypatch.delenv("NFCORE_WORKER_ONESHOT", raising=False)
    with patch.object(worker_main, "run", return_value=0) as run:
        assert worker_main.main() == 0
        assert callable(run.call_args.kwargs["handler_factory"])
    monkeypatch.setenv("NFCORE_WORKER_GSM_MODE", "configured")
    with pytest.raises(RuntimeConfigurationError):
        worker_main.main()


@pytest.mark.parametrize("fail_after_write", [False, True])
def test_official_status_writeback_retries_without_reissuing(installation, fail_after_write):
    from kordena_fiscal.application.background_runtime import RoutedOutboxHandler
    from kordena_fiscal.application.bling_orders import PUBLISH_STATUS
    from kordena_fiscal.application.bling_status_delivery import BlingStatusPublisher

    db, application, orders = installation
    raw = {**RAW, "situacao": {"id": 1}}
    row = orders.stage(9001, raw, event_id="original", now=NOW)
    prepare(application, orders.scope)
    orders.approve_prepared(
        9001,
        snapshot_sha256=row["snapshot_sha256"],
        document_id="doc-test",
        actor_id="operator",
        now=NOW,
    )
    transport = Transport()
    issue_handler = handler_for(application, orders, transport)
    remote = {"status": 1, "writes": 0}

    def fetch(order_id):
        assert order_id == 9001
        return {**raw, "situacao": {"id": remote["status"]}}

    def update(order_id, status_id):
        assert order_id == 9001
        remote["status"] = status_id
        remote["writes"] += 1
        if fail_after_write:
            raise BlingApiError(None, retryable=True)

    publisher = BlingStatusPublisher(orders, {"authorized": 10, "rejected": 11}, fetch, update)
    worker = DurableFiscalOutboxWorker(
        uow_factory=db,
        handler=RoutedOutboxHandler(
            {
                ISSUE_ORDER: issue_handler,
                PUBLISH_STATUS: publisher,
            }
        ),
        claim_selection=OutboxClaimSelection(
            orders.scope, frozenset({ISSUE_ORDER, PUBLISH_STATUS})
        ),
    )
    assert worker.run_once(now=NOW)[0].status is FiscalOutboxStatus.SUCCEEDED
    first = worker.run_once(now=NOW)[0]
    if fail_after_write:
        assert first.status is FiscalOutboxStatus.RETRY_WAIT
        assert (
            worker.run_once(now=NOW + timedelta(seconds=10))[0].status
            is FiscalOutboxStatus.SUCCEEDED
        )
    else:
        assert first.status is FiscalOutboxStatus.SUCCEEDED
    assert remote == {"status": 10, "writes": 1}
    assert transport.calls == 1
    # Provider status notifications are not treated as new fiscal document versions.
    echo = orders.stage(9001, fetch(9001), event_id="status-echo", now=NOW)
    assert not echo.get("changed_snapshot_sha256")
    assert echo["state"] == "authorized"


def test_writeback_does_not_overwrite_intervening_business_status(installation):
    from kordena_fiscal.application.bling_orders import PUBLISH_STATUS
    from kordena_fiscal.application.bling_status_delivery import BlingStatusPublisher

    db, application, orders = installation
    row = orders.stage(9001, {**RAW, "situacao": {"id": 1}}, event_id="first", now=NOW)
    prepare(application, orders.scope)
    orders.approve_prepared(
        9001,
        snapshot_sha256=row["snapshot_sha256"],
        document_id="doc-test",
        actor_id="operator",
        now=NOW,
    )
    DurableFiscalOutboxWorker(
        uow_factory=db,
        handler=handler_for(application, orders, Transport()),
        claim_selection=OutboxClaimSelection(orders.scope, frozenset({ISSUE_ORDER})),
    ).run_once(now=NOW)
    update = Mock()
    publisher = BlingStatusPublisher(
        orders,
        {"authorized": 10},
        Mock(return_value={**RAW, "situacao": {"id": 99}}),
        update,
    )
    (job,) = DurableFiscalOutboxWorker(
        uow_factory=db,
        handler=publisher,
        claim_selection=OutboxClaimSelection(orders.scope, frozenset({PUBLISH_STATUS})),
    ).run_once(now=NOW)
    assert job.status is FiscalOutboxStatus.DEAD_LETTER
    update.assert_not_called()
    assert orders.get(9001)["state"] == "authorized"


def test_concurrent_approval_creates_only_one_fiscal_job(installation):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    db, application, orders = installation
    row = orders.stage(9001, RAW, event_id="original", now=NOW)
    prepare(application, orders.scope)
    barrier = Barrier(4)

    def approve_concurrently(_):
        barrier.wait(timeout=10)
        try:
            return orders.approve_prepared(
                9001,
                snapshot_sha256=row["snapshot_sha256"],
                document_id="doc-test",
                actor_id="operator",
                now=NOW,
            )
        except PersistenceConflictError:
            return None

    with ThreadPoolExecutor(max_workers=4) as pool:
        outcomes = list(pool.map(approve_concurrently, range(4)))
    assert any(result is not None for result in outcomes)
    with db() as uow:
        jobs = uow.outbox.list_for_scope(orders.scope, operations=frozenset({ISSUE_ORDER}))
        assert len(jobs) == 1
    assert orders.get(9001)["document_id"] == "doc-test"


def test_explicit_status_retry_never_queues_another_issuance(installation):
    from kordena_fiscal.application.bling_orders import PUBLISH_STATUS

    db, application, orders = installation
    prepare(application, orders.scope)
    approve(orders)
    transport = Transport()
    DurableFiscalOutboxWorker(
        uow_factory=db,
        handler=handler_for(application, orders, transport),
        claim_selection=OutboxClaimSelection(orders.scope, frozenset({ISSUE_ORDER})),
    ).run_once(now=NOW)
    job_id = orders.retry_status(9001, request_id="fixed-oauth", actor_id="operator")
    assert orders.retry_status(9001, request_id="fixed-oauth", actor_id="operator") == job_id
    with db() as uow:
        jobs = uow.outbox.list_for_scope(orders.scope)
        assert len([job for job in jobs if job.operation == PUBLISH_STATUS]) == 2
        assert len([job for job in jobs if job.operation == ISSUE_ORDER]) == 1
    assert transport.calls == 1
    assert orders.get(9001)["state"] == "authorized"


def test_retry_before_dispatch_preserves_document_and_refuses_after_dispatch(installation):
    from kordena_fiscal.persistence import PersistenceStateError

    db, application, orders = installation
    prepare(application, orders.scope)
    approve(orders)
    job_id = orders.retry_issuance(9001, request_id="fixed-certificate", actor_id="operator")
    assert (
        orders.retry_issuance(9001, request_id="fixed-certificate", actor_id="operator") == job_id
    )
    transport = Transport()
    result = DurableFiscalOutboxWorker(
        uow_factory=db,
        handler=handler_for(application, orders, transport),
        claim_selection=OutboxClaimSelection(orders.scope, frozenset({ISSUE_ORDER})),
    ).run_once(now=NOW)
    assert len(result) == 2
    assert all(job.status is FiscalOutboxStatus.SUCCEEDED for job in result)
    assert transport.calls == 1
    with pytest.raises(PersistenceStateError):
        orders.retry_issuance(9001, request_id="unsafe-resend", actor_id="operator")


@pytest.mark.parametrize("change", [{"total": "999.00"}, {"situacao": {"id": 99}}])
def test_issue_rechecks_current_order_even_when_update_webhook_has_not_arrived(
    installation, change
):
    db, application, orders = installation
    prepare(application, orders.scope)
    approve(orders)
    transport = Transport()
    handler = handler_for(application, orders, transport)
    handler.fetch.return_value = {**RAW, **change}
    result = DurableFiscalOutboxWorker(
        uow_factory=db,
        handler=handler,
        claim_selection=OutboxClaimSelection(orders.scope, frozenset({ISSUE_ORDER})),
    ).run_once(now=NOW)
    assert result[0].status is FiscalOutboxStatus.DEAD_LETTER
    assert transport.calls == 0
    assert orders.requires_dispatch("doc-test")


def test_signed_http_event_through_worker_issuance_and_official_return(installation):
    import hmac
    import json

    from kordena_fiscal.application.background_runtime import RoutedOutboxHandler
    from kordena_fiscal.application.bling_orders import PUBLISH_STATUS
    from kordena_fiscal.application.bling_status_delivery import BlingStatusPublisher
    from kordena_fiscal.runtime.bling_ingress import build_bling_ingress

    db, application, orders = installation
    secret = "synthetic-client-secret"
    router = build_bling_ingress(
        application,
        {
            "NFCORE_BLING_CLIENT_SECRET": secret,
            "NFCORE_BLING_COMPANY_ID": orders.company_id,
            "NFCORE_BLING_TENANT_ID": "host-tenant",
            "NFCORE_BLING_UNIT_ID": "host-unit",
            "NFCORE_BLING_ENVIRONMENT": "homologation",
        },
    )
    app = FastAPI()
    app.include_router(router)
    body = json.dumps(
        {
            "eventId": "end-to-end",
            "date": NOW.isoformat(),
            "version": "v1",
            "event": "order.created",
            "companyId": orders.company_id,
            "data": {"id": 9001},
        }
    ).encode()
    headers = {
        "X-Bling-Signature-256": "sha256=" + hmac.digest(secret.encode(), body, "sha256").hex()
    }
    provider = Transport()
    handler = handler_for(application, orders, provider)
    handler.fetch.return_value = {**RAW, "situacao": {"id": 1}}
    update = Mock()
    publisher = BlingStatusPublisher(
        orders,
        {"authorized": 10, "rejected": 11},
        handler.fetch,
        update,
    )
    registered = {PROCESS_ORDER: handler, ISSUE_ORDER: handler, PUBLISH_STATUS: publisher}
    worker = DurableFiscalOutboxWorker(
        uow_factory=db,
        handler=RoutedOutboxHandler(registered),
        claim_selection=OutboxClaimSelection(orders.scope, frozenset(registered)),
    )
    with TestClient(app) as client:
        assert client.post("/webhooks/bling", content=body, headers=headers).status_code == 202
        now = datetime.now(UTC)
        assert worker.run_once(now=now)[0].status is FiscalOutboxStatus.SUCCEEDED
        row = orders.get(9001)
        assert row["state"] == "review_required"
        assert provider.calls == 0
        prepare(application, orders.scope)
        orders.approve_prepared(
            9001,
            snapshot_sha256=row["snapshot_sha256"],
            document_id="doc-test",
            actor_id="operator",
            now=now,
        )
        assert worker.run_once(now=now)[0].status is FiscalOutboxStatus.SUCCEEDED
        assert worker.run_once(now=now)[0].status is FiscalOutboxStatus.SUCCEEDED
        assert orders.get(9001)["state"] == "authorized"
        update.assert_called_once_with(9001, 10)
        assert provider.calls == 1
        assert client.post("/webhooks/bling", content=body, headers=headers).status_code == 202
        assert worker.run_once(now=datetime.now(UTC)) == ()


def review_client(orders, *, tenant="tenant", unit="unit", role="owner"):
    from kordena_fiscal.runtime.bling_review import build_bling_review_router
    from kordena_fiscal.security.human_identity import (
        HumanAccount,
        HumanIdentityService,
        InMemoryHumanAccountRepository,
        InMemoryWebSessionRepository,
        PortalRole,
        ScryptPasswordHasher,
    )
    from kordena_fiscal.web import create_app

    password = "synthetic-review-password-2026"
    hasher = ScryptPasswordHasher()
    identity = HumanIdentityService(
        accounts=InMemoryHumanAccountRepository((HumanAccount(
            account_id="reviewer", email="review@example.test",
            password_hash=hasher.hash(password), tenant_id=tenant,
            role=PortalRole(role), unit_ids=frozenset({unit}),
        ),)),
        sessions=InMemoryWebSessionRepository(), password_hasher=hasher,
    )
    app = create_app(human_identity=identity)
    app.include_router(build_bling_review_router(identity, lambda: orders))
    client = TestClient(app, base_url="https://nfcore.test")
    assert client.post("/v1/auth/login", json={
        "email": "review@example.test", "password": password,
    }).status_code == 200
    return client


def test_portal_bling_review_session_csrf_snapshot_and_real_approval(installation):
    _db, application, orders = installation
    orders.stage(9001, RAW, event_id="review-1", now=NOW)
    orders.stage(
        9001, {**RAW, "observacoes": "revised"},
        event_id="review-2", now=NOW + timedelta(seconds=1),
    )
    client = review_client(orders)
    path = "/v1/portal/integrations/bling/orders/9001"
    reviewed = client.get(path)
    assert reviewed.status_code == 200
    assert reviewed.headers["cache-control"] == "no-store"
    data = reviewed.json()
    assert len(data["snapshots"]) == 2
    digest = data["order"]["changed_snapshot_sha256"]
    body = {"snapshot_sha256": digest}
    assert client.post(path + "/select-snapshot", json=body).status_code == 403
    headers = {"X-CSRF-Token": client.cookies.get("nfcore_csrf")}
    assert client.post(path + "/select-snapshot", json={**body, "actor_id": "spoof"},
                       headers=headers).status_code == 422
    assert client.post(path + "/select-snapshot", json=body, headers=headers).status_code == 200
    assert orders.get(9001)["reviewed_by"] == "reviewer"
    prepare(application, orders.scope)
    approval = {**body, "document_id": "doc-test"}
    assert client.post(path + "/approve-prepared", json=approval,
                       headers=headers).status_code == 200
    assert client.post(path + "/approve-prepared", json=approval,
                       headers=headers).status_code == 200
    assert orders.get(9001)["state"] == "queued"
    assert orders.get(9001)["approved_by"] == "reviewer"
    client.cookies.clear()
    assert client.get(path).status_code == 401


@pytest.mark.parametrize("attributes", [
    {"tenant": "other-tenant"}, {"unit": "other-unit"}, {"role": "auditor"},
])
def test_portal_bling_review_rejects_other_tenant_unit_or_role(installation, attributes):
    _db, _application, orders = installation
    orders.stage(9001, RAW, event_id="review-1", now=NOW)
    client = review_client(orders, **attributes)
    path = "/v1/portal/integrations/bling/orders/9001"
    assert client.get(path).status_code == 403
    assert client.post(path + "/select-snapshot", json={"snapshot_sha256": "x"},
                       headers={"X-CSRF-Token": client.cookies.get("nfcore_csrf")}
                       ).status_code == 403
