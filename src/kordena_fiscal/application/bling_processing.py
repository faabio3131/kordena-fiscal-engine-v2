"""Bling jobs use the canonical durable inbox, snapshots and fiscal executor."""

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

from kordena_fiscal.application.bling_orders import ISSUE_ORDER, PROCESS_ORDER, BlingOrders
from kordena_fiscal.connectors.bling_api import BlingApiError
from kordena_fiscal.contingency import (
    FiscalDispatchResult,
    FiscalDispatchStatus,
    FiscalOutboxEntry,
)
from kordena_fiscal.domain import ExecutionScope, FiscalValidationError
from kordena_fiscal.events.inbox import FiscalInboxStatus
from kordena_fiscal.persistence.ports import PersistenceConflictError, PersistenceStateError


class BlingFiscalExecutor(Protocol):
    def execute(
        self,
        *,
        operation_id: str,
        scope: ExecutionScope,
        payload: Mapping[str, Any],
        idempotency_key: str | None,
    ) -> Mapping[str, Any]: ...


@dataclass(frozen=True, slots=True)
class BlingProcessingHandler:
    orders: BlingOrders
    fetch: Callable[[int], Mapping[str, Any]]
    fiscal_path: BlingFiscalExecutor
    before_issue: Callable[[str], None] | None = None
    validate_binding: Callable[[], None] | None = None

    def dispatch(self, job: FiscalOutboxEntry) -> FiscalDispatchResult:
        fatal = FiscalDispatchStatus.FATAL_FAILURE
        if (
            job.operation not in {PROCESS_ORDER, ISSUE_ORDER}
            or job.scope.identity_partition_key != self.orders.scope.identity_partition_key
        ):
            return FiscalDispatchResult(fatal, error="Bling job scope mismatch")
        try:
            if self.validate_binding is not None:
                self.validate_binding()
            if job.operation == ISSUE_ORDER:
                return self._issue(job)
            entry_id = job.payload.decode("ascii")
            suffix = job.deduplication_key.removeprefix(entry_id + ":retry:")
            retry = (
                job.deduplication_key.startswith(entry_id + ":retry:")
                and len(suffix) == 64
                and all(c in "0123456789abcdef" for c in suffix)
            )
            if entry_id != job.deduplication_key and not retry:
                raise ValueError("job reference mismatch")
            event = self.orders.application.get_inbox_event(entry_id)
            if (
                event is None
                or event.scope.identity_partition_key != self.orders.scope.identity_partition_key
                or event.producer != f"bling:{self.orders.company_id}".lower()
                or event.event_type not in {"order.created", "order.updated", "order.deleted"}
            ):
                raise ValueError("inbox scope mismatch")
            payload = json.loads(event.payload)
            if payload.get("companyId") != self.orders.company_id:
                raise ValueError("company mismatch")
            order_id = payload["data"]["id"]
            self.orders.key(order_id)  # Reject booleans, strings and non-positive identifiers.
            if event.status is FiscalInboxStatus.PROCESSED:
                return FiscalDispatchResult(
                    FiscalDispatchStatus.SUCCEEDED,
                    reference=self.orders.key(order_id),
                )
            if event.event_type == "order.deleted":
                self.orders.mark_deleted(order_id, now=event.received_at)
            else:
                self.orders.stage(
                    order_id,
                    self.fetch(order_id),
                    event_id=entry_id,
                    now=event.received_at,
                )
            current = self.orders.application.get_inbox_event(entry_id)
            assert current is not None
            if current.status is FiscalInboxStatus.RECEIVED:
                current = self.orders.application.begin_inbox_processing(
                    entry_id,
                    expected_version=current.version,
                )
            if current.status is FiscalInboxStatus.PROCESSING:
                self.orders.application.complete_inbox_event(
                    entry_id,
                    expected_version=current.version,
                    processed_at=datetime.now(UTC),
                    outcome_reference=self.orders.key(order_id),
                )
            return FiscalDispatchResult(
                FiscalDispatchStatus.SUCCEEDED,
                reference=self.orders.key(order_id),
            )
        except BlingApiError as exc:
            status = FiscalDispatchStatus.RETRYABLE_FAILURE if exc.retryable else fatal
            return FiscalDispatchResult(status, error="Bling order lookup failed")
        except (ValueError, TypeError, KeyError, FiscalValidationError, PersistenceStateError):
            return FiscalDispatchResult(fatal, error="Bling order requires review")
        except PersistenceConflictError:
            return FiscalDispatchResult(
                FiscalDispatchStatus.RETRYABLE_FAILURE,
                error="Bling concurrent state change",
            )
        except Exception:
            # Never persist credentials or provider exception messages in delivery audit.
            return FiscalDispatchResult(
                FiscalDispatchStatus.RETRYABLE_FAILURE,
                error="Bling processing unavailable",
            )

    def _issue(self, job: FiscalOutboxEntry) -> FiscalDispatchResult:
        order_id = int(job.payload.decode("ascii"))
        if job.deduplication_key != self.orders.key(order_id):
            raise ValueError("invalid issuance reference")
        row = self.orders.get(order_id)
        if row is None or not isinstance(row.get("document_id"), str):
            raise ValueError("missing approved document")
        if row.get("deleted") or row.get("changed_snapshot_sha256"):
            return FiscalDispatchResult(
                FiscalDispatchStatus.FATAL_FAILURE,
                error="Bling approved order changed",
            )
        if self.before_issue is not None:
            self.before_issue(str(row["document_id"]))
        result = self.fiscal_path.execute(
            operation_id="issueFiscalDocument",
            scope=job.scope,
            payload={"document_id": row["document_id"]},
            idempotency_key=self.orders.key(order_id),
        )
        self.orders.record_result(order_id, result)
        return FiscalDispatchResult(
            FiscalDispatchStatus.SUCCEEDED,
            reference=str(row["document_id"]),
        )

    def reconcile(self, order_id: int) -> Mapping[str, object]:
        """Explicit recovery consults the original fiscal attempt, never issues again."""
        row = self.orders.get(order_id)
        if row is None or not isinstance(row.get("document_id"), str):
            raise FiscalValidationError("Bling order has no prepared document")
        result = self.fiscal_path.execute(
            operation_id="reconcileFiscalOperation",
            scope=self.orders.scope,
            payload={"document_id": row["document_id"]},
            idempotency_key=self.orders.key(order_id) + ":reconcile",
        )
        return self.orders.record_result(order_id, result)
