"""Read-only commercial snapshot endpoint for the FM Command (product -> Command).

Mirrors the schema already used by other FM products for this exact purpose
(``<product>.fmcc.commercial.v1``, e.g. Kordena's ``KordenaCommercialSnapshot`` on the
Command side): ``customers``, ``product_accounts``, ``trials``, ``subscriptions``,
``billing_transactions``, ``entitlements`` and ``catalog``. Same auth pattern already
proven for the cognitive Command route (``kordena_fiscal.cognitive.command_api``): a
dedicated per-domain control-plane token, mandatory correlation id, no-store caching,
rate limiting and a provenance envelope.

Scope boundary (NFCore -> Command "domínio comercial" per FM-CONTROL-CENTER AGENTS.md):
this endpoint reports NFCore's own operational/commercial records -- purchases,
subscriptions, quotas, entitlements -- never a computed MRR/ARR, never an invoice, and
never treats itself as the financial authority. Amount fields are deliberately absent
from ``billing_transactions``; the Command/gateway ledger remains the sole authority for
money. Reading plans.json uses the same validated parser as the rest of the product
(``read_candidate``), never hand-parsed JSON, and reports only entries whose own
``status`` field in the file says ``published`` -- never a status invented here.
"""

from __future__ import annotations

import hmac
import json
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from kordena_fiscal.persistence.commercial_fulfillment import ConnectionContextFactory
from kordena_fiscal.product.commercial_plan_candidate import read_candidate
from kordena_fiscal.security.s2s import FixedWindowRateLimiter

TOKEN_ENV = "NFCORE_COMMAND_COMMERCIAL_CONTROL_PLANE_TOKEN"
MIN_TOKEN_LENGTH = 32
SCHEMA_VERSION = "nfcore.fmcc.commercial.v1"
PRODUCT_CODE = "NFCORE"
_DEFAULT_CATALOG_PATH = Path.cwd() / "config" / "commercial" / "plans.json"
_MAX_ROWS = 200


def _fail(status: int, code: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code})


class CommandCommercialSnapshotReader:
    """Bounded, read-only aggregation over the existing commercial tables.

    Every query is a plain, parameterless-filter ``SELECT ... LIMIT`` against tables
    already certified by ``kordena_fiscal.persistence.commercial_fulfillment`` and
    ``kordena_fiscal.persistence.postgres``. No write, no cross-tenant filter bypass,
    no second billing authority: subscriptions/entitlements/quotas are reported as
    persisted; trials are the real ``status='trial'`` rows of
    ``fm_commercial_subscriptions`` (``SubscriptionStatus.TRIAL``), not a separate
    invented concept.
    """

    def __init__(self, acquire: ConnectionContextFactory, *, limit: int = _MAX_ROWS) -> None:
        if not 1 <= limit <= _MAX_ROWS:
            raise ValueError("snapshot row budget out of range")
        self._acquire = acquire
        self._limit = limit

    def _rows(self, sql: str, params: tuple[object, ...] = ()) -> list[Sequence[Any]]:
        with self._acquire() as connection:
            connection.execute("SET LOCAL statement_timeout = '2s'")
            return list(connection.execute(sql, params).fetchall())

    def customers(self) -> list[dict[str, object]]:
        rows = self._rows(
            "SELECT DISTINCT tenant_id, buyer_email FROM fm_commercial_purchases "
            "WHERE tenant_id IS NOT NULL ORDER BY tenant_id LIMIT ?",
            (self._limit,),
        )
        return [{"tenant_id": r[0], "buyer_email": r[1]} for r in rows]

    def product_accounts(self) -> list[dict[str, object]]:
        rows = self._rows(
            "SELECT DISTINCT account_id, tenant_id FROM fm_commercial_purchases "
            "WHERE account_id IS NOT NULL ORDER BY account_id LIMIT ?",
            (self._limit,),
        )
        return [{"account_id": r[0], "tenant_id": r[1]} for r in rows]

    def _subscriptions(self, *, status: str | None) -> list[dict[str, object]]:
        if status is None:
            rows = self._rows(
                "SELECT subscription_id, tenant_id, plan_id, status, period_start, "
                "period_end, entitlement_ids_json, quotas_json, usage_json "
                "FROM fm_commercial_subscriptions ORDER BY subscription_id LIMIT ?",
                (self._limit,),
            )
        else:
            rows = self._rows(
                "SELECT subscription_id, tenant_id, plan_id, status, period_start, "
                "period_end, entitlement_ids_json, quotas_json, usage_json "
                "FROM fm_commercial_subscriptions WHERE status = ? "
                "ORDER BY subscription_id LIMIT ?",
                (status, self._limit),
            )
        return [
            {
                "subscription_id": r[0],
                "tenant_id": r[1],
                "plan_id": r[2],
                "status": r[3],
                "period_start": r[4],
                "period_end": r[5],
                "entitlement_ids": json.loads(str(r[6])),
                "quotas": json.loads(str(r[7])),
                "usage": json.loads(str(r[8])),
            }
            for r in rows
        ]

    def subscriptions(self) -> list[dict[str, object]]:
        return self._subscriptions(status=None)

    def trials(self) -> list[dict[str, object]]:
        return self._subscriptions(status="trial")

    def entitlements(self) -> list[dict[str, object]]:
        seen: dict[str, dict[str, object]] = {}
        for row in self._subscriptions(status=None):
            entitlement_ids = row["entitlement_ids"]
            assert isinstance(entitlement_ids, list)
            for entitlement_id in entitlement_ids:
                seen.setdefault(
                    str(entitlement_id),
                    {
                        "entitlement_id": entitlement_id,
                        "subscription_id": row["subscription_id"],
                        "tenant_id": row["tenant_id"],
                        "plan_id": row["plan_id"],
                    },
                )
        return list(seen.values())

    def billing_transactions(self) -> list[dict[str, object]]:
        """Non-monetary purchase/event facts only -- never an amount or an invoice.

        The gateway/Command ledger is the financial authority; this reports which
        purchase reached which state and when, for operational correlation only.
        """
        rows = self._rows(
            "SELECT purchase_id, provider_id, state, last_event_id, last_event_at, "
            "tenant_id FROM fm_commercial_purchases ORDER BY last_event_at DESC LIMIT ?",
            (self._limit,),
        )
        return [
            {
                "purchase_id": r[0],
                "provider_id": r[1],
                "state": r[2],
                "last_event_id": r[3],
                "last_event_at": r[4],
                "tenant_id": r[5],
            }
            for r in rows
        ]

    def catalog(self, *, path: Path = _DEFAULT_CATALOG_PATH) -> list[dict[str, object]]:
        try:
            candidate = read_candidate(path)
        except Exception:  # noqa: BLE001 - absence of a readable file is not fatal here
            return []
        plans = candidate.get("plans")
        if not isinstance(plans, dict):
            return []
        catalog_status = candidate.get("status")
        if catalog_status != "published":
            return []
        return [
            {"plan_id": plan_id, "definition": definition}
            for plan_id, definition in plans.items()
            if isinstance(definition, dict)
        ]

    def snapshot(self, *, as_of: datetime) -> dict[str, object]:
        return {
            "schema_version": SCHEMA_VERSION,
            "product_code": PRODUCT_CODE,
            "as_of": as_of.isoformat(),
            "customers": self.customers(),
            "product_accounts": self.product_accounts(),
            "trials": self.trials(),
            "subscriptions": self.subscriptions(),
            "billing_transactions": self.billing_transactions(),
            "entitlements": self.entitlements(),
            "catalog": self.catalog(),
        }


