"""Container-facing API assembly with infrastructure readiness and observability."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from kordena_fiscal.gateway.production_activation import ProductionExecutionAuthority
from kordena_fiscal.persistence.postgres import PostgresFiscalDatabase
from kordena_fiscal.product.cakto import CaktoWebhookReceiver
from kordena_fiscal.web.app import create_app

from .cakto import build_cakto_webhook_router
from .config import RuntimeSettings
from .observability import MetricsRegistry, RequestTimer, StructuredLogger
from .security import configure_edge_security


class RuntimeApi:
    def __init__(self, settings: RuntimeSettings) -> None:
        self.settings = settings
        self.database: PostgresFiscalDatabase | None = None
        self._database_boot_error = False
        if settings.persistence_backend == "postgres":
            assert settings.database_url is not None
            try:
                database = PostgresFiscalDatabase(settings.database_url)
                database.initialize()
                self.database = database
            except Exception:
                self._database_boot_error = True

    def ready(self) -> tuple[bool, str]:
        if self.settings.persistence_backend == "postgres":
            if self._database_boot_error or self.database is None:
                return False, "database_unavailable"
            try:
                with self.database.connection() as connection:
                    connection.execute("SELECT 1").fetchone()
                if not self.database.applied_migrations():
                    return False, "schema_not_initialized"
            except Exception:
                return False, "database_unavailable"
        return True, "ready"

    def close(self) -> None:
        if self.database is not None:
            self.database.close()


def create_runtime_app(
    settings: RuntimeSettings | None = None,
    *,
    metrics: MetricsRegistry | None = None,
    logger: StructuredLogger | None = None,
    cakto_receiver: CaktoWebhookReceiver | None = None,
    production_authority: ProductionExecutionAuthority | None = None,
) -> FastAPI:
    resolved = settings or RuntimeSettings.from_environ()
    runtime = RuntimeApi(resolved)
    runtime_metrics = metrics or MetricsRegistry()
    runtime_logger = logger or StructuredLogger(
        service="nfcore-api",
        environment=resolved.environment.value,
    )

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            runtime.close()

    app = FastAPI(title="FM NFCORE Runtime", version="1.0.0", lifespan=lifespan)
    app.state.nfcore_runtime = runtime
    app.state.nfcore_metrics = runtime_metrics
    app.state.nfcore_logger = runtime_logger
    app.state.nfcore_production_authority = production_authority
    configure_edge_security(app, resolved)

    @app.middleware("http")
    async def observe_request(request: Request, call_next):  # type: ignore[no-untyped-def]
        timer = RequestTimer()
        correlation_id = request.headers.get("X-Correlation-Id", "").strip() or uuid4().hex
        causation_id = request.headers.get("X-Causation-Id", "").strip() or None
        try:
            response = await call_next(request)
            status_code = response.status_code
            outcome = "success" if status_code < 500 else "server_error"
        except Exception as exc:
            elapsed = timer.elapsed()
            runtime_metrics.increment(
                "nfcore_http_requests_total",
                method=request.method,
                status_class="5xx",
            )
            runtime_metrics.observe_seconds(
                "nfcore_http_request",
                elapsed,
                method=request.method,
                status_class="5xx",
            )
            runtime_logger.emit(
                "ERROR",
                "http_request_failed",
                request_id=correlation_id,
                correlation_id=correlation_id,
                causation_id=causation_id,
                method=request.method,
                path=request.url.path,
                duration_seconds=elapsed,
                error_type=type(exc).__name__,
            )
            raise
        elapsed = timer.elapsed()
        status_class = f"{status_code // 100}xx"
        runtime_metrics.increment(
            "nfcore_http_requests_total",
            method=request.method,
            status_class=status_class,
        )
        runtime_metrics.observe_seconds(
            "nfcore_http_request",
            elapsed,
            method=request.method,
            status_class=status_class,
        )
        runtime_logger.emit(
            "INFO",
            "http_request_completed",
            request_id=correlation_id,
            correlation_id=correlation_id,
            causation_id=causation_id,
            method=request.method,
            path=request.url.path,
            status_code=status_code,
            result=outcome,
            duration_seconds=elapsed,
        )
        response.headers["X-Correlation-Id"] = correlation_id
        return response

    @app.get("/health/live", tags=["health"])
    async def live() -> dict[str, str]:
        return {"status": "live", "product": "FM NFCORE"}

    @app.get("/health/ready", tags=["health"])
    async def ready() -> JSONResponse:
        healthy, reason = runtime.ready()
        runtime_metrics.increment(
            "nfcore_dependency_checks_total",
            service="postgres" if resolved.persistence_backend == "postgres" else "sqlite",
            outcome="ready" if healthy else "not_ready",
        )
        return JSONResponse(
            status_code=200 if healthy else 503,
            content={"status": "ready" if healthy else "not_ready", "reason": reason},
        )

    @app.get("/internal/metrics", tags=["operability"])
    async def metric_snapshot() -> dict[str, object]:
        return {"metrics": runtime_metrics.as_dicts()}

    @app.get("/runtime/profile", tags=["health"])
    async def profile() -> dict[str, object]:
        active_grants = 0 if production_authority is None else production_authority.active_count
        return {
            "environment": resolved.environment.value,
            "persistence_backend": resolved.persistence_backend,
            "secret_backend_profile": resolved.secret_backend,
            "https_required": resolved.require_https,
            "public_hostname_configured": resolved.public_hostname is not None,
            "trusted_proxy_networks_configured": len(resolved.trusted_proxy_cidrs),
            "fiscal_production_activated": active_grants > 0,
            "fiscal_production_active_grants": active_grants,
            "cakto_webhook_configured": cakto_receiver is not None,
        }

    if cakto_receiver is not None:
        app.include_router(build_cakto_webhook_router(cakto_receiver))

    # Fiscal production stays false unless a governed authority is explicitly injected.
    app.mount("/", create_app())
    return app


app = create_runtime_app()
