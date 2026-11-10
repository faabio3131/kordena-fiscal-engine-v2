"""B-02/B-04: scope-safe recovery and visibility on canonical fiscal persistence."""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pytest
from test_bling_a02_oauth import installation

from kordena_fiscal.application.bling_operations import (
    BlingOperationalError,
    BlingOperationsService,
)
from kordena_fiscal.application.bling_orders import BlingOrders
from kordena_fiscal.connectors.bling_api import BlingApiError
from kordena_fiscal.connectors.bling_order_search import list_sales_orders
from kordena_fiscal.contingency import FiscalOutboxStatus
from kordena_fiscal.domain import ExecutionScope, FiscalEnvironment
from kordena_fiscal.integrations.bling_contracts import (
    BlingInstallationState,
    BlingRecoveryOutcome,
)


def setup(tmp_path: Path):
    db, store, view, scope, client, oauth, _seen = installation(tmp_path)
    state = oauth.begin(
        scope, view.installation_id, actor_id="operator", session_id="session",
    ).split("state=")[1]
    oauth.complete(
        scope, state=state, code="approved", actor_id="operator", session_id="session",
    )
    seen: list[tuple[str, str]] = []
    fetched: list[int] = []
    pauses: list[float] = []

    def verify(token: str, company_id: str) -> None:
        seen.append((token, company_id))
        assert token == "access-one"
        assert company_id == "expected-company"

    def fetch(order_id: int, token: str):
        fetched.append(order_id)
        assert token == "access-one"
        return {"id": order_id, "itens": [], "total": "1.00"}

    def search(page: int, limit: int, token: str):
        assert token == "access-one"
        assert page > 0 and 0 < limit <= 20
        return tuple({"id": order_id} for order_id in (105, 103)[:limit])

    service = BlingOperationsService(
        db, store, oauth, verify=verify, fetch=fetch, search=search,
        pause=pauses.append,
    )
    return db, store, view, scope, service, seen, fetched, pauses


def test_operator_recovers_missing_webhook_without_starting_fiscal_issuance(
    tmp_path: Path,
) -> None:
    db, _store, view, scope, service, seen, fetched, _pauses = setup(tmp_path)
    result = service.reconcile(
        scope, view.installation_id, 105,
        request_id="first-recovery", actor_id="operator",
    )
    assert result.outcome is BlingRecoveryOutcome.REQUIRES_REVIEW
    assert result.installation_id == view.installation_id
    assert fetched == [105]
    assert seen == [("access-one", "expected-company")]
    order = BlingOrders(db, scope, "expected-company")
    assert order.get(105)["state"] == "review_required"
    assert order.snapshot(105)["raw"]["id"] == 105
    with db() as uow:
        assert sum(uow.outbox.counts_by_status().values()) == 0
    repeated = service.reconcile(
        scope, view.installation_id, 105,
        request_id="first-recovery", actor_id="operator",
    )
    assert repeated.outcome is BlingRecoveryOutcome.ALREADY_RECORDED
    assert repeated.operation_id == result.operation_id
    assert fetched == [105]


def test_list_orders_is_paginated_company_bound_and_redacted(tmp_path: Path) -> None:
    db, _store, view, scope, service, _seen, _fetched, _pauses = setup(tmp_path)
    orders = BlingOrders(db, scope, "expected-company")
    for order_id in (104, 102, 103):
        orders.stage(
            order_id,
            {"id": order_id, "contato": {"nome": "CONFIDENTIAL BUYER"}, "itens": []},
            event_id=f"recovered-{order_id}", now=datetime.now(UTC),
        )
    first = service.list_orders(scope, view.installation_id, limit=2)
    assert [row["order_id"] for row in first.rows] == [102, 103]
    assert first.next_cursor is not None
    assert first.rows[0]["document_id"] is None
    assert "CONFIDENTIAL BUYER" not in str(first)
    second = service.list_orders(
        scope, view.installation_id, limit=2, cursor=first.next_cursor,
    )
    assert [row["order_id"] for row in second.rows] == [104]
    assert second.next_cursor is None
    other_scope = ExecutionScope(
        tenant_id=scope.tenant_id, unit_id="another-unit",
        environment=FiscalEnvironment.HOMOLOGATION,
        correlation_id="isolated", host_namespace="bling",
    )
    with pytest.raises(BlingOperationalError, match="BLING_INSTALLATION_NOT_FOUND"):
        service.list_orders(other_scope, view.installation_id)
    with pytest.raises(BlingOperationalError, match="BLING_INVALID_CURSOR"):
        service.list_orders(scope, view.installation_id, cursor="forged-cursor")
    with pytest.raises(BlingOperationalError, match="BLING_INVALID_LIMIT"):
        service.list_orders(scope, view.installation_id, limit=101)


