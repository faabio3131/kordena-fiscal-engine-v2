"""Multi-installation Bling Worker over the canonical outbox and scoped claims.

This is a scheduler of existing handlers, not a second fiscal executor/queue.
Every iteration re-reads installation authority, OAuth state and runtime settings.
"""
from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from threading import Event

from kordena_fiscal.application.background_runtime import BackgroundCycleResult
from kordena_fiscal.application.service import FiscalApplicationService
from kordena_fiscal.contingency.outbox import FiscalOutboxStatus
from kordena_fiscal.integrations.bling_contracts import (
    BlingInstallationState,
    BlingInstallationView,
)
from kordena_fiscal.persistence.bling_installations import (
    BlingInstallationRepository,
)
from kordena_fiscal.persistence.bling_runtime_settings import (
    BlingRuntimeSettingsRepository,
)
from kordena_fiscal.persistence.postgres import PostgresFiscalDatabase

from .bling_oauth_factory import build_bling_oauth_service
from .bling_oauth_service import BlingOAuthService
from .bling_worker import build_bling_worker
from .config import RuntimeConfigurationError, RuntimeEnvironment, RuntimeSettings
from .observability import (
    MetricsRegistry,
    StructuredLogger,
    WorkerHealth,
    WorkerObservability,
)
from .worker_composition import (
    ProductionWorkerComposition,
    build_production_worker_runtime,
)

BLING_MULTI_MODE = "bling-multi"


