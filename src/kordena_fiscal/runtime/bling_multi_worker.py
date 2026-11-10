"""One multi-installation Bling scheduler over the existing scoped fiscal Worker.

No new queue, auth, business rules, API or fiscal execution code. Each bounded
cycle resolves the canonical host binding and claims exactly one fiscal partition.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from threading import Event

from kordena_fiscal.application.background_runtime import BackgroundCycleResult
from kordena_fiscal.application.bling_orders import BlingOrders
from kordena_fiscal.application.service import FiscalApplicationService
from kordena_fiscal.contingency import FiscalOutboxStatus
from kordena_fiscal.domain import ExecutionScope, FiscalEnvironment
from kordena_fiscal.integrations.bling_contracts import (
    BlingInstallationState,
    BlingInstallationView,
)
from kordena_fiscal.persistence.bling_installations import BlingInstallationRepository
from kordena_fiscal.persistence.postgres import PostgresFiscalDatabase
from kordena_fiscal.vault.encrypted_a1 import EncryptedA1Vault

from .bling_oauth_factory import build_bling_oauth_service
from .bling_oauth_service import BlingOAuthService
from .bling_worker import build_scoped_bling_handlers
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


class BlingMultiTenantWorkerComposition:
    """One process, canonical DB, round-robin bounded scoped outbox cycles."""

    def __init__(
        self,
        database: PostgresFiscalDatabase,
        installations: BlingInstallationRepository,
        oauth: BlingOAuthService,
        *,
        vault: EncryptedA1Vault | None = None,
        scoped_factory: (
            Callable[[BlingInstallationView], ProductionWorkerComposition] | None
        ) = None,
    ) -> None:
        self._db = database
        self._installations = installations
        self._oauth = oauth
        self._vault = vault
        self._scoped_factory = scoped_factory or self._scoped_worker
        self._observer = WorkerObservability(
            metrics=MetricsRegistry(),
            logger=StructuredLogger(service="nfcore-bling-worker", environment="production"),
            queue_counts=self._counts,
        )

    def _counts(self) -> Mapping[FiscalOutboxStatus, int]:
        with self._db() as uow:
            return uow.outbox.counts_by_status()

    def health(self) -> WorkerHealth:
        return self._observer.health()

    def _scope(self, view: BlingInstallationView) -> ExecutionScope:
        if (
            view.state is not BlingInstallationState.CONNECTED
            or view.environment is not FiscalEnvironment.HOMOLOGATION
        ):
            raise RuntimeConfigurationError("Bling installation cannot dispatch fiscal production")
        host = self._installations.host_binding(view.installation_id)
        if host is None:
            raise RuntimeConfigurationError("Bling installation missing canonical host binding")
        scope = FiscalApplicationService(self._db).resolve_scope(
            host,
            environment=view.environment,
            correlation_id="bling-multi-worker",
        )
        if (
            scope.host_namespace != "bling"
            or scope.tenant_id != view.tenant_id
            or scope.unit_id != view.unit_id
            or scope.environment is not view.environment
        ):
            raise RuntimeConfigurationError("Bling installation canonical binding drift")
        return scope

    def _scoped_worker(self, view: BlingInstallationView) -> ProductionWorkerComposition:
        scope = self._scope(view)
        mapping = self._installations.status_mapping_for_scope(scope, view.installation_id)
        if mapping is None:
            # Do not claim orders if business status writeback cannot be delivered.
            raise RuntimeConfigurationError("Bling installation status policy unavailable")

        def validate_binding() -> None:
            current = self._installations.get_for_scope(scope, view.installation_id)
            if (
                current is None
                or current.state is not BlingInstallationState.CONNECTED
                or current.company_id != view.company_id
                or current.revision != view.revision
                or self._scope(current).identity_partition_key
                != scope.identity_partition_key
                or self._installations.status_mapping_for_scope(
                    scope, view.installation_id
                ) != mapping
            ):
                raise RuntimeConfigurationError("Bling installation authorization changed")

        def token() -> str:
            validate_binding()
            return self._oauth.access_token(scope, view.installation_id)

        orders = BlingOrders(self._db, scope, view.company_id)
        scoped = build_scoped_bling_handlers(
            self._db,
            orders,
            token=token,
            validate_binding=validate_binding,
            status_mapping={"authorized": mapping[0], "rejected": mapping[1]},
            vault=self._vault,
        )
        return build_production_worker_runtime(
            uow_factory=self._db,
            handlers=scoped.handlers,
            claim_selection=scoped.claim_selection,
            environment="production",
            batch_size=1,
        )

    def _installations_page(self) -> tuple[BlingInstallationView, ...]:
        # Bounded scan; fail closed rather than silently starve tenants beyond limit.
        items: list[BlingInstallationView] = []
        cursor: str | None = None
        while True:
            page, cursor = self._installations.list_connected_for_worker(
                after=cursor or "", limit=100,
            )
            items.extend(page)
            if len(items) > 10_000:
                raise RuntimeConfigurationError("Bling worker installation registry too large")
            if cursor is None:
                return tuple(items)

    def run_cycle(self) -> BackgroundCycleResult:
        started = datetime.now(UTC)
        claimed = succeeded = retry_wait = dead_letter = 0
        failures = 0
        try:
            installations = self._installations_page()
        except Exception:
            self._observer.cycle_failed(
                error_type="BlingInstallationRegistryUnavailable", elapsed_seconds=0.0,
            )
            raise RuntimeConfigurationError(
                "Bling worker installation registry unavailable"
            ) from None

        for view in installations:
            try:
                outcome = self._scoped_factory(view).runtime.run_cycle()
                claimed += outcome.claimed
                succeeded += outcome.succeeded
                retry_wait += outcome.retry_wait
                dead_letter += outcome.dead_letter
            except Exception:
                # Fail only the affected tenant; never leak provider errors or data.
                failures += 1
        result = BackgroundCycleResult(
            claimed=claimed,
            succeeded=succeeded,
            retry_wait=retry_wait,
            dead_letter=dead_letter,
            elapsed_seconds=(datetime.now(UTC) - started).total_seconds(),
        )
        if failures:
            self._observer.cycle_failed(
                error_type="BlingTenantScopeUnavailable",
                elapsed_seconds=result.elapsed_seconds,
            )
        else:
            self._observer.cycle_completed(result)
        return result

    def run_forever(self, stop: Event) -> None:
        self._observer.worker_started()
        try:
            while not stop.is_set():
                try:
                    self.run_cycle()
                except Exception:
                    # Registry errors cannot become zero-work false-success health.
                    pass
                stop.wait(1.0)
        finally:
            self._observer.worker_stopped()


def build_bling_multi_worker(
    database: PostgresFiscalDatabase,
    settings: RuntimeSettings,
    environ: Mapping[str, str] | None = None,
) -> BlingMultiTenantWorkerComposition:
    """Opt-in only, never run when legacy global company configuration is present."""
    source = os.environ if environ is None else environ
    if (
        source.get("NFCORE_BLING_INSTALLATIONS_ENABLED") != "true"
        or source.get("NFCORE_WORKER_CONNECTOR") != "bling-multi"
        or settings.environment is not RuntimeEnvironment.PRODUCTION
        or settings.secret_backend != "external"
        or settings.persistence_backend != "postgres"
        or source.get("NFCORE_WORKER_GSM_MODE", "").strip()
        or any(
            source.get("NFCORE_BLING_" + field, "").strip()
            for field in ("COMPANY_ID", "TENANT_ID", "UNIT_ID", "ENVIRONMENT", "ACCESS_TOKEN_FILE")
        )
    ):
        raise RuntimeConfigurationError("Bling multi-worker authority denied")
    database.require_current_schema(require_bling=True)
    installations, oauth = build_bling_oauth_service(database, source)
    return BlingMultiTenantWorkerComposition(
        database, installations, oauth, vault=EncryptedA1Vault.from_environ(),
    )
