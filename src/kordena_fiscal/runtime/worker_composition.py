"""Composition root for the canonical durable NFCORE background worker.

CL-02 deliberately wires the already-certified outbox, retry, delivery-audit and
observability primitives. It does not introduce a second queue or invent background
operations. Concrete handlers remain explicit dependencies so missing external
integrations fail closed instead of consuming jobs with placeholder behavior.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kordena_fiscal.application.webhook_delivery import SignedWebhookOutboxHandler
    from kordena_fiscal.security import WebhookSecurity

from kordena_fiscal.application import (
    BackgroundWorkerRuntime,
    DurableFiscalOutboxWorker,
    RoutedOutboxHandler,
)
from kordena_fiscal.contingency import FiscalOutboxHandler, FiscalRetryPolicy
from kordena_fiscal.persistence.ports import FiscalUnitOfWorkFactory

from .observability import MetricsRegistry, StructuredLogger, WorkerObservability


@dataclass(frozen=True, slots=True)
class ProductionWorkerComposition:
    """Process-local worker composition; authoritative job state stays durable."""

    runtime: BackgroundWorkerRuntime
    operations: frozenset[str]
    metrics: MetricsRegistry


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
) -> ProductionWorkerComposition:
    """Compose one durable worker over the canonical outbox and observer boundaries.

    ``RoutedOutboxHandler`` intentionally rejects an empty handler map. That keeps a
    staging/production worker from appearing healthy while no authorized operation can
    actually be executed.
    """

    routed = RoutedOutboxHandler(handlers)
    metrics = MetricsRegistry()
    observer = WorkerObservability(
        metrics=metrics,
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