class BlingMultiInstallationWorkerComposition:
    """Fair bounded round robin across *authorized* installations.

    No tenant authority comes from jobs, callback query, or generic environment
    variables. A stale/paused installation is re-checked before each claim.
    """

    def __init__(
        self,
        database: PostgresFiscalDatabase,
        environ: Mapping[str, str],
        installations: BlingInstallationRepository,
        oauth: BlingOAuthService,
    ) -> None:
        self._db = database
        self._source = environ
        self._installations = installations
        self._oauth = oauth
        self._settings = BlingRuntimeSettingsRepository(database, installations)
        self._observer = WorkerObservability(
            metrics=MetricsRegistry(),
            logger=StructuredLogger(service="nfcore-bling-worker", environment="production"),
            queue_counts=self._counts,
        )
        if not self._installations.scan_connected(limit=1):
            raise RuntimeConfigurationError("Bling has no connected installation")

    def _counts(self) -> Mapping[FiscalOutboxStatus, int]:
        with self._db() as uow:
            return uow.outbox.counts_by_status()

    def health(self) -> WorkerHealth:
        return self._observer.health()

    def _scoped(self, view: BlingInstallationView) -> ProductionWorkerComposition:
        host = self._installations.host_binding(view.installation_id)
        if host is None:
            raise RuntimeConfigurationError("Bling fiscal binding is unavailable")
        scope = FiscalApplicationService(self._db).resolve_scope(
            host, environment=view.environment,
            correlation_id="bling-multi-dispatch",
        )
        if (
            scope.tenant_id != view.tenant_id
            or scope.unit_id != view.unit_id
            or scope.environment is not view.environment
            or scope.host_namespace != "bling"
        ):
            raise RuntimeConfigurationError("Bling installation binding drift")
        current = self._installations.get_for_scope(scope, view.installation_id)
        if current is None or current.state is not BlingInstallationState.CONNECTED:
            raise RuntimeConfigurationError("Bling installation no longer connected")

        local = dict(self._source)
        # No global single-company status IDs, token or fiscal policy may
        # silently bleed into a different installation's work queue.
        for key in (
            "NFCORE_BLING_ACCESS_TOKEN_FILE",
            "NFCORE_BLING_AUTHORIZED_STATUS_ID",
            "NFCORE_BLING_REJECTED_STATUS_ID",
            "NFCORE_BLING_FISCAL_POLICY_FILE",
            "NFCORE_BLING_FISCAL_POLICY_SHA256",
        ):
            local.pop(key, None)
        local.update({
            "NFCORE_BLING_COMPANY_ID": view.company_id,
            "NFCORE_BLING_TENANT_ID": host.tenant_id,
            "NFCORE_BLING_UNIT_ID": host.unit_id,
            "NFCORE_BLING_ENVIRONMENT": view.environment.value,
        })
        config = self._settings.get(scope, view.installation_id)
        if config is not None:
            if (
                config.authorized_status_id is not None
                and config.rejected_status_id is not None
            ):
                local["NFCORE_BLING_AUTHORIZED_STATUS_ID"] = str(
                    config.authorized_status_id
                )
                local["NFCORE_BLING_REJECTED_STATUS_ID"] = str(config.rejected_status_id)
            if config.fiscal_policy_sha256:
                policy_root = self._source.get("NFCORE_BLING_POLICY_MOUNT", "")
                if policy_root != "/run/nfcore/bling/policies":
                    raise RuntimeConfigurationError("Bling fiscal policy mount is untrusted")
                local["NFCORE_BLING_FISCAL_POLICY_FILE"] = (
                    policy_root + "/" + view.installation_id + ".json"
                )
                local["NFCORE_BLING_FISCAL_POLICY_SHA256"] = config.fiscal_policy_sha256

        def validate_installation() -> None:
            fresh = self._installations.get_for_scope(scope, view.installation_id)
            if fresh is None or fresh.state is not BlingInstallationState.CONNECTED:
                raise RuntimeConfigurationError("Bling installation authorization revoked")

        handlers = build_bling_worker(
            self._db, local,
            token_provider=lambda: self._oauth.access_token(scope, view.installation_id),
            installation_validator=validate_installation,
        )
        return build_production_worker_runtime(
            uow_factory=self._db,
            handlers=handlers.handlers,
            environment="production",
            batch_size=1,
            claim_selection=handlers.claim_selection,
        )

    def run_cycle(self) -> BackgroundCycleResult:
        started = datetime.now(UTC)
        claimed = succeeded = retry_wait = dead_letter = 0
        failures = 0
        after = ""
        discovered = 0
        while True:
            records = self._installations.scan_connected(after=after, limit=100)
            discovered += len(records)
            if not records:
                break
            for view in records:
                try:
                    outcome = self._scoped(view).runtime.run_cycle()
                    claimed += outcome.claimed
                    succeeded += outcome.succeeded
                    retry_wait += outcome.retry_wait
                    dead_letter += outcome.dead_letter
                except Exception:
                    # One tenant cannot starve another or leak provider errors.
                    failures += 1
            after = records[-1].installation_id
            if len(records) < 100:
                break
        if failures or not discovered:
            self._observer.cycle_failed(
                error_type="BlingScopeUnavailable", elapsed_seconds=0.0,
            )
        else:
            self._observer.cycle_completed(BackgroundCycleResult(
                claimed, succeeded, retry_wait, dead_letter,
                (datetime.now(UTC) - started).total_seconds(),
            ))
        return BackgroundCycleResult(
            claimed, succeeded, retry_wait, dead_letter,
            (datetime.now(UTC) - started).total_seconds(),
        )

    def run_forever(self, stop: Event) -> None:
        self._observer.worker_started()
        try:
            while not stop.is_set():
                try:
                    self.run_cycle()
                except Exception:
                    self._observer.cycle_failed(
                        error_type="BlingRegistryUnavailable", elapsed_seconds=0.0,
                    )
                stop.wait(1.0)
        finally:
            self._observer.worker_stopped()


def build_bling_multi_worker_factory(
    environ: Mapping[str, str] | None = None,
) -> Callable[
    [PostgresFiscalDatabase, RuntimeSettings],
    BlingMultiInstallationWorkerComposition,
]:
    source = os.environ if environ is None else environ
    if source.get("NFCORE_WORKER_CONNECTOR") != BLING_MULTI_MODE:
        raise RuntimeConfigurationError("Bling multi-worker mode is not selected")
    if source.get("NFCORE_WORKER_GSM_MODE"):
        raise RuntimeConfigurationError("Bling/GSM multi-worker authority conflict")

    def build(
        database: PostgresFiscalDatabase,
        settings: RuntimeSettings,
    ) -> BlingMultiInstallationWorkerComposition:
        if (
            settings.environment is not RuntimeEnvironment.PRODUCTION
            or settings.secret_backend != "external"
        ):
            raise RuntimeConfigurationError(
                "Bling multi-worker requires canonical production/external runtime"
            )
        installations, oauth = build_bling_oauth_service(database, source)
        return BlingMultiInstallationWorkerComposition(
            database, source, installations, oauth,
        )
    return build
