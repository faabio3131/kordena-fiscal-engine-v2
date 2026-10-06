"""Resolve the requested destination from the canonical outbox partition."""

from kordena_fiscal.application.webhook_delivery import WebhookDestination
from kordena_fiscal.contingency import FiscalOutboxEntry
from kordena_fiscal.persistence.ports import FiscalUnitOfWorkFactory


class DurableWebhookDestinationResolver:
    def __init__(self, factory: FiscalUnitOfWorkFactory, destination_id: str) -> None:
        self._factory = factory
        self._destination_id = destination_id

    def resolve(self, entry: FiscalOutboxEntry) -> WebhookDestination | None:
        with self._factory() as uow:
            record = uow.commercial.webhook_approval(entry.scope, self._destination_id)
        if record is None:
            return None
        return WebhookDestination(self._destination_id, str(record["url"]))
