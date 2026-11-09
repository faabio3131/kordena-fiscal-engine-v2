"""Retryable status writeback, independent of the fiscal issuance job."""

import hashlib
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from kordena_fiscal.application.bling_orders import PUBLISH_STATUS, BlingOrders, encode_order
from kordena_fiscal.connectors.bling_api import BlingApiError
from kordena_fiscal.contingency import FiscalDispatchResult, FiscalDispatchStatus, FiscalOutboxEntry


@dataclass(frozen=True, slots=True)
class BlingStatusPublisher:
    orders: BlingOrders
    status_ids: Mapping[str, int]
    fetch: Callable[[int], Mapping[str, Any]]
    update: Callable[[int, int], None]
    validate_binding: Callable[[], None] | None = None

    def dispatch(self, job: FiscalOutboxEntry) -> FiscalDispatchResult:
        fatal = FiscalDispatchStatus.FATAL_FAILURE
        if (
            job.operation != PUBLISH_STATUS
            or job.scope.identity_partition_key != self.orders.scope.identity_partition_key
        ):
            return FiscalDispatchResult(fatal, error="Bling result scope mismatch")
        try:
            if self.validate_binding is not None:
                self.validate_binding()
            payload = json.loads(job.payload)
            order_id, status = payload["order_id"], payload["status"]
            row = self.orders.get(order_id)
            if row is None or row.get("document_id") != payload["document_id"]:
                raise ValueError("result identity mismatch")
            if row.get("state") != status:
                return FiscalDispatchResult(
                    FiscalDispatchStatus.SUCCEEDED,
                    reference="superseded_fiscal_result",
                )
            if row.get("deleted") or row.get("changed_snapshot_sha256"):
                raise ValueError("order requires review")
            target = self.status_ids[status]
            if type(target) is not int or target <= 0:
                raise ValueError("unconfigured status")
            current = self.fetch(order_id)
            if type(current.get("id")) is not int or current["id"] != order_id:
                raise ValueError("order mismatch")
            fingerprint = hashlib.sha256(
                encode_order({key: value for key, value in current.items() if key != "situacao"})
            ).hexdigest()
            if fingerprint != row.get("order_fingerprint"):
                raise ValueError("fiscal order data changed before writeback")
            current_status = current["situacao"]["id"]
            if type(current_status) is not int:
                raise ValueError("invalid current status")
            if current_status == target:
                return FiscalDispatchResult(
                    FiscalDispatchStatus.SUCCEEDED,
                    reference=f"bling-status:{order_id}:{target}",
                )
            original = self.orders.snapshot(order_id)["raw"]["situacao"]["id"]
            if type(original) is not int or current_status != original:
                raise ValueError("business status changed outside this integration")
            self.update(order_id, target)
            return FiscalDispatchResult(
                FiscalDispatchStatus.SUCCEEDED,
                reference=f"bling-status:{order_id}:{target}",
            )
        except BlingApiError as exc:
            return FiscalDispatchResult(
                FiscalDispatchStatus.RETRYABLE_FAILURE if exc.retryable else fatal,
                error="Bling status update unavailable",
            )
        except (ValueError, TypeError, KeyError):
            return FiscalDispatchResult(fatal, error="Bling status update requires review")
        except Exception:
            return FiscalDispatchResult(
                FiscalDispatchStatus.RETRYABLE_FAILURE,
                error="Bling result delivery unavailable",
            )