def test_provider_discovery_backfills_bounded_page_and_reports_partial(
    tmp_path: Path,
) -> None:
    db, _store, view, scope, service, seen, fetched, pauses = setup(tmp_path)
    preview, next_page = service.search_orders(scope, view.installation_id, limit=2)
    assert preview == (
        {"order_id": 105, "recorded": False},
        {"order_id": 103, "recorded": False},
    )
    assert next_page == "page:2"
    result = service.backfill_page(
        scope, view.installation_id, page=1, limit=2,
        request_id="batch-one", actor_id="operator",
    )
    assert result == {
        "examined": 2, "recovered": 2, "already_recorded": 0,
        "next_cursor": "page:2", "fiscal_issuance_started": False,
    }
    assert fetched == [105, 103]
    assert len(pauses) == 2
    assert all(seconds >= 0.35 for seconds in pauses)
    again = service.backfill_page(
        scope, view.installation_id, page=1, limit=2,
        request_id="batch-one", actor_id="operator",
    )
    assert again["recovered"] == 0
    assert again["already_recorded"] == 2
    assert fetched == [105, 103]
    assert seen
    with db() as uow:
        assert sum(uow.outbox.counts_by_status().values()) == 0


def test_recovery_fails_closed_without_valid_installation_or_provider(
    tmp_path: Path,
) -> None:
    _db, store, view, scope, service, _seen, _fetched, _pauses = setup(tmp_path)
    record = store.get_for_scope(scope, view.installation_id)
    assert record is not None
    store.transition(
        scope, view.installation_id, expected_revision=record.revision,
        state=BlingInstallationState.PAUSED,
    )
    with pytest.raises(BlingOperationalError, match="BLING_PAUSED"):
        service.reconcile(
            scope, view.installation_id, 100,
            request_id="paused", actor_id="operator",
        )
    with pytest.raises(BlingOperationalError, match="BLING_PAUSED"):
        service.search_orders(scope, view.installation_id)
    with pytest.raises(BlingOperationalError, match="BLING_INPUT_INVALID"):
        service.reconcile(
            scope, view.installation_id, 100,
            request_id="", actor_id="operator",
        )


def test_jobs_and_metrics_do_not_expose_provider_or_customer_payload(tmp_path: Path) -> None:
    db, _store, view, scope, service, _seen, _fetched, _pauses = setup(tmp_path)
    orders = BlingOrders(db, scope, "expected-company")
    orders.stage(
        120, {"id": 120, "contato": {"nome": "CUSTOMER SECRET"}, "itens": []},
        event_id="secret-test", now=datetime.now(UTC),
    )
    from kordena_fiscal.application.bling_orders import PUBLISH_STATUS, encode_order
    from kordena_fiscal.contingency import FiscalOutboxService

    foreign = BlingOrders(db, scope, "other-company")
    with db() as uow:
        FiscalOutboxService(uow.outbox).enqueue(
            scope=scope, operation=PUBLISH_STATUS,
            deduplication_key=orders.key(120) + ":original-status",
            payload=encode_order({
                "order_id": 120, "status": "authorized", "private": "PRIVATE ORDER RAW DATA",
            }),
            created_at=datetime.now(UTC),
        )
        FiscalOutboxService(uow.outbox).enqueue(
            scope=scope, operation=PUBLISH_STATUS,
            deduplication_key=foreign.key(121) + ":original-status",
            payload=encode_order({
                "order_id": 121, "status": "authorized", "private": "OTHER COMPANY SECRET",
            }),
            created_at=datetime.now(UTC),
        )
        uow.commit()
    jobs = service.list_jobs(scope, view.installation_id)
    assert len(jobs["rows"]) == 1
    assert jobs["rows"][0]["status"] == FiscalOutboxStatus.PENDING.value
    assert "PRIVATE ORDER RAW DATA" not in str(jobs)
    assert "OTHER COMPANY SECRET" not in str(jobs)
    assert "CUSTOMER SECRET" not in str(jobs)
    metrics = service.page_metrics(scope, view.installation_id)
    assert metrics["order_states"]["review_required"] == 1
    assert metrics["job_states"]["pending"] == 1
    assert metrics["has_dead_letter"] is False


@pytest.mark.parametrize(
    ("status", "retryable"),
    [(401, False), (429, True), (503, True)],
)
def test_provider_listing_classifies_failures(status: int, retryable: bool) -> None:
    with patch("kordena_fiscal.connectors.bling_order_search.HTTPSConnection") as connection:
        connection.return_value.getresponse.return_value.status = status
        with pytest.raises(BlingApiError) as error:
            list_sales_orders(2, 10, "synthetic-token")
        assert error.value.status == status
        assert error.value.retryable is retryable


