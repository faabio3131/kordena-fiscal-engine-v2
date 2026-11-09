"""Durable Bling intake and explicit handoff to prepared canonical documents.

Order data is advisory. Only trusted preparation may provide a signed document;
this module never derives tax decisions or accepts XML from a webhook.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
from typing import Any

from kordena_fiscal.application.service import FiscalApplicationService
from kordena_fiscal.archive import FiscalArchiveEntry, FiscalArchiveKind, RetentionPolicyMetadata
from kordena_fiscal.connectors.erp_pme import ConnectorValidationError, normalize_erp_order
from kordena_fiscal.contingency import FiscalOutboxService
from kordena_fiscal.domain import ElectronicInvoiceModel, ExecutionScope, FiscalValidationError
from kordena_fiscal.gateway import AuthorizationRequest
from kordena_fiscal.lifecycle import FiscalDocumentState
from kordena_fiscal.persistence.ports import (
    FiscalUnitOfWorkFactory,
    PersistenceConflictError,
    PersistenceStateError,
)

PROCESS_ORDER = "process_bling_order"
ISSUE_ORDER = "issue_bling_order"
PUBLISH_STATUS = "publish_bling_status"
MEDIA_TYPE = "application/vnd.nfcore.bling-order.v1+json"


def _decimal_json(value: object) -> str:
    if isinstance(value, Decimal) and value.is_finite():
        return str(value)
    raise ValueError("unsupported order value")


def encode_order(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
        default=_decimal_json,
    ).encode()


class BlingOrders:
    """Use existing transactional receipts, immutable archive and outbox authorities."""

    def __init__(
        self,
        factory: FiscalUnitOfWorkFactory,
        scope: ExecutionScope,
        company_id: str,
    ) -> None:
        if scope.host_namespace != "bling" or not company_id or len(company_id) > 96:
            raise FiscalValidationError("invalid Bling installation scope")
        self.factory = factory
        self.scope = scope
        self.company_id = company_id
        self.application = FiscalApplicationService(factory)

    def key(self, order_id: int) -> str:
        if type(order_id) is not int or order_id <= 0:
            raise FiscalValidationError("invalid Bling order identifier")
        # Receipt storage predates host namespaces: explicitly include it in the key.
        identity = json.dumps([*self.scope.identity_material, self.company_id, order_id])
        return "bling-order:" + hashlib.sha256(identity.encode()).hexdigest()

    def get(self, order_id: int) -> Mapping[str, object] | None:
        with self.factory() as uow:
            return uow.commercial.configuration_receipt(self.scope, self.key(order_id))

    def requires_dispatch(self, document_id: str) -> bool:
        with self.factory() as uow:
            uow.lifecycle.assert_scope(document_id, self.scope)
            lifecycle = uow.lifecycle.get(document_id)
        return lifecycle is not None and lifecycle.state is FiscalDocumentState.READY_TO_TRANSMIT

    def snapshot(self, order_id: int) -> dict[str, Any]:
        row = self.get(order_id)
        if row is None:
            raise FiscalValidationError("Bling order not found")
        with self.factory() as uow:
            entries = uow.archive.list_for_document(self.scope, self.key(order_id))
        for entry in entries:
            if entry.entry_id == row.get("archive_id") and entry.media_type == MEDIA_TYPE:
                data = json.loads(entry.content)
                if isinstance(data, dict):
                    return data
        raise PersistenceStateError("Bling snapshot is unavailable")

    def review_snapshots(self, order_id: int) -> list[dict[str, Any]]:
        """Expose only the selected and latest pending snapshots to authorized reviewers."""
        row = self.get(order_id)
        if row is None:
            raise FiscalValidationError("Bling order not found")
        digests = {row.get("snapshot_sha256"), row.get("changed_snapshot_sha256")}
        with self.factory() as uow:
            entries = uow.archive.list_for_document(self.scope, self.key(order_id))
        return [
            {"sha256": entry.content_sha256, "content": json.loads(entry.content)}
            for entry in entries
            if entry.media_type == MEDIA_TYPE and entry.content_sha256 in digests
        ]

    def stage(
        self,
        order_id: int,
        raw: Mapping[str, Any],
        *,
        event_id: str,
        now: datetime,
    ) -> Mapping[str, object]:
        if type(raw.get("id")) is not int or raw["id"] != order_id:
            raise FiscalValidationError("Bling order identity mismatch")
        normalized = None
        try:
            normalized = normalize_erp_order(raw, platform="BLING_V3")
        except ConnectorValidationError:
            pass  # Preserve incomplete orders for review, never fabricate fiscal fields.
        content = encode_order({"raw": dict(raw), "normalized": normalized})
        entry = FiscalArchiveEntry.build(
            scope=self.scope,
            document_reference=self.key(order_id),
            kind=FiscalArchiveKind.OTHER,
            content=content,
            media_type=MEDIA_TYPE,
            archived_at=now,
            retention=RetentionPolicyMetadata("nfcore-bling-order", 1),
        )
        row: dict[str, object] = {
            "order_id": order_id,
            "company_id": self.company_id,
            "order_fingerprint": hashlib.sha256(
                encode_order({key: value for key, value in raw.items() if key != "situacao"})
            ).hexdigest(),
            "snapshot_sha256": entry.content_sha256,
            "archive_id": entry.entry_id,
            "state": "review_required",
            "normalization_ready": normalized is not None,
            "event_id": event_id,
            "created_at": now.isoformat(),
            "document_id": None,
        }
        with self.factory() as uow:
            # One first snapshot per order, committed atomically. Later updates never
            # silently overwrite a snapshot already reviewed or sent for issuance.
            existing = uow.commercial.reserve_configuration_command(
                self.scope,
                self.key(order_id),
                self.key(order_id),
            )
            uow.archive.append(entry)
            if existing is None:
                uow.commercial.complete_configuration_command(self.scope, self.key(order_id), row)
            else:
                incoming_fingerprint = row["order_fingerprint"]
                row = dict(existing)
                if existing.get("order_fingerprint") != incoming_fingerprint:
                    row["changed_snapshot_sha256"] = entry.content_sha256
                    row["review_required"] = True
                    if not uow.commercial.replace_configuration_receipt(
                        self.scope,
                        self.key(order_id),
                        existing,
                        row,
                    ):
                        raise PersistenceConflictError("Bling order changed concurrently")
            uow.commit()
        return row

    def select_snapshot(
        self,
        order_id: int,
        *,
        snapshot_sha256: str,
        actor_id: str,
        now: datetime,
    ) -> Mapping[str, object]:
        """Accept a reviewed newer snapshot only before any document has been bound."""
        if not actor_id.strip() or len(actor_id) > 128:
            raise FiscalValidationError("review actor is required")
        with self.factory() as uow:
            key = self.key(order_id)
            row = uow.commercial.configuration_receipt(self.scope, key)
            if row is None or row.get("document_id") is not None or row.get("deleted"):
                raise PersistenceConflictError("Bling order cannot replace its snapshot")
            latest = row.get("changed_snapshot_sha256") or row.get("snapshot_sha256")
            if snapshot_sha256 != latest:
                raise PersistenceConflictError("Bling review must use the latest known snapshot")
            candidates = [
                entry
                for entry in uow.archive.list_for_document(self.scope, key)
                if entry.media_type == MEDIA_TYPE and entry.content_sha256 == snapshot_sha256
            ]
            if len(candidates) != 1:
                raise PersistenceConflictError("Bling snapshot not found in this scope")
            entry = candidates[0]
            content = json.loads(entry.content)
            updated = {
                **row,
                "snapshot_sha256": snapshot_sha256,
                "archive_id": entry.entry_id,
                "order_fingerprint": hashlib.sha256(
                    encode_order(
                        {key: value for key, value in content["raw"].items() if key != "situacao"}
                    )
                ).hexdigest(),
                "normalization_ready": content.get("normalized") is not None,
                "changed_snapshot_sha256": None,
                "review_required": True,
                "reviewed_by": actor_id,
                "reviewed_at": now.isoformat(),
            }
            if not uow.commercial.replace_configuration_receipt(self.scope, key, row, updated):
                raise PersistenceConflictError("Bling snapshot changed concurrently")
            uow.commit()
            return updated

    def retry_event(self, entry_id: str, *, request_id: str, actor_id: str) -> str:
        """Explicit durable retry after correcting configuration; original event stays intact."""
        if not request_id.strip() or len(request_id) > 128 or not actor_id.strip():
            raise FiscalValidationError("retry request and actor are required")
        with self.factory() as uow:
            event = uow.inbox.get(entry_id)
            if (
                event is None
                or event.scope.identity_partition_key != self.scope.identity_partition_key
                or event.producer != ("bling:" + self.company_id).lower()
                or json.loads(event.payload).get("companyId") != self.company_id
            ):
                raise FiscalValidationError("Bling retry event is unavailable")
            key = entry_id + ":retry:" + hashlib.sha256(request_id.encode()).hexdigest()
            fingerprint = hashlib.sha256(
                encode_order({"actor": actor_id, "event": entry_id})
            ).hexdigest()
            existing = uow.commercial.reserve_configuration_command(self.scope, key, fingerprint)
            if existing is None:
                uow.commercial.complete_configuration_command(
                    self.scope,
                    key,
                    {
                        "event_id": entry_id,
                        "requested_by": actor_id,
                        "request_id": request_id,
                    },
                )
            job = (
                FiscalOutboxService(uow.outbox)
                .enqueue(
                    scope=self.scope,
                    operation=PROCESS_ORDER,
                    deduplication_key=key,
                    payload=entry_id.encode("ascii"),
                    created_at=event.received_at,
                )
                .entry
            )
            uow.commit()
            return job.entry_id

    def approve_prepared(
        self,
        order_id: int,
        *,
        snapshot_sha256: str,
        document_id: str,
        actor_id: str,
        now: datetime,
    ) -> Mapping[str, object]:
        """Trusted operator command; external webhook cannot invoke this transition."""
        if not actor_id.strip() or len(actor_id) > 128:
            raise FiscalValidationError("approval actor is required")
        # Canonical archive verifies that signed preparation exists in the exact scope.
        prepared = self.application.load_prepared_document_authorization(self.scope, document_id)
        if (
            not isinstance(prepared, AuthorizationRequest)
            or prepared.access_key.model is not ElectronicInvoiceModel.NFE
        ):
            raise FiscalValidationError("Bling requires a prepared model-55 document")
        with self.factory() as uow:
            row = uow.commercial.configuration_receipt(self.scope, self.key(order_id))
            if row is None or row.get("snapshot_sha256") != snapshot_sha256:
                raise PersistenceConflictError("Bling snapshot is unavailable or changed")
            if row.get("changed_snapshot_sha256") or row.get("deleted"):
                raise PersistenceConflictError("Bling order needs review before approval")
            if row.get("document_id") == document_id:
                return row
            if row.get("document_id") is not None:
                raise PersistenceConflictError("Bling order is already bound to a document")
            # A prepared document cannot be assigned to two different orders/companies.
            document_key = (
                "bling-document:"
                + hashlib.sha256(
                    json.dumps([*self.scope.identity_material, document_id]).encode()
                ).hexdigest()
            )
            uow.commercial.reserve_configuration_command(
                self.scope,
                document_key,
                self.key(order_id),
            )
            uow.commercial.complete_configuration_command(
                self.scope,
                document_key,
                {"order_key": self.key(order_id)},
            )
            updated = {
                **row,
                "document_id": document_id,
                "state": "queued",
                "approved_by": actor_id,
                "approved_at": now.isoformat(),
            }
            if not uow.commercial.replace_configuration_receipt(
                self.scope,
                self.key(order_id),
                row,
                updated,
            ):
                raise PersistenceConflictError("Bling approval changed concurrently")
            FiscalOutboxService(uow.outbox).enqueue(
                scope=self.scope,
                operation=ISSUE_ORDER,
                deduplication_key=self.key(order_id),
                payload=str(order_id).encode("ascii"),
                created_at=now,
            )
            uow.commit()
        return updated

    def mark_deleted(self, order_id: int, *, now: datetime) -> None:
        with self.factory() as uow:
            key = self.key(order_id)
            row = uow.commercial.reserve_configuration_command(self.scope, key, key)
            if row is None:
                uow.commercial.complete_configuration_command(
                    self.scope,
                    key,
                    {
                        "order_id": order_id,
                        "company_id": self.company_id,
                        "state": "deleted",
                        "deleted": True,
                        "document_id": None,
                        "snapshot_sha256": None,
                        "created_at": now.isoformat(),
                    },
                )
            elif not uow.commercial.replace_configuration_receipt(
                self.scope,
                key,
                row,
                {**row, "deleted": True, "review_required": True},
            ):
                raise PersistenceConflictError("Bling deletion changed concurrently")
            uow.commit()

    def retry_issuance(self, order_id: int, *, request_id: str, actor_id: str) -> str:
        """Retry an approved document only when canonical state proves no dispatch occurred."""
        if not request_id.strip() or len(request_id) > 128 or not actor_id.strip():
            raise FiscalValidationError("retry request and actor are required")
        with self.factory() as uow:
            row = uow.commercial.configuration_receipt(self.scope, self.key(order_id))
            if (
                row is None
                or not isinstance(row.get("document_id"), str)
                or row.get("deleted")
                or row.get("changed_snapshot_sha256")
            ):
                raise PersistenceStateError("Bling approved document is unavailable")
            document_id = str(row["document_id"])
            uow.lifecycle.assert_scope(document_id, self.scope)
            lifecycle = uow.lifecycle.get(document_id)
            if lifecycle is None or lifecycle.state is not FiscalDocumentState.READY_TO_TRANSMIT:
                raise PersistenceStateError("Bling document requires reconciliation, not resend")
            key = self.key(order_id) + ":retry:" + hashlib.sha256(request_id.encode()).hexdigest()
            fingerprint = hashlib.sha256(
                encode_order(
                    {
                        "actor": actor_id,
                        "document_id": document_id,
                    }
                )
            ).hexdigest()
            existing = uow.commercial.reserve_configuration_command(self.scope, key, fingerprint)
            if existing is None:
                uow.commercial.complete_configuration_command(
                    self.scope,
                    key,
                    {
                        "document_id": document_id,
                        "requested_by": actor_id,
                        "request_id": request_id,
                    },
                )
            job = (
                FiscalOutboxService(uow.outbox)
                .enqueue(
                    scope=self.scope,
                    operation=ISSUE_ORDER,
                    deduplication_key=key,
                    payload=str(order_id).encode("ascii"),
                    created_at=datetime.fromisoformat(str(row["approved_at"])),
                )
                .entry
            )
            uow.commit()
            return job.entry_id

    def retry_status(self, order_id: int, *, request_id: str, actor_id: str) -> str:
        """Retry only ERP writeback after an operator fixes its permanent failure."""
        if not request_id.strip() or len(request_id) > 128 or not actor_id.strip():
            raise FiscalValidationError("retry request and actor are required")
        with self.factory() as uow:
            row = uow.commercial.configuration_receipt(self.scope, self.key(order_id))
            if (
                row is None
                or row.get("state") not in {"authorized", "rejected"}
                or row.get("deleted")
                or row.get("changed_snapshot_sha256")
            ):
                raise PersistenceStateError("Bling final result is unavailable for retry")
            payload = encode_order(
                {
                    "event": "bling.fiscal_result",
                    "order_id": order_id,
                    "document_id": row["document_id"],
                    "status": row["state"],
                    "recovery_required": row.get("recovery_required", False),
                    "result_reference": row.get("result_reference"),
                }
            )
            key = (
                self.key(order_id)
                + ":result-retry:"
                + hashlib.sha256(request_id.encode()).hexdigest()
            )
            fingerprint = hashlib.sha256(payload + actor_id.encode()).hexdigest()
            existing = uow.commercial.reserve_configuration_command(self.scope, key, fingerprint)
            if existing is None:
                uow.commercial.complete_configuration_command(
                    self.scope,
                    key,
                    {
                        "order_id": order_id,
                        "requested_by": actor_id,
                        "request_id": request_id,
                    },
                )
            job = (
                FiscalOutboxService(uow.outbox)
                .enqueue(
                    scope=self.scope,
                    operation=PUBLISH_STATUS,
                    deduplication_key=key,
                    payload=payload,
                    created_at=datetime.fromisoformat(str(row["approved_at"])),
                )
                .entry
            )
            uow.commit()
            return job.entry_id

    def record_result(self, order_id: int, result: Mapping[str, Any]) -> Mapping[str, object]:
        # Only the canonical executor supplies this result, never the ERP payload.
        with self.factory() as uow:
            row = uow.commercial.configuration_receipt(self.scope, self.key(order_id))
            if row is None or result.get("document_id") != row.get("document_id"):
                raise PersistenceStateError("Bling fiscal result identity mismatch")
            if row.get("state") in {"authorized", "rejected"} and row["state"] != result["status"]:
                return row  # A late pending response cannot replace a terminal result.
            updated = {
                **row,
                "state": result["status"],
                "recovery_required": bool(result.get("recovery_required", False)),
                "result_reference": result.get("result_reference"),
                "rejection_reason": result.get("rejection_reason"),
            }
            if not uow.commercial.replace_configuration_receipt(
                self.scope,
                self.key(order_id),
                row,
                updated,
            ):
                raise PersistenceConflictError("Bling result changed concurrently")
            notification = encode_order(
                {
                    "event": "bling.fiscal_result",
                    "order_id": order_id,
                    "document_id": updated["document_id"],
                    "status": updated["state"],
                    "recovery_required": updated["recovery_required"],
                    "result_reference": updated["result_reference"],
                }
            )
            FiscalOutboxService(uow.outbox).enqueue(
                scope=self.scope,
                operation="deliver_webhook",
                deduplication_key=self.key(order_id)
                + ":"
                + hashlib.sha256(notification).hexdigest(),
                payload=notification,
                created_at=datetime.fromisoformat(str(row["approved_at"])),
            )
            if updated["state"] in {"authorized", "rejected"}:
                FiscalOutboxService(uow.outbox).enqueue(
                    scope=self.scope,
                    operation=PUBLISH_STATUS,
                    deduplication_key=self.key(order_id)
                    + ":"
                    + hashlib.sha256(notification).hexdigest(),
                    payload=notification,
                    created_at=datetime.fromisoformat(str(row["approved_at"])),
                )
            uow.commit()
        return updated
