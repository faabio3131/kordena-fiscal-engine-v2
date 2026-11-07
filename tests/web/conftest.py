"""Shared in-memory test doubles for the commercial claim HTTP boundary tests.

Mirrors the equivalent doubles in tests/application/test_cl11_secure_commercial_claim.py.
Kept local to tests/web (rather than imported cross-package) because this
project's pytest collection does not expose `tests` as an importable package —
see tests/cognitive/conftest.py for the same pattern used elsewhere.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime

from kordena_fiscal.product.commercial_fulfillment import (
    CommercialClaimRecord,
    CommercialFulfillmentError,
    CommercialPurchaseRecord,
    CommercialPurchaseState,
)

NOW = datetime(2026, 9, 28, 5, 0, tzinfo=UTC)


class MemoryClaimStore:
    def __init__(self) -> None:
        self.purchases: dict[str, CommercialPurchaseRecord] = {}
        self.claims_by_purchase: dict[str, CommercialClaimRecord] = {}
        self.claims_by_digest: dict[str, CommercialClaimRecord] = {}

    def get_purchase(self, purchase_id: str) -> CommercialPurchaseRecord | None:
        return self.purchases.get(purchase_id)

    def put_purchase(self, purchase: CommercialPurchaseRecord) -> CommercialPurchaseRecord:
        current = self.purchases.get(purchase.purchase_id)
        if current is not None:
            if current.tenant_id is not None and current.tenant_id != purchase.tenant_id:
                raise CommercialFulfillmentError("canonical purchase tenant cannot change")
            if current.legal_name is not None and current.legal_name != purchase.legal_name:
                raise CommercialFulfillmentError("canonical purchase legal name cannot change")
        self.purchases[purchase.purchase_id] = purchase
        return purchase

    def get_claim_by_digest(self, token_sha256: str) -> CommercialClaimRecord | None:
        return self.claims_by_digest.get(token_sha256)

    def get_claim_for_purchase(self, purchase_id: str) -> CommercialClaimRecord | None:
        return self.claims_by_purchase.get(purchase_id)

    def put_claim(self, claim: CommercialClaimRecord) -> CommercialClaimRecord:
        old = self.claims_by_purchase.get(claim.purchase_id)
        if old is not None:
            self.claims_by_digest.pop(old.token_sha256, None)
        self.claims_by_purchase[claim.purchase_id] = claim
        self.claims_by_digest[claim.token_sha256] = claim
        return claim

    def consume_claim(self, claim_id: str, used_at: datetime) -> bool:
        current = next(
            (claim for claim in self.claims_by_purchase.values() if claim.claim_id == claim_id),
            None,
        )
        if current is None or current.used_at is not None:
            return False
        used = CommercialClaimRecord(
            claim_id=current.claim_id,
            purchase_id=current.purchase_id,
            token_sha256=current.token_sha256,
            created_at=current.created_at,
            expires_at=current.expires_at,
            used_at=used_at,
        )
        self.claims_by_purchase[used.purchase_id] = used
        self.claims_by_digest[used.token_sha256] = used
        return True


class MemoryClaimUow:
    def __init__(self, store: MemoryClaimStore) -> None:
        self.commercial = store
        self._snapshot: tuple[object, object, object] | None = None
        self._committed = False

    def __enter__(self) -> MemoryClaimUow:
        self._snapshot = (
            deepcopy(self.commercial.purchases),
            deepcopy(self.commercial.claims_by_purchase),
            deepcopy(self.commercial.claims_by_digest),
        )
        self._committed = False
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        if exc_type is not None or not self._committed:
            assert self._snapshot is not None
            purchases, claims_by_purchase, claims_by_digest = self._snapshot
            self.commercial.purchases = purchases  # type: ignore[assignment]
            self.commercial.claims_by_purchase = claims_by_purchase  # type: ignore[assignment]
            self.commercial.claims_by_digest = claims_by_digest  # type: ignore[assignment]

    def commit(self) -> None:
        self._committed = True


class MemoryClaimDatabase:
    def __init__(self) -> None:
        self.store = MemoryClaimStore()

    def __call__(self) -> MemoryClaimUow:
        return MemoryClaimUow(self.store)


def purchase(
    *,
    state: CommercialPurchaseState = CommercialPurchaseState.UNCLAIMED,
    email: str | None = "owner@example.com",
) -> CommercialPurchaseRecord:
    return CommercialPurchaseRecord(
        purchase_id="commercial-purchase-0123456789abcdef0123456789abcdef",
        provider_id="hotmart",
        external_order_id="external-order-1",
        plan_id="growth",
        price_id="growth-monthly",
        state=state,
        created_at=NOW,
        updated_at=NOW,
        last_event_at=NOW,
        last_event_id="evt-sale",
        buyer_email=email,
        external_customer_id="provider-customer-1",
    )