def test_provider_listing_validates_fixed_origin_pagination_and_identity() -> None:
    with patch("kordena_fiscal.connectors.bling_order_search.HTTPSConnection") as connect:
        instance = connect.return_value
        result = instance.getresponse.return_value
        result.status = 200
        result.read.return_value = b'{"data":[{"id":10},{"id":11}]}'
        assert list_sales_orders(2, 10, "token") == ({"id": 10}, {"id": 11})
        connect.assert_called_once_with("api.bling.com.br", timeout=10)
        instance.request.assert_called_once_with(
            "GET", "/Api/v3/pedidos/vendas?pagina=2&limite=10",
            headers={"Authorization": "Bearer token", "Accept": "application/json"},
        )
        result.read.return_value = b'{"data":[{"id":10},{"id":10}]}'
        with pytest.raises(BlingApiError):
            list_sales_orders(2, 10, "token")
    with patch("kordena_fiscal.connectors.bling_order_search.HTTPSConnection") as connect:
        with pytest.raises(ValueError):
            list_sales_orders(0, 10, "token")
        connect.assert_not_called()


def test_status_retry_requires_proven_dead_letter_and_keeps_idempotency(
    tmp_path: Path,
) -> None:
    from datetime import timedelta

    from kordena_fiscal.application.bling_orders import PUBLISH_STATUS, encode_order
    from kordena_fiscal.contingency import FiscalOutboxService
    from kordena_fiscal.contingency.outbox import OutboxClaimSelection

    db, _store, view, scope, service, _seen, _fetched, _pauses = setup(tmp_path)
    orders = BlingOrders(db, scope, "expected-company")
    orders.stage(
        333, {"id": 333, "itens": []},
        event_id="status-retry-test", now=datetime.now(UTC),
    )
    with db() as uow:
        old = uow.commercial.configuration_receipt(scope, orders.key(333))
        assert old is not None
        changed = {
            **old, "state": "authorized", "document_id": "synthetic-document",
            "approved_at": datetime.now(UTC).isoformat(),
        }
        assert uow.commercial.replace_configuration_receipt(
            scope, orders.key(333), old, changed,
        )
        uow.commit()
    with pytest.raises(BlingOperationalError, match="BLING_RECOVERY_REQUIRED"):
        service.retry_status(
            scope, view.installation_id, 333,
            request_id="premature-retry", actor_id="operator",
        )
    # Another Bling company can use the same numeric order ID within a unit.
    # Its dead letter must never authorize a writeback for this installation.
    foreign_key = BlingOrders(db, scope, "other-company").key(333)
    foreign_now = datetime.now(UTC)
    with db() as uow:
        FiscalOutboxService(uow.outbox).enqueue(
            scope=scope, operation=PUBLISH_STATUS,
            deduplication_key=foreign_key + ":original-status",
            payload=encode_order({"order_id": 333, "status": "authorized"}),
            created_at=foreign_now,
        )
        uow.commit()
    with db() as uow:
        foreign_claimed = uow.outbox.claim_due(
            now=foreign_now + timedelta(seconds=1),
            limit=1, lease_duration=timedelta(seconds=30),
            selection=OutboxClaimSelection(
                scope=scope, operations=frozenset({PUBLISH_STATUS}),
            ),
        )
        assert len(foreign_claimed) == 1
        uow.outbox.dead_letter(
            foreign_claimed[0].entry_id,
            expected_attempt=foreign_claimed[0].attempt_count,
            error="synthetic foreign provider failure",
        )
        uow.commit()
    with pytest.raises(BlingOperationalError, match="BLING_RECOVERY_REQUIRED"):
        service.retry_status(
            scope, view.installation_id, 333,
            request_id="foreign-only", actor_id="operator",
        )
    now = datetime.now(UTC)
    with db() as uow:
        FiscalOutboxService(uow.outbox).enqueue(
            scope=scope, operation=PUBLISH_STATUS,
            deduplication_key=orders.key(333) + ":original-status",
            payload=encode_order({"order_id": 333, "status": "authorized"}),
            created_at=now,
        )
        uow.commit()
    with db() as uow:
        claimed = uow.outbox.claim_due(
            now=now + timedelta(seconds=1),
            limit=1, lease_duration=timedelta(seconds=30),
            selection=OutboxClaimSelection(
                scope=scope, operations=frozenset({PUBLISH_STATUS}),
            ),
        )
        assert len(claimed) == 1
        uow.outbox.dead_letter(
            claimed[0].entry_id, expected_attempt=claimed[0].attempt_count,
            error="synthetic provider permanent failure",
        )
        uow.commit()
    retry = service.retry_status(
        scope, view.installation_id, 333,
        request_id="approved-retry", actor_id="operator",
    )
    assert retry.outcome is BlingRecoveryOutcome.QUEUED
    repeated = service.retry_status(
        scope, view.installation_id, 333,
        request_id="approved-retry", actor_id="operator",
    )
    assert repeated.operation_id == retry.operation_id
