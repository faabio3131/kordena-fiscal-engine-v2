"""Composition root for the canonical durable NFCORE background worker.

CL-02 deliberately wires the already-certified outbox, retry, delivery-audit and
observability primitives. It does not introduce a second queue or invent background
operations. Concrete handlers remain explicit dependencies so missing external
integrations fail closed instead of consuming jobs with placeholder behavior.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import timedelta
from types import MappingProxyType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kordena_fiscal.application.webhook_delivery import SignedWebhookOutboxHandler
    from kordena_fiscal.security import WebhookSecurity

from kordena_fiscal.application import (
    BackgroundWorkerRuntime,
    DurableFiscalOutboxWorker,
    RoutedOutboxHandler,
)
from kordena_fiscal.contingency import FiscalOutboxHandler, FiscalOutboxStatus, FiscalRetryPolicy
from kordena_fiscal.persistence.ports import FiscalUnitOfWorkFactory

from .config import RuntimeConfigurationError
from .observability import MetricsRegistry, StructuredLogger, WorkerHealth, WorkerObservability

DELIVER_WEBHOOK_OPERATION = "deliver_webhook"


@dataclass(frozen=True, slots=True)
class WorkerWebhookDependencies:
    """Explicit platform dependencies; no URL, raw key or tenant authority here.

    Security must be supplied by the governed signing boundary. Destination URLs
    and approvals are resolved durably for each entry's scope at dispatch time.
    This dependency object does not certify an external secret backend.
    """

    security: WebhookSecurity = field(repr=False)
    destination_id: str

    def __post_init__(self) -> None:
        from kordena_fiscal.security import WebhookSecurity

        if not isinstance(self.security, WebhookSecurity):
            raise RuntimeConfigurationError("worker webhook signing dependency is invalid")
        if (
            not isinstance(self.destination_id, str)
            or not self.destination_id.strip()
            or len(self.destination_id) > 256
            or any(ord(char) < 32 or ord(char) == 127 for char in self.destination_id)
        ):
            raise RuntimeConfigurationError("worker webhook destination reference is invalid")
        object.__setattr__(self, "destination_id", self.destination_id.strip())


def build_canonical_worker_handlers(
    *,
    uow_factory: FiscalUnitOfWorkFactory,
    webhook: WorkerWebhookDependencies | None,
) -> Mapping[str, FiscalOutboxHandler]:
    """Register existing concrete handlers only, over the canonical outbox.

    No implicit fiscal provider, inbox replay or commercial provisioning handler
    exists. Missing dependencies fail before claiming jobs. The immutable map has
    one canonical operation, never tenant-selected aliases or dynamic imports.
    """
    if not isinstance(webhook, WorkerWebhookDependencies):
        raise RuntimeConfigurationError(
            "continuous worker requires an explicitly configured handler factory "
            "or canonical webhook signing dependencies"
        )
    return MappingProxyType(
        {
            DELIVER_WEBHOOK_OPERATION: build_customer_webhook_handler(
                uow_factory=uow_factory,
                security=webhook.security,
                destination_id=webhook.destination_id,
            )
        }
    )


@dataclass(frozen=True, slots=True)
class ProductionWorkerComposition:
    """Process-local worker composition; authoritative job state stays durable."""

    runtime: BackgroundWorkerRuntime
    operations: frozenset[str]
    metrics: MetricsRegistry
    observer: WorkerObservability

    def health(self) -> WorkerHealth:
        return self.observer.health()


def build_production_worker_runtime(
    *,
    uow_factory: FiscalUnitOfWorkFactory,
    handlers: Mapping[str, FiscalOutboxHandler],
    environment: str,
    retry_policy: FiscalRetryPolicy | None = None,
    batch_size: int = 10,
    lease_duration: timedelta = timedelta(seconds=60),
    idle_wait_seconds: float = 1.0,
    failure_wait_seconds: float = 2.0,
    heartbeat_timeout_seconds: float = 60.0,
) -> ProductionWorkerComposition:
    """Compose one durable worker over the canonical outbox and observer boundaries.

    ``RoutedOutboxHandler`` intentionally rejects an empty handler map. That keeps a
    staging/production worker from appearing healthy while no authorized operation can
    actually be executed.
    """

    routed = RoutedOutboxHandler(handlers)
    metrics = MetricsRegistry()

    def queue_counts() -> Mapping[FiscalOutboxStatus, int]:
        with uow_factory() as uow:
            return uow.outbox.counts_by_status()

    observer = WorkerObservability(
        metrics=metrics,
        queue_counts=queue_counts,
        heartbeat_timeout_seconds=heartbeat_timeout_seconds,
        logger=StructuredLogger(service="nfcore-worker", environment=environment),
    )
    worker = DurableFiscalOutboxWorker(
        uow_factory=uow_factory,
        handler=routed,
        retry_policy=retry_policy,
    )
    runtime = BackgroundWorkerRuntime(
        worker=worker,
        observer=observer,
        batch_size=batch_size,
        lease_duration=lease_duration,
        idle_wait_seconds=idle_wait_seconds,
        failure_wait_seconds=failure_wait_seconds,
    )
    return ProductionWorkerComposition(
        runtime=runtime,
        operations=routed.operations,
        metrics=metrics,
        observer=observer,
    )


def build_customer_webhook_handler(
    *,
    uow_factory: FiscalUnitOfWorkFactory,
    security: WebhookSecurity,
    destination_id: str,
) -> SignedWebhookOutboxHandler:
    """Compose the approved adapter without activating any worker operation/deploy."""
    from kordena_fiscal.application.webhook_delivery import SignedWebhookOutboxHandler
    from kordena_fiscal.control_plane.webhook_policy import DurableWebhookEgressPolicy
    from kordena_fiscal.gateway.webhook_transport import PinnedWebhookTransport
    from kordena_fiscal.runtime.webhook_destination import DurableWebhookDestinationResolver

    policy = DurableWebhookEgressPolicy(uow_factory)
    return SignedWebhookOutboxHandler(
        security=security,
        policy=policy,
        destination_resolver=DurableWebhookDestinationResolver(uow_factory, destination_id),
        transport=PinnedWebhookTransport(policy),
    )
