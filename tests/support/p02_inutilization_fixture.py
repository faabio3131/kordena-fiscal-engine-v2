"""Synthetic internal outbox receipt, never a fiscal provider or runtime adapter."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

from fastapi import HTTPException

from kordena_fiscal.contingency import FiscalOutboxEntry, OutboxConflictError


def internal_handler(database, *, response_loss=False):
    def enqueue(scope, payload, idempotency_key):
        # This handler exists only in tests. It never dispatches or declares acceptance.
        digest = hashlib.sha256(
            json.dumps((*scope.identity_material, "inutilize", idempotency_key)).encode()
        ).hexdigest()
        content = json.dumps(dict(payload), sort_keys=True).encode()
        now = datetime.now(UTC)
        try:
            with database() as uow:
                result = uow.outbox.enqueue(
                    FiscalOutboxEntry(
                        entry_id=digest,
                        scope=scope,
                        operation="inutilize",
                        deduplication_key=digest,
                        payload=content,
                        payload_sha256=hashlib.sha256(content).hexdigest(),
                        created_at=now,
                        available_at=now,
                    )
                )
                uow.commit()
        except OutboxConflictError as exc:
            raise HTTPException(409, detail={"code": "SYNTHETIC_INTENT_CONFLICT"}) from exc
        if response_loss and not result.replay:
            raise HTTPException(
                503,
                detail={
                    "code": "SYNTHETIC_RESPONSE_LOSS",
                    "message": "Synthetic response loss after outbox commit; retry unchanged",
                },
            )
        return {
            "status": "internal_outbox_only",
            "entry_id": result.entry.entry_id,
            "replay": result.replay,
        }

    return enqueue
