"""Container-facing API assembly with infrastructure readiness checks."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from kordena_fiscal.persistence.postgres import PostgresFiscalDatabase
from kordena_fiscal.web.app import create_app

from .config import RuntimeSettings


class RuntimeApi:
    def __init__(self, settings: RuntimeSettings) -> None:
        self.settings = settings
        self.database: PostgresFiscalDatabase | None = None
        if settings.persistence_backend == "postgres":
            assert settings.database_url is not None
            self.database = PostgresFiscalDatabase(settings.database_url)
            self.database.initialize()

    def ready(self) -> tuple[bool, str]:
        if self.settings.persistence_backend == "postgres":
            if self.database is None:
                return False, "database_not_initialized"
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


def create_runtime_app(settings: RuntimeSettings | None = None) -> FastAPI:
    resolved = settings or RuntimeSettings.from_environ()
    runtime = RuntimeApi(resolved)
    app = FastAPI(title="FM NFCORE Runtime", version="1.0.0")
    app.state.nfcore_runtime = runtime

    @app.get("/health/live", tags=["health"])
    async def live() -> dict[str, str]:
        return {"status": "live", "product": "FM NFCORE"}

    @app.get("/health/ready", tags=["health"])
    async def ready() -> JSONResponse:
        healthy, reason = runtime.ready()
        return JSONResponse(
            status_code=200 if healthy else 503,
            content={"status": "ready" if healthy else "not_ready", "reason": reason},
        )

    @app.get("/runtime/profile", tags=["health"])
    async def profile() -> dict[str, object]:
        return {
            "environment": resolved.environment.value,
            "persistence_backend": resolved.persistence_backend,
            "secret_backend_profile": resolved.secret_backend,
            "https_required": resolved.require_https,
            "fiscal_production_activated": False,
        }

    @app.on_event("shutdown")
    async def close_runtime() -> None:
        runtime.close()

    # The existing bridge remains fail-closed because no fiscal authority/provider
    # adapter is invented by the container packaging work package.
    app.mount("/", create_app())
    return app


app = create_runtime_app()
