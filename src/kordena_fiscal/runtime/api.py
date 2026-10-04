"""Container-facing API assembly with infrastructure readiness and observability."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from kordena_fiscal.application.commercial_acquisition import CommercialAcquisitionService
from kordena_fiscal.gateway.production_activation import ProductionExecutionAuthority
from kordena_fiscal.persistence.commercial_fulfillment import (
    postgres_canonical_commercial_database,
)
from kordena_fiscal.persistence.postgres import PostgresFiscalDatabase
from kordena_fiscal.product.cakto import CaktoWebhookReceiver
from kordena_fiscal.product.checkout import (
    CommercialCheckoutProjector,
    CommercialCheckoutStarter,
)
from kordena_fiscal.product.commercial_readiness import CommercialDeliveryPathReadiness
from kordena_fiscal.security.s2s import FixedWindowRateLimiter, WebhookSecurity
from kordena_fiscal.web.app import create_app
from kordena_fiscal.web.commercial_acquisition import (
    create_commercial_acquisition_router,
)
from kordena_fiscal.web.commercial_trial import create_commercial_trial_router
from kordena_fiscal.web.human_recovery import PasswordResetDelivery
from kordena_fiscal.web.portal_runtime import PortalOperationExecutor

from .activation_email import build_activation_delivery_from_environ
from .cakto import build_cakto_webhook_router
from .composition import RuntimeComposition, build_postgres_runtime_composition
from .config import RuntimeSettings
from .observability import MetricsRegistry, RequestTimer, StructuredLogger
from .security import configure_edge_security


class RuntimeApi:
    def __init__(
        self,
        settings: RuntimeSettings,
        *,
        portal_operation_executor: PortalOperationExecutor | None = None,
    ) -> None:
        self.settings = settings
        self.database: PostgresFiscalDatabase | None = None
        self.composition: RuntimeComposition | None = None
        self._database_boot_error = False
        self._composition_boot_error = False
        if settings.persistence_backend == "postgres":
            assert settings.database_url is not None
            try:
                database = PostgresFiscalDatabase(settings.database_url)
                database.initialize()
            except Exception:
                self._database_boot_error = True
            else:
                self.database = database
                try:
                    self.composition = build_postgres_runtime_composition(
                        database,
                        portal_operation_executor=portal_operation_executor,
                        enable_cakto_checkout=(
                            settings.commercial_checkout_provider == "cakto"
                        ),
                        password_reset_ttl=timedelta(
                            minutes=settings.password_reset_ttl_minutes
                        ),
                    )
                except Exception:
                    self._composition_boot_error = True

    def ready(self) -> tuple[bool, str]:
        if self.settings.persistence_backend == "postgres":
            if self._database_boot_error or self.database is None:
                return False, "database_unavailable"
            if self._composition_boot_error or self.composition is None:
                return False, "composition_unavailable"
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
    commercial_checkout_projector: CommercialCheckoutProjector | None = None,
    commercial_checkout_starter: CommercialCheckoutStarter | None = None,
    commercial_checkout_processing_configured: bool = False,
    commercial_acquisition_security: WebhookSecurity | None = None,
    commercial_acquisition_rate_limiter: FixedWindowRateLimiter | None = None,
    commercial_trial_security: WebhookSecurity | None = None,
    commercial_trial_rate_limiter: FixedWindowRateLimiter | None = None,
    password_reset_delivery: PasswordResetDelivery | None = None,
    production_authority: ProductionExecutionAuthority | None = None,
    portal_operation_executor: PortalOperationExecutor | None = None,
) -> FastAPI:
    resolved = settings or RuntimeSettings.from_environ()
    runtime = RuntimeApi(
        resolved,
        portal_operation_executor=portal_operation_executor,
    )
    runtime_metrics = metrics or MetricsRegistry()
    runtime_logger = logger or StructuredLogger(
        service="nfcore-api",
        environment=resolved.environment.value,
    )
    composition = runtime.composition
    selected_checkout = commercial_checkout_projector
    selected_checkout_starter = commercial_checkout_starter
    selected_checkout_processing = commercial_checkout_processing_configured
    if (
        selected_checkout is None
        and resolved.commercial_checkout_provider == "cakto"
        and composition is not None
        and composition.cakto_checkout_administration is not None
    ):
        selected_checkout = composition.cakto_checkout_administration
        selected_checkout_starter = composition.cakto_checkout_administration
        selected_checkout_processing = cakto_receiver is not None
    if (
        selected_checkout is not None
        and resolved.commercial_checkout_provider is not None
        and selected_checkout.provider_id != resolved.commercial_checkout_provider
    ):
        selected_checkout = None
        selected_checkout_starter = None
        selected_checkout_processing = False

    commercial_delivery_readiness = CommercialDeliveryPathReadiness(
        canonical_commercial_persistence=(
            composition is not None and runtime.database is not None
        ),
        fulfillment=composition is not None,
        provisioning=composition is not None,
        activation_delivery=(
            composition is not None and password_reset_delivery is not None
        ),
    )

    commercial_acquisition: CommercialAcquisitionService | None = None
    if (
        composition is not None
        and runtime.database is not None
        and selected_checkout is not None
        and selected_checkout_starter is not None
        and commercial_acquisition_security is not None
        and selected_checkout.provider_id == selected_checkout_starter.provider_id
    ):
        commercial_acquisition = CommercialAcquisitionService(
            unit_of_work_factory=postgres_canonical_commercial_database(
                runtime.database
            ),
            pricing=composition.pricing_administration,
            release=composition.commercial_release_administration,
            checkout=selected_checkout,
            checkout_starter=selected_checkout_starter,
            checkout_processing_configured=selected_checkout_processing,
            delivery_readiness=commercial_delivery_readiness,
        )

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            runtime.close()

    app = FastAPI(title="FM NFCORE Runtime", version="1.0.0", lifespan=lifespan)
    app.state.nfcore_runtime = runtime
    app.state.nfcore_runtime_composition = composition
    app.state.nfcore_password_recovery = (
        None if composition is None else composition.password_recovery
    )
    app.state.nfcore_password_reset_delivery = password_reset_delivery
    app.state.nfcore_commercial_activation = (
        None if composition is None else composition.commercial_activation
    )
    app.state.nfcore_commercial_acquisition = commercial_acquisition
    app.state.nfcore_commercial_trial = (
        None if composition is None else composition.commercial_trial
    )
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
            "human_identity_configured": composition is not None,
            "portal_executor_configured": composition is not None,
            "password_recovery_configured": composition is not None,
            "password_reset_delivery_configured": password_reset_delivery is not None,
            "commercial_activation_configured": (
                composition is not None
                and composition.commercial_activation is not None
            ),
            "pricing_admin_configured": pricing_administration is not None,
            "pricing_catalog_published": (
                pricing_administration is not None
                and pricing_administration.current is not None
            ),
            "commercial_release_admin_configured": (
                commercial_release_administration is not None
            ),
            "commercial_release_status": (
                "unavailable"
                if commercial_release_administration is None
                or commercial_release_administration.current is None
                else commercial_release_administration.current.status.value
            ),
            "commercial_checkout_provider_configured": (
                resolved.commercial_checkout_provider
            ),
            "commercial_checkout_provider_active": (
                None if selected_checkout is None else selected_checkout.provider_id
            ),
            "commercial_checkout_status": (
                "unconfigured"
                if selected_checkout is None
                else selected_checkout.project(
                    None
                    if pricing_administration is None
                    else pricing_administration.current
                ).status.value
            ),
            "commercial_checkout_processing_configured": (
                selected_checkout_processing
            ),
            "canonical_commercial_persistence_configured": (
                commercial_delivery_readiness.canonical_commercial_persistence
            ),
            "commercial_fulfillment_configured": (
                commercial_delivery_readiness.fulfillment
            ),
            "commercial_provisioning_configured": (
                commercial_delivery_readiness.provisioning
            ),
            "commercial_activation_delivery_configured": (
                commercial_delivery_readiness.activation_delivery
            ),
            "commercial_delivery_path_ready": commercial_delivery_readiness.ready,
            "commercial_first_party_acquisition_configured": (
                commercial_acquisition is not None
            ),
            "commercial_trial_configured": (
                composition is not None
                and commercial_trial_security is not None
                and password_reset_delivery is not None
            ),
            "cakto_checkout_admin_configured": (
                cakto_checkout_administration is not None
            ),
            "cakto_checkout_status": (
                "unconfigured"
                if cakto_checkout_administration is None
                else cakto_checkout_administration.project(
                    None
                    if pricing_administration is None
                    else pricing_administration.current
                ).status.value
            ),
            "fiscal_production_activated": active_grants > 0,
            "fiscal_production_active_grants": active_grants,
            "cakto_webhook_configured": cakto_receiver is not None,
        }

    if cakto_receiver is not None:
        app.include_router(build_cakto_webhook_router(cakto_receiver))

    if commercial_acquisition is not None and commercial_acquisition_security is not None:
        app.include_router(
            create_commercial_acquisition_router(
                commercial_acquisition,
                security=commercial_acquisition_security,
                rate_limiter=(
                    commercial_acquisition_rate_limiter
                    or FixedWindowRateLimiter(
                        max_requests=30,
                        window_seconds=60,
                    )
                ),
            )
        )

    if (
        composition is not None
        and commercial_trial_security is not None
        and password_reset_delivery is not None
    ):
        app.include_router(
            create_commercial_trial_router(
                composition.commercial_trial,
                security=commercial_trial_security,
                rate_limiter=(
                    commercial_trial_rate_limiter
                    or FixedWindowRateLimiter(
                        max_requests=10,
                        window_seconds=3600,
                    )
                ),
                delivery=password_reset_delivery,
            )
        )

    human_identity = None if composition is None else composition.human_identity
    password_recovery = None if composition is None else composition.password_recovery
    portal_executor = None if composition is None else composition.portal_executor
    pricing_administration = (
        None if composition is None else composition.pricing_administration
    )
    commercial_release_administration = (
        None
        if composition is None
        else composition.commercial_release_administration
    )
    cakto_checkout_administration = (
        None
        if composition is None
        else composition.cakto_checkout_administration
    )
    def mark_commercial_active(account_id: str, now: datetime) -> None:
        if composition is None:
            return
        composition.commercial_activation.mark_active(account_id=account_id, now=now)

    commercial_activation_completed = (
        None if composition is None else mark_commercial_active
    )

    # Fiscal production stays false unless a governed authority is explicitly injected.
    app.mount(
        "/",
        create_app(
            human_identity=human_identity,
            human_login_completed=commercial_activation_completed,
            password_recovery=password_recovery,
            password_reset_delivery=password_reset_delivery,
            password_reset_completed=commercial_activation_completed,
            portal_executor=portal_executor,
            pricing_administration=pricing_administration,
            commercial_release_administration=commercial_release_administration,
            commercial_checkout=selected_checkout,
            commercial_checkout_processing_configured=(
                selected_checkout_processing
            ),
            commercial_delivery_readiness=commercial_delivery_readiness,
            cakto_checkout_administration=cakto_checkout_administration,
        ),
    )
    return app


app = create_runtime_app(
    password_reset_delivery=build_activation_delivery_from_environ(),
)
