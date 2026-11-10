"""Bling operational queue and missing-webhook recovery on canonical fiscal stores.

No duplicate order persistence, fiscal business rule, outbox, authentication,
tenant authority or API. Provider facts can only stage a review-required order;
the human approval and deterministic NF-e path remain separate.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import json
import time
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any, Protocol

from kordena_fiscal.application.bling_orders import (
    ISSUE_ORDER,
    PROCESS_ORDER,
    PUBLISH_STATUS,
    BlingOrders,
)
from kordena_fiscal.application.service import FiscalApplicationService
from kordena_fiscal.connectors.bling_api import fetch_sales_order, verify_company
from kordena_fiscal.connectors.bling_order_search import list_sales_orders
from kordena_fiscal.contingency import FiscalOutboxStatus
from kordena_fiscal.domain import ExecutionScope, FiscalValidationError
from kordena_fiscal.integrations.bling_contracts import (
    BlingInstallationState,
    BlingInstallationView,
    BlingOrderPage,
    BlingOrderSummary,
    BlingRecoveryOutcome,
    BlingRecoveryResult,
)
from kordena_fiscal.persistence.bling_installations import BlingInstallationRepository
from kordena_fiscal.persistence.ports import FiscalUnitOfWorkFactory


class BlingOAuthAccess(Protocol):
    def access_token(self, scope: ExecutionScope, installation_id: str) -> str: ...


class BlingOperationalError(RuntimeError):
    """No provider payload, credential, account number or raw tax facts in errors."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class BlingOperationsService:
    """Session-authenticated router supplies only canonical ExecutionScope."""

    def __init__(
        self,
        factory: FiscalUnitOfWorkFactory,
        installations: BlingInstallationRepository,
        oauth: BlingOAuthAccess,
        *,
        fetch: Callable[[int, str], dict[str, Any]] = fetch_sales_order,
        search: Callable[[int, int, str], tuple[dict[str, Any], ...]] = list_sales_orders,
        verify: Callable[[str, str], None] = verify_company,
        pause: Callable[[float], None] = time.sleep,
    ) -> None:
        self.factory = factory
        self.installations = installations
        self.oauth = oauth
        self._fetch = fetch
        self._search = search
        self._verify = verify
        self._pause = pause

    def _bound(
        self, scope: ExecutionScope, installation_id: str, *, active: bool = False,
    ) -> BlingInstallationView:
        if scope.host_namespace != "bling":
            raise BlingOperationalError("BLING_SCOPE_FORBIDDEN")
        view = self.installations.get_for_scope(scope, installation_id)
        if view is None:
            raise BlingOperationalError("BLING_INSTALLATION_NOT_FOUND")
        host = self.installations.host_binding(installation_id)
        if host is None:
            raise BlingOperationalError("BLING_INSTALLATION_NOT_FOUND")
        try:
            current = FiscalApplicationService(self.factory).resolve_scope(
                host, environment=view.environment, correlation_id="bling-operations",
            )
        except FiscalValidationError:
            raise BlingOperationalError("BLING_SCOPE_FORBIDDEN") from None
        if (
            current.identity_partition_key != scope.identity_partition_key
            or current.tenant_id != view.tenant_id
            or current.unit_id != view.unit_id
        ):
            raise BlingOperationalError("BLING_SCOPE_FORBIDDEN")
        if active and view.state is not BlingInstallationState.CONNECTED:
            raise BlingOperationalError(
                "BLING_NEEDS_REAUTH"
                if view.state is BlingInstallationState.NEEDS_REAUTH
                else "BLING_PAUSED"
            )
        return view

    def _orders(
        self, scope: ExecutionScope, installation_id: str, *, active: bool = False,
    ) -> BlingOrders:
        view = self._bound(scope, installation_id, active=active)
        return BlingOrders(self.factory, scope, view.company_id)

    @staticmethod
    def _scope_tag(scope: ExecutionScope, installation_id: str) -> str:
        return hashlib.sha256(
            json.dumps(
                [*scope.identity_material, installation_id], separators=(",", ":"),
            ).encode()
        ).hexdigest()

    @classmethod
    def _cursor(cls, scope: ExecutionScope, installation_id: str, last: int) -> str:
        raw = json.dumps({
            "scope": cls._scope_tag(scope, installation_id), "after": last,
        }, separators=(",", ":")).encode()
        return base64.urlsafe_b64encode(raw).decode().rstrip("=")

    @classmethod
    def _after(cls, scope: ExecutionScope, installation_id: str, cursor: str | None) -> int:
        if cursor is None:
            return 0
        if not cursor or len(cursor) > 256 or not cursor.isascii():
            raise BlingOperationalError("BLING_INVALID_CURSOR")
        try:
            data = json.loads(
                base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)),
            )
            if (
                not isinstance(data, dict) or set(data) != {"scope", "after"}
                or type(data["after"]) is not int or data["after"] <= 0
                or data["scope"] != cls._scope_tag(scope, installation_id)
            ):
                raise ValueError
            return data["after"]
        except (ValueError, TypeError, KeyError, UnicodeDecodeError, binascii.Error):
            raise BlingOperationalError("BLING_INVALID_CURSOR") from None

    @staticmethod
    def _is_order_receipt(row: Mapping[str, object], company_id: str) -> bool:
        return (
            type(row.get("order_id")) is int
            and int(str(row["order_id"])) > 0
            and row.get("company_id") == company_id
            and isinstance(row.get("snapshot_sha256"), str)
            and isinstance(row.get("state"), str)
        )

    def _receipts(self, orders: BlingOrders) -> tuple[Mapping[str, object], ...]:
        with self.factory() as uow:
            rows = uow.commercial.list_configuration_receipts(orders.scope, "bling-order:")
        if len(rows) > 100_000:
            raise BlingOperationalError("BLING_TEMPORARILY_UNAVAILABLE")
        return tuple(row for row in rows if self._is_order_receipt(row, orders.company_id))

    def list_orders(
        self, scope: ExecutionScope, installation_id: str, *,
        cursor: str | None = None, limit: int = 50,
    ) -> BlingOrderPage:
        orders = self._orders(scope, installation_id)
        if type(limit) is not int or not 1 <= limit <= 100:
            raise BlingOperationalError("BLING_INVALID_LIMIT")
        after = self._after(scope, installation_id, cursor)
        found = sorted(
            (row for row in self._receipts(orders) if int(str(row["order_id"])) > after),
            key=lambda row: int(str(row["order_id"])),
        )
        views: list[BlingOrderSummary] = []
        for row in found[:limit]:
            state = str(row["state"])
            views.append({
                "order_id": int(str(row["order_id"])),
                "state": state,
                "document_id": (
                    str(row["document_id"]) if isinstance(row.get("document_id"), str)
                    else None
                ),
                "review_required": (
                    state == "review_required"
                    or bool(row.get("review_required"))
                    or bool(row.get("changed_snapshot_sha256"))
                ),
                "retryable": (
                    state in {"authorized", "rejected"}
                    and not bool(row.get("changed_snapshot_sha256"))
                    and not bool(row.get("deleted"))
                ),
                "updated_at": str(row.get("approved_at") or row.get("created_at") or ""),
            })
        next_cursor = (
            self._cursor(scope, installation_id, views[-1]["order_id"])
            if len(found) > limit and views else None
        )
        return BlingOrderPage(rows=tuple(views), next_cursor=next_cursor, limit=limit)

    def list_jobs(
        self, scope: ExecutionScope, installation_id: str, *,
        offset: int = 0, limit: int = 50,
    ) -> dict[str, object]:
        self._bound(scope, installation_id)
        if (
            type(limit) is not int or not 1 <= limit <= 100
            or type(offset) is not int or not 0 <= offset <= 10_000
        ):
            raise BlingOperationalError("BLING_INVALID_CURSOR")
        with self.factory() as uow:
            rows = uow.outbox.list_for_scope(
                scope, limit=limit, offset=offset,
                operations=frozenset({PROCESS_ORDER, ISSUE_ORDER, PUBLISH_STATUS}),
            )
        return {
            "rows": [
                {
                    "entry_id": row.entry_id,
                    "operation": row.operation,
                    "status": row.status.value,
                    "attempt_count": row.attempt_count,
                    "available_at": row.available_at.isoformat(),
                }
                for row in rows
            ],
            "next_offset": offset + limit if len(rows) == limit else None,
        }

    def page_metrics(
        self, scope: ExecutionScope, installation_id: str, *,
        limit: int = 100,
    ) -> dict[str, object]:
        page = self.list_orders(scope, installation_id, limit=limit)
        jobs = self.list_jobs(scope, installation_id, limit=limit)
        order_states: dict[str, int] = {}
        for order in page.rows:
            order_states[order["state"]] = order_states.get(order["state"], 0) + 1
        job_states: dict[str, int] = {}
        job_rows = jobs["rows"]
        if isinstance(job_rows, list):
            for job in job_rows:
                if not isinstance(job, dict):
                    continue
                key = str(job.get("status", "unknown"))
                job_states[key] = job_states.get(key, 0) + 1
        return {
            "sample_limit": limit,
            "partial": page.next_cursor is not None or jobs["next_offset"] is not None,
            "order_states": order_states,
            "job_states": job_states,
            "has_dead_letter": job_states.get(FiscalOutboxStatus.DEAD_LETTER.value, 0) > 0,
        }

    @staticmethod
    def _request(request_id: str, actor_id: str, order_id: int) -> None:
        if (
            not request_id or len(request_id) > 128
            or not actor_id or len(actor_id) > 128
            or type(order_id) is not int or order_id <= 0
        ):
            raise BlingOperationalError("BLING_INPUT_INVALID")

    @staticmethod
    def _result(
        installation_id: str, order_id: int, request_id: str, operation_id: str,
        outcome: BlingRecoveryOutcome,
    ) -> BlingRecoveryResult:
        return BlingRecoveryResult(
            operation_id=operation_id,
            installation_id=installation_id,
            order_id=order_id,
            outcome=outcome,
            correlation_id=request_id,
        )

    def _provider_token(self, scope: ExecutionScope, view: BlingInstallationView) -> str:
        token = self.oauth.access_token(scope, view.installation_id)
        self._verify(token, view.company_id)
        return token

    def reconcile(
        self, scope: ExecutionScope, installation_id: str, order_id: int, *,
        request_id: str, actor_id: str,
    ) -> BlingRecoveryResult:
        self._request(request_id, actor_id, order_id)
        view = self._bound(scope, installation_id, active=True)
        orders = BlingOrders(self.factory, scope, view.company_id)
        current = orders.get(order_id)
        operation = hashlib.sha256(
            f"{installation_id}:recover:{order_id}:{request_id}".encode()
        ).hexdigest()
        if current is not None:
            result = (
                BlingRecoveryOutcome.REQUIRES_REVIEW
                if current.get("changed_snapshot_sha256") or current.get("review_required")
                else BlingRecoveryOutcome.ALREADY_RECORDED
            )
            return self._result(installation_id, order_id, request_id, operation, result)
        token = self._provider_token(scope, view)
        raw = self._fetch(order_id, token)
        # Re-read installation to reject revocation while the network call was pending.
        self._bound(scope, installation_id, active=True)
        if type(raw.get("id")) is not int or raw["id"] != order_id:
            raise BlingOperationalError("BLING_RECOVERY_REQUIRED")
        row = orders.stage(
            order_id, raw, event_id="operator-recovery:" + operation,
            now=datetime.now(UTC),
        )
        return self._result(
            installation_id, order_id, request_id, operation,
            BlingRecoveryOutcome.REQUIRES_REVIEW
            if row.get("state") == "review_required"
            else BlingRecoveryOutcome.ALREADY_RECORDED,
        )

    def retry_status(
        self, scope: ExecutionScope, installation_id: str, order_id: int, *,
        request_id: str, actor_id: str,
    ) -> BlingRecoveryResult:
        self._request(request_id, actor_id, order_id)
        orders = self._orders(scope, installation_id, active=True)
        # A successful/queued status must not be resent just because its
        # fiscal document is final. Retry only a proven dead-letter writeback.
        found = False
        with self.factory() as uow:
            for offset in range(0, 10_000, 100):
                entries = uow.outbox.list_for_scope(
                    scope, limit=100, offset=offset,
                    statuses=frozenset({FiscalOutboxStatus.DEAD_LETTER}),
                    operations=frozenset({PUBLISH_STATUS}),
                )
                for entry in entries:
                    try:
                        payload = json.loads(entry.payload)
                    except (ValueError, TypeError, UnicodeDecodeError):
                        continue
                    if (isinstance(payload, dict) and
                            payload.get("order_id") == order_id):
                        found = True
                        break
                if found or len(entries) < 100:
                    break
        if not found:
            raise BlingOperationalError("BLING_RECOVERY_REQUIRED")
        operation_id = orders.retry_status(
            order_id, request_id=request_id, actor_id=actor_id,
        )
        return self._result(
            installation_id, order_id, request_id, operation_id, BlingRecoveryOutcome.QUEUED,
        )

    def retry_event(
        self, scope: ExecutionScope, installation_id: str, entry_id: str, *,
        request_id: str, actor_id: str,
    ) -> str:
        if (
            not isinstance(entry_id, str) or len(entry_id) != 64
            or any(c not in "0123456789abcdef" for c in entry_id)
            or not request_id or len(request_id) > 128 or not actor_id
        ):
            raise BlingOperationalError("BLING_INPUT_INVALID")
        orders = self._orders(scope, installation_id, active=True)
        return orders.retry_event(entry_id, request_id=request_id, actor_id=actor_id)

    def search_orders(
        self, scope: ExecutionScope, installation_id: str, *,
        cursor: str | None = None, limit: int = 10,
    ) -> tuple[tuple[dict[str, object], ...], str | None]:
        view = self._bound(scope, installation_id, active=True)
        if type(limit) is not int or not 1 <= limit <= 20:
            raise BlingOperationalError("BLING_INVALID_LIMIT")
        page = 1
        if cursor is not None:
            if not cursor.startswith("page:") or not cursor[5:].isdigit():
                raise BlingOperationalError("BLING_INVALID_CURSOR")
            page = int(cursor[5:])
        if not 1 <= page <= 100_000:
            raise BlingOperationalError("BLING_INVALID_CURSOR")
        token = self._provider_token(scope, view)
        rows = self._search(page, limit, token)
        items: list[dict[str, object]] = []
        orders = BlingOrders(self.factory, scope, view.company_id)
        for row in rows:
            order_id = row["id"]
            if type(order_id) is not int or order_id <= 0:
                raise BlingOperationalError("BLING_RECOVERY_REQUIRED")
            present = orders.get(order_id) is not None
            items.append({"order_id": order_id, "recorded": present})
        return tuple(items), ("page:" + str(page + 1) if len(rows) == limit else None)

    def backfill_page(
        self, scope: ExecutionScope, installation_id: str, *,
        page: int, limit: int, request_id: str, actor_id: str,
    ) -> dict[str, object]:
        if (
            type(page) is not int or not 1 <= page <= 100_000
            or type(limit) is not int or not 1 <= limit <= 5
        ):
            raise BlingOperationalError("BLING_INPUT_INVALID")
        self._request(request_id, actor_id, 1)
        view = self._bound(scope, installation_id, active=True)
        orders = BlingOrders(self.factory, scope, view.company_id)
        token = self._provider_token(scope, view)
        # Rate limit is account-wide, not instance-wide; propagate 429 without
        # looping or pretending that a partial scan was fully reconciled.
        rows = self._search(page, limit, token)
        recovered = 0
        already_recorded = 0
        for row in rows:
            order_id = row.get("id")
            if type(order_id) is not int or order_id <= 0:
                raise BlingOperationalError("BLING_RECOVERY_REQUIRED")
            if orders.get(order_id) is not None:
                already_recorded += 1
                continue
            self._pause(0.36)
            raw = self._fetch(order_id, token)
            if type(raw.get("id")) is not int or raw["id"] != order_id:
                raise BlingOperationalError("BLING_RECOVERY_REQUIRED")
            self._bound(scope, installation_id, active=True)
            event_key = hashlib.sha256(
                f"{installation_id}:backfill:{order_id}:{request_id}".encode()
            ).hexdigest()
            orders.stage(
                order_id, raw, event_id="operator-backfill:" + event_key,
                now=datetime.now(UTC),
            )
            recovered += 1
        return {
            "examined": len(rows),
            "recovered": recovered,
            "already_recorded": already_recorded,
            "next_cursor": ("page:" + str(page + 1) if len(rows) == limit else None),
            "fiscal_issuance_started": False,
        }
