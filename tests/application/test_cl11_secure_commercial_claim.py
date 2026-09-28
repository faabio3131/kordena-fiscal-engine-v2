from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime, timedelta

import pytest

from kordena_fiscal.application.commercial_claim import CommercialClaimService
from kordena_fiscal.product.commercial_fulfillment import (
    CommercialClaimRecord,
    CommercialFulfillmentError,
    CommercialPurchaseRecord,
    CommercialPurchaseState,
)
from kordena_fiscal.security.human_identity import (
    HumanAccount,
    InMemoryHumanAccountRepository,
    PortalRole,
)

NOW = datetime(2026, 9, 28, 4, 0, tzinfo=UTC)


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


def service(
    database: MemoryClaimDatabase,
    accounts: InMemoryHumanAccountRepository | None = None,
) -> CommercialClaimService:
    return CommercialClaimService(
        unit_of_work_factory=database,
        accounts=accounts or InMemoryHumanAccountRepository(),
    )


def test_claim_stores_digest_only_rotates_and_redacts_representation() -> None:
    database = MemoryClaimDatabase()
    database.store.purchases[purchase().purchase_id] = purchase()
    claims = service(database)

    first = claims.issue(purchase_id=purchase().purchase_id, now=NOW)
    first_record = database.store.claims_by_purchase[purchase().purchase_id]
    assert first.claim_token not in repr(first)
    assert first.delivery_email not in repr(first)
    assert first.claim_token != first_record.token_sha256
    assert len(first_record.token_sha256) == 64

    second = claims.issue(
        purchase_id=purchase().purchase_id,
        now=NOW + timedelta(minutes=1),
    )
    assert second.claim_token != first.claim_token
    assert first_record.token_sha256 not in database.store.claims_by_digest

    with pytest.raises(CommercialFulfillmentError, match="not usable"):
        claims.complete(
            claim_token=first.claim_token,
            legal_name="ACME LTDA",
            now=NOW + timedelta(minutes=2),
        )


def test_claim_completion_generates_nfcore_owned_tenant_and_is_one_time() -> None:
    database = MemoryClaimDatabase()
    original = purchase()
    database.store.purchases[original.purchase_id] = original
    claims = service(database)

    issued = claims.issue(purchase_id=original.purchase_id, now=NOW)
    completed = claims.complete(
        claim_token=issued.claim_token,
        legal_name=" ACME Tecnologia LTDA ",
        now=NOW + timedelta(minutes=2),
    )

    assert completed.manual_review is False
    assert completed.purchase.state is CommercialPurchaseState.READY_TO_PROVISION
    assert completed.purchase.legal_name == "ACME Tecnologia LTDA"
    assert completed.purchase.tenant_id is not None
    assert completed.purchase.tenant_id.startswith("tenant-")
    assert "hotmart" not in completed.purchase.tenant_id
    assert "provider-customer-1" not in completed.purchase.tenant_id
    assert completed.purchase.account_id is None

    with pytest.raises(CommercialFulfillmentError, match="not usable"):
        claims.complete(
            claim_token=issued.claim_token,
            legal_name="ACME Tecnologia LTDA",
            now=NOW + timedelta(minutes=3),
        )


def test_existing_owner_email_moves_purchase_to_manual_review_without_rebinding() -> None:
    database = MemoryClaimDatabase()
    original = purchase()
    database.store.purchases[original.purchase_id] = original
    accounts = InMemoryHumanAccountRepository(
        (
            HumanAccount(
                account_id="existing-owner",
                email="owner@example.com",
                password_hash="not-used-in-claim-test",
                tenant_id="existing-tenant",
                role=PortalRole.OWNER,
            ),
        )
    )
    claims = service(database, accounts)

    issued = claims.issue(purchase_id=original.purchase_id, now=NOW)
    completed = claims.complete(
        claim_token=issued.claim_token,
        legal_name="ACME Tecnologia LTDA",
        now=NOW + timedelta(minutes=1),
    )

    assert completed.manual_review is True
    assert completed.purchase.state is CommercialPurchaseState.MANUAL_REVIEW
    assert completed.purchase.tenant_id is None
    assert completed.purchase.account_id is None


def test_claim_fails_closed_without_delivery_contact_or_after_commercial_termination() -> None:
    for candidate in (
        purchase(email=None),
        purchase(state=CommercialPurchaseState.CANCELED),
        purchase(state=CommercialPurchaseState.REFUNDED),
    ):
        database = MemoryClaimDatabase()
        database.store.purchases[candidate.purchase_id] = candidate
        claims = service(database)
        with pytest.raises(CommercialFulfillmentError):
            claims.issue(purchase_id=candidate.purchase_id, now=NOW)


def test_expired_claim_fails_closed_without_mutating_purchase() -> None:
    database = MemoryClaimDatabase()
    original = purchase()
    database.store.purchases[original.purchase_id] = original
    claims = CommercialClaimService(
        unit_of_work_factory=database,
        accounts=InMemoryHumanAccountRepository(),
        claim_ttl=timedelta(minutes=15),
    )
    issued = claims.issue(purchase_id=original.purchase_id, now=NOW)

    with pytest.raises(CommercialFulfillmentError, match="not usable"):
        claims.complete(
            claim_token=issued.claim_token,
            legal_name="ACME LTDA",
            now=NOW + timedelta(minutes=15),
        )

    assert database.store.purchases[original.purchase_id] == original