def create_command_commercial_snapshot_router(
    reader: CommandCommercialSnapshotReader | None,
    environ: Mapping[str, str],
    *,
    rate_limiter: FixedWindowRateLimiter | None = None,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> APIRouter:
    """Always mounted; fails closed per-request when the reader isn't wired.

    Mirrors the cognitive Command route's lesson: a route that disappears from the
    real app composition whenever a dependency is absent looks identical to a config
    bug from Command's side. ``reader=None`` (e.g. no PostgreSQL composition) yields a
    clear ``COMMAND_COMMERCIAL_NOT_CONFIGURED`` 503, never a 404.
    """
    router = APIRouter(tags=["command-commercial-snapshot"])
    limiter = rate_limiter or FixedWindowRateLimiter(max_requests=60, window_seconds=60)

    @router.get("/v1/command/commercial/snapshot")
    async def snapshot(request: Request) -> JSONResponse:
        token = environ.get(TOKEN_ENV, "")
        if len(token) < MIN_TOKEN_LENGTH:
            raise _fail(503, "COMMAND_CONTROL_PLANE_NOT_CONFIGURED")
        header = request.headers.get("Authorization", "")
        presented = header[7:] if header.lower().startswith("bearer ") else ""
        if not hmac.compare_digest(presented.encode(), token.encode()):
            raise _fail(401, "COMMAND_AUTHENTICATION_FAILED")
        correlation_id = request.headers.get("X-Correlation-Id", "").strip()
        if not correlation_id or len(correlation_id) > 128:
            raise _fail(400, "CORRELATION_ID_REQUIRED")
        now = clock()
        if not limiter.allow("command-commercial-snapshot", now):
            raise _fail(429, "COMMAND_RATE_LIMITED")
        if reader is None:
            raise _fail(503, "COMMAND_COMMERCIAL_NOT_CONFIGURED")
        body: dict[str, Any] = {
            "correlationId": correlation_id,
            "provenance": {"authority": "nfcore-commercial-core", "readOnly": True},
            **reader.snapshot(as_of=now),
        }
        return JSONResponse(body, headers={"Cache-Control": "no-store, max-age=0"})

    return router
