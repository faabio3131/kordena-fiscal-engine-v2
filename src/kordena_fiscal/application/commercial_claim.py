"""Secure customer claim for provider-neutral NFCore commercial purchases."""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass, replace
from datetime import datetime, timedelta

from kordena_fiscal.product.commercial_fulfillment import (
    CanonicalCommercialUnitOfWorkFactory,
    CommercialClaimRecord,
    CommercialFulfillmentError,
    CommercialPurchaseRecord,
    CommercialPurchaseState,
)
from kordena_fiscal.security.human_identity import HumanAccountRepository


def _aware(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise CommercialFulfillmentError(f"{field_name} must be timezone-aware")
    return value


def _digest(token: str) -> str:
    normalized = token.strip()
    if not normalized or len(normalized) > 4096:
        raise CommercialFulfillmentError("commercial claim token is not usable")
    return hashlib.sha256(normalized.encode()).hexdigest()


def _legal_name(value: str) -> str:
    normalized = value.strip()
    if not normalized or len(normalized) > 256:
        raise CommercialFulfillmentError(
            "legal_name must be non-blank and <= 256 chars"
        )
    return normalized


@dataclass(frozen=True, slots=True)
class IssuedCommercialClaim:
    claim_token: str
    purchase_id: str
    delivery_email: str
    expires_at: datetime

    def __repr__(self) -> str:
        return (
            "IssuedCommercialClaim(claim_token=<redacted>, "
            f"purchase_id={self.purchase_id!r}, delivery_email=<redacted>, "
            f"expires_at={self.expires_at!r})"
        )


@dataclass(frozen=True, slots=True)
class CommercialClaimCompletion:
    purchase: CommercialPurchaseRecord
    manual_review: bool


class CommercialClaimService:
    """Issue and consume one-time claims without trusting external customer identity."""

    def __init__(
        self,
        *,
        unit_of_work_factory: CanonicalCommercialUnitOfWorkFactory,
        accounts: HumanAccountRepository,
        claim_ttl: timedelta = timedelta(hours=24),
    ) -> None:
        if not isinstance(accounts, HumanAccountRepository):
            raise ValueError("accounts must implement HumanAccountRepository")
        if claim_ttl < timedelta(minutes=15) or claim_ttl > timedelta(days=7):
            raise ValueError("claim_ttl must be between 15 minutes and 7 days")
        self._unit_of_work_factory = unit_of_work_factory
        self._accounts = accounts
        self._claim_ttl = claim_ttl

    def issue(
        self,
        *,
        purchase_id: str,
        now: datetime,
    ) -> IssuedCommercialClaim:
        _aware(now, "now")
        with self._unit_of_work_factory() as uow:
            purchase = uow.commercial.get_purchase(purchase_id)
            if purchase is None:
                raise CommercialFulfillmentError("commercial purchase was not found")
            self._assert_claimable(purchase)
            self._assert_coverage(uow.commercial, purchase, now)
            if purchase.buyer_email is None:
                raise CommercialFulfillmentError(
                    "commercial purchase requires verified delivery contact"
                )
            token = secrets.token_urlsafe(48)
            claim = CommercialClaimRecord(
                claim_id=f"claim-{secrets.token_hex(16)}",
                purchase_id=purchase.purchase_id,
                token_sha256=_digest(token),
                created_at=now,
                expires_at=now + self._claim_ttl,
            )
            uow.commercial.put_claim(claim)
            uow.commit()
        return IssuedCommercialClaim(
            claim_token=token,
            purchase_id=purchase.purchase_id,
            delivery_email=purchase.buyer_email,
            expires_at=claim.expires_at,
        )

    def complete(
        self,
        *,
        claim_token: str,
        legal_name: str,
        now: datetime,
    ) -> CommercialClaimCompletion:
        _aware(now, "now")
        normalized_name = _legal_name(legal_name)
        token_sha256 = _digest(claim_token)

        with self._unit_of_work_factory() as uow:
            claim = uow.commercial.get_claim_by_digest(token_sha256)
            if claim is None or claim.used_at is not None or now >= claim.expires_at:
                raise CommercialFulfillmentError("commercial claim token is not usable")

            purchase = uow.commercial.get_purchase(claim.purchase_id)
            if purchase is None:
                raise CommercialFulfillmentError("commercial claim has no canonical purchase")
            self._assert_claimable(purchase)
            self._assert_coverage(uow.commercial, purchase, now)
            if purchase.buyer_email is None:
                raise CommercialFulfillmentError(
                    "commercial purchase requires verified delivery contact"
                )
            if not uow.commercial.consume_claim(claim.claim_id, now):
                raise CommercialFulfillmentError("commercial claim token is not usable")

            existing_account = self._accounts.by_email(purchase.buyer_email)
            if existing_account is not None:
                updated = replace(
                    purchase,
                    state=CommercialPurchaseState.MANUAL_REVIEW,
                    legal_name=normalized_name,
                    updated_at=now,
                )
                uow.commercial.put_purchase(updated)
                uow.commit()
                return CommercialClaimCompletion(
                    purchase=updated,
                    manual_review=True,
                )

            updated = replace(
                purchase,
                state=CommercialPurchaseState.READY_TO_PROVISION,
                legal_name=normalized_name,
                tenant_id=f"tenant-{secrets.token_hex(16)}",
                updated_at=now,
            )
            uow.commercial.put_purchase(updated)
            uow.commit()
            return CommercialClaimCompletion(
                purchase=updated,
                manual_review=False,
            )

    @staticmethod
    def _assert_coverage(store: object, purchase: CommercialPurchaseRecord, now: datetime) -> None:
        get_contract = getattr(store, "get_contract", None)
        contract = get_contract(purchase.purchase_id) if callable(get_contract) else None
        if contract is not None:
            if not contract.covers(purchase.billing_status, now):
                raise CommercialFulfillmentError("commercial coverage blocks customer claim")
        elif purchase.provider_id == "command":
            raise CommercialFulfillmentError("canonical contracted coverage is unavailable")

    @staticmethod
    def _assert_claimable(purchase: CommercialPurchaseRecord) -> None:
        if purchase.state not in {
            CommercialPurchaseState.UNCLAIMED,
            CommercialPurchaseState.IDENTITY_REQUIRED,
        }:
            raise CommercialFulfillmentError(
                "commercial purchase is not eligible for customer claim"
            )
        if purchase.tenant_id is not None or purchase.account_id is not None:
            raise CommercialFulfillmentError(
                "commercial purchase already has canonical identity"
            )


__all__ = [
    "CommercialClaimCompletion",
    "CommercialClaimService",
    "IssuedCommercialClaim",
]
