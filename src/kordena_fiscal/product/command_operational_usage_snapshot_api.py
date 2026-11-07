"""Read-only operational consumption/quota snapshot for the FM Command.

NFCore's own side of the "consumo operacional, franquias, quotas e telemetria"
contract (hybrid-architecture decision item 1). Companion to
``command_commercial_snapshot_api``: it wraps the exact same canonical
``fm_commercial_subscriptions`` rows, via
``CommandCommercialSnapshotReader.subscriptions()``, and projects out only the
quota/usage fields already persisted there (``quotas_json``/``usage_json``).
No new table, no new query, no second quota authority -- the commercial reader
remains the single place that touches this table.

Naming follows the same per-product convention already used for the commercial
contracts (``kordena.fmcc.commercial.v1``, ``iron.fmcc.commercial.v1``,
``nfcore.fmcc.commercial.v1``): ``nfcore.fmcc.operational-usage.v1``. There is no
single universal ``fmcc.saas.usage/v1`` schema reused here -- none exists in this
codebase or in the other FM SaaS repos under that name. The closest real analog is
IRON's own published read-model (``iron.fmcc.ai-usage.v1``, see IRON's
``AGENTS.md`` D9 and ``docs/D9_AI_EXECUTION_USAGE_COMMAND_READ_MODEL_2026-10-19.md``
in ``faabio3131/iron-fit-backend``): a per-product, read-only, server-to-server
usage snapshot that the product's own control-plane guard protects, where a metric
with no persisted measurement is reported as unavailable, never estimated as zero.
This module follows that same convention for NFCore.

Scope boundary: this is NFCore's own side only. The FM Command does not consume
this endpoint yet -- mirroring IRON's own current state, where the Command-side
wiring of its analogous contract was explicitly deferred by the product owner.
Building that consumption is a separate, explicitly authorized step.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from kordena_fiscal.product.command_commercial_snapshot_api import (
    CommandCommercialSnapshotReader,
)
from kordena_fiscal.security.s2s import FixedWindowRateLimiter

TOKEN_ENV = "NFCORE_COMMAND_OPERATIONAL_USAGE_CONTROL_PLANE_TOKEN"
MIN_TOKEN_LENGTH = 32
SCHEMA_VERSION = "nfcore.fmcc.operational-usage.v1"
PRODUCT_CODE = "NFCORE"


def _fail(status: int, code: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code})


class CommandOperationalUsageSnapshotReader:
    """Projects quota/usage facts out of the already-certified commercial rows.

    Takes a ``CommandCommercialSnapshotReader`` (not a raw connection) by
    construction: this reader never queries the database itself, it only
    reshapes rows the commercial reader already fetched and validated the
    shape of for its own envelope. A subscription without any configured
    quota is simply omitted -- never reported with a fabricated empty entry.
    """

    def __init__(self, commercial: CommandCommercialSnapshotReader) -> None:
        self._commercial = commercial

    @staticmethod
    def _metrics_for(quotas: object, usage: object) -> list[dict[str, object]]:
        if not isinstance(quotas, dict):
            return []
        used_map = usage if isinstance(usage, dict) else {}
        metrics: list[dict[str, object]] = []
        for metric_id, limit in quotas.items():
            if (
                not isinstance(metric_id, str)
                or not isinstance(limit, int)
                or isinstance(limit, bool)
            ):
                continue
            used = used_map.get(metric_id)
            has_measurement = isinstance(used, int) and not isinstance(used, bool)
            metrics.append(
                {
                    "metric_id": metric_id,
                    "limit": limit,
                    # Never an invented zero: absent measurement stays None and
                    # unavailable=True, same convention as IRON's unavailable_metrics.
                    "used": used if has_measurement else None,
                    "unavailable": not has_measurement,
                }
            )
        return metrics

    def consumption(self) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for sub in self._commercial.subscriptions():
            metrics = self._metrics_for(sub.get("quotas"), sub.get("usage"))
            if not metrics:
                continue
            rows.append(
                {
                    "subscription_id": sub["subscription_id"],
                    "tenant_id": sub["tenant_id"],
                    "plan_id": sub["plan_id"],
                    "status": sub["status"],
                    "metrics": metrics,
                }
            )
        return rows

    def snapshot(self, *, as_of: datetime) -> dict[str, object]:
        consumption = self.consumption()
        total_metrics = 0
        unavailable_metrics = 0
        for row in consumption:
            metrics_obj = row["metrics"]
            assert isinstance(metrics_obj, list)
            total_metrics += len(metrics_obj)
            for metric in metrics_obj:
                assert isinstance(metric, dict)
                if metric["unavailable"]:
                    unavailable_metrics += 1
        summary = {
            "subscriptions_with_quotas": len(consumption),
            "metrics_reported": total_metrics,
            "metrics_unavailable": unavailable_metrics,
        }
        clean_payload = {"as_of": as_of.isoformat(), **summary}
        stable_id = hashlib.sha256(
            json.dumps(clean_payload, sort_keys=True).encode("utf-8")
        ).hexdigest()
        return {
            "schema_version": SCHEMA_VERSION,
            "product_code": PRODUCT_CODE,
            "as_of": as_of.isoformat(),
            "consumption": consumption,
            "summary": summary,
            "facts": [
                {
                    "external_id": "nfcore-operational-usage-v1:" + stable_id,
                    "fact_type": "nfcore.operational_usage.snapshot",
                    "payload": clean_payload,
                    "source_timestamp": as_of.isoformat(),
                }
            ],
        }


def create_command_operational_usage_snapshot_router(
    reader: CommandOperationalUsageSnapshotReader | None,
    environ: Mapping[str, str],
    *,
    rate_limiter: FixedWindowRateLimiter | None = None,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> APIRouter:
    """Always mounted; fails closed per-request when the reader isn't wired.

    Same rationale already proven for the commercial and cognitive Command
    routes: a route that disappears from the real app composition whenever a
    dependency is absent looks identical to a config bug from Command's side.
    """
    router = APIRouter(tags=["command-operational-usage-snapshot"])
    limiter = rate_limiter or FixedWindowRateLimiter(max_requests=60, window_seconds=60)

    @router.get("/v1/command/operational-usage/snapshot")
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
        if not limiter.allow("command-operational-usage-snapshot", now):
            raise _fail(429, "COMMAND_RATE_LIMITED")
        if reader is None:
            raise _fail(503, "COMMAND_OPERATIONAL_USAGE_NOT_CONFIGURED")
        body: dict[str, Any] = {
            "correlationId": correlation_id,
            "provenance": {"authority": "nfcore-operational-usage-core", "readOnly": True},
            **reader.snapshot(as_of=now),
        }
        return JSONResponse(body, headers={"Cache-Control": "no-store, max-age=0"})

    return router
