"""Durable provider-neutral commercial persistence for FM NFCORE.

This module owns canonical commercial purchase/subscription persistence only. Provider-specific
payloads remain in their adapters and raw webhook bodies/secrets are never stored here.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable, Sequence
from contextlib import AbstractContextManager
from datetime import datetime
from types import TracebackType
from typing import Protocol, Self, cast

from kordena_fiscal.product.billing import (
    CommercialPlan,
    SubscriptionCheckpoint,
    SubscriptionStatus,
    UsageQuota,
)
from kordena_fiscal.product.commercial_fulfillment import (
    CanonicalCommercialStore,
    CommercialAcquisitionRecord,
    CommercialClaimRecord,
    CommercialEventReceipt,
    CommercialEventType,
    CommercialFulfillmentError,
    CommercialPurchaseRecord,
    CommercialPurchaseState,
    DurableCommercialSubscription,
)


class _Cursor(Protocol):
    @property
    def rowcount(self) -> int: ...

    def fetchone(self) -> Sequence[object] | None: ...

    def fetchall(self) -> Sequence[Sequence[object]]: ...


class _Connection(Protocol):
    def execute(self, statement: str, parameters: Sequence[object] = ()) -> _Cursor: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...


ConnectionContextFactory = Callable[[], AbstractContextManager[_Connection]]


def _iso(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise CommercialFulfillmentError("persisted datetime must be timezone-aware")
    return value.isoformat()


def _dt(value: object, field_name: str) -> datetime:
    if not isinstance(value, str):
        raise CommercialFulfillmentError(f"persisted {field_name} must be text")
    try:
        result = datetime.fromisoformat(value)
    except ValueError as exc:
        raise CommercialFulfillmentError(f"persisted {field_name} is invalid") from exc
    if result.tzinfo is None or result.utcoffset() is None:
        raise CommercialFulfillmentError(
            f"persisted {field_name} must be timezone-aware"
        )
    return result


def _text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise CommercialFulfillmentError(
            f"persisted {field_name} must be non-empty text"
        )
    return value


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise CommercialFulfillmentError("persisted optional value must be text or null")
    return value


def _json_string_tuple(value: object, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, str):
        raise CommercialFulfillmentError(f"persisted {field_name} must be JSON text")
    try:
        decoded = json.loads(value)
    except json.JSONDecodeError as exc:
        raise CommercialFulfillmentError(f"persisted {field_name} is invalid JSON") from exc
    if not isinstance(decoded, list) or not all(isinstance(item, str) for item in decoded):
        raise CommercialFulfillmentError(
            f"persisted {field_name} must be a JSON string list"
        )
    return tuple(cast(list[str], decoded))


def _json_quotas(value: object) -> tuple[UsageQuota, ...]:
    if not isinstance(value, str):
        raise CommercialFulfillmentError("persisted quotas_json must be JSON text")
    try:
        decoded = json.loads(value)
    except json.JSONDecodeError as exc:
        raise CommercialFulfillmentError("persisted quotas_json is invalid JSON") from exc
    if not isinstance(decoded, list):
        raise CommercialFulfillmentError("persisted quotas_json must be a list")
    quotas: list[UsageQuota] = []
    for item in decoded:
        if (
            not isinstance(item, dict)
            or not isinstance(item.get("metric_id"), str)
            or not isinstance(item.get("limit"), int)
            or isinstance(item.get("limit"), bool)
        ):
            raise CommercialFulfillmentError("persisted quota entry is invalid")
        quotas.append(UsageQuota(str(item["metric_id"]), int(item["limit"])))
    return tuple(quotas)


def _json_usage(value: object) -> tuple[tuple[str, int], ...]:
    if not isinstance(value, str):
        raise CommercialFulfillmentError("persisted usage_json must be JSON text")
    try:
        decoded = json.loads(value)
    except json.JSONDecodeError as exc:
        raise CommercialFulfillmentError("persisted usage_json is invalid JSON") from exc
    if not isinstance(decoded, dict):
        raise CommercialFulfillmentError("persisted usage_json must be an object")
    usage: list[tuple[str, int]] = []
    for key, amount in decoded.items():
        if (
            not isinstance(key, str)
            or not isinstance(amount, int)
            or isinstance(amount, bool)
            or amount < 0
        ):
            raise CommercialFulfillmentError("persisted usage entry is invalid")
        usage.append((key, amount))
    return tuple(sorted(usage))


class CommercialSqlStore(CanonicalCommercialStore):
    def __init__(self, connection: _Connection) -> None:
        self._connection = connection

    def get_acquisition(
        self,
        acquisition_id: str,
    ) -> CommercialAcquisitionRecord | None:
        row = self._connection.execute(
            """
            SELECT acquisition_id, idempotency_sha256, request_sha256, provider_id,
                   plan_id, price_id, buyer_email, legal_name, created_at, expires_at,
                   linked_purchase_id
            FROM fm_commercial_acquisitions
            WHERE acquisition_id = ?
            """,
            (acquisition_id.strip().lower(),),
        ).fetchone()
        return None if row is None else self._acquisition(row)

    def get_acquisition_by_idempotency(
        self,
        idempotency_sha256: str,
    ) -> CommercialAcquisitionRecord | None:
        row = self._connection.execute(
            """
            SELECT acquisition_id, idempotency_sha256, request_sha256, provider_id,
                   plan_id, price_id, buyer_email, legal_name, created_at, expires_at,
                   linked_purchase_id
            FROM fm_commercial_acquisitions
            WHERE idempotency_sha256 = ?
            """,
            (idempotency_sha256.strip().lower(),),
        ).fetchone()
        return None if row is None else self._acquisition(row)

    def put_acquisition(
        self,
        acquisition: CommercialAcquisitionRecord,
    ) -> CommercialAcquisitionRecord:
        current = self.get_acquisition(acquisition.acquisition_id)
        if current is not None:
            immutable_current = (
                current.idempotency_sha256,
                current.request_sha256,
                current.provider_id,
                current.plan_id,
                current.price_id,
                current.buyer_email,
                current.legal_name,
                current.created_at,
                current.expires_at,
            )
            immutable_candidate = (
                acquisition.idempotency_sha256,
                acquisition.request_sha256,
                acquisition.provider_id,
                acquisition.plan_id,
                acquisition.price_id,
                acquisition.buyer_email,
                acquisition.legal_name,
                acquisition.created_at,
                acquisition.expires_at,
            )
            if immutable_current != immutable_candidate:
                raise CommercialFulfillmentError(
                    "canonical acquisition identity cannot be rewritten"
                )
            if (
                current.linked_purchase_id is not None
                and acquisition.linked_purchase_id != current.linked_purchase_id
            ):
                raise CommercialFulfillmentError(
                    "canonical acquisition purchase link cannot change"
                )
        try:
            self._connection.execute(
                """
                INSERT INTO fm_commercial_acquisitions (
                    acquisition_id, idempotency_sha256, request_sha256, provider_id,
                    plan_id, price_id, buyer_email, legal_name, created_at, expires_at,
                    linked_purchase_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (acquisition_id) DO UPDATE SET
                    linked_purchase_id = excluded.linked_purchase_id
                """,
                (
                    acquisition.acquisition_id,
                    acquisition.idempotency_sha256,
                    acquisition.request_sha256,
                    acquisition.provider_id,
                    acquisition.plan_id,
                    acquisition.price_id,
                    acquisition.buyer_email,
                    acquisition.legal_name,
                    _iso(acquisition.created_at),
                    _iso(acquisition.expires_at),
                    acquisition.linked_purchase_id,
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise CommercialFulfillmentError(
                "canonical commercial acquisition conflicts with durable state"
            ) from exc
        return acquisition

    def receive_event(
        self,
        receipt: CommercialEventReceipt,
    ) -> tuple[CommercialEventReceipt, bool]:
        current = self.get_event(receipt.provider_id, receipt.event_id)
        if current is not None:
            self._validate_event_replay(current, receipt)
            return current, True
        try:
            self._connection.execute(
                """
                INSERT INTO fm_commercial_event_receipts (
                    provider_id, event_id, event_type, external_order_id, purchase_id,
                    occurred_at, received_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    receipt.provider_id,
                    receipt.event_id,
                    receipt.event_type.value,
                    receipt.external_order_id,
                    receipt.purchase_id,
                    _iso(receipt.occurred_at),
                    _iso(receipt.received_at),
                ),
            )
        except sqlite3.IntegrityError:
            current = self.get_event(receipt.provider_id, receipt.event_id)
            if current is None:
                raise
            self._validate_event_replay(current, receipt)
            return current, True
        return receipt, False

    def get_event(
        self,
        provider_id: str,
        event_id: str,
    ) -> CommercialEventReceipt | None:
        row = self._connection.execute(
            """
            SELECT provider_id, event_id, event_type, external_order_id, purchase_id,
                   occurred_at, received_at
            FROM fm_commercial_event_receipts
            WHERE provider_id = ? AND event_id = ?
            """,
            (provider_id.strip().lower(), event_id.strip()),
        ).fetchone()
        if row is None:
            return None
        return CommercialEventReceipt(
            provider_id=_text(row[0], "provider_id"),
            event_id=_text(row[1], "event_id"),
            event_type=CommercialEventType(_text(row[2], "event_type")),
            external_order_id=_text(row[3], "external_order_id"),
            purchase_id=_text(row[4], "purchase_id"),
            occurred_at=_dt(row[5], "occurred_at"),
            received_at=_dt(row[6], "received_at"),
        )

    def get_purchase(self, purchase_id: str) -> CommercialPurchaseRecord | None:
        row = self._connection.execute(
            """
            SELECT purchase_id, provider_id, external_order_id, plan_id, state,
                   created_at, updated_at, last_event_at, last_event_id, price_id,
                   external_subscription_id, external_customer_id, buyer_email,
                   legal_name, tenant_id, account_id
            FROM fm_commercial_purchases
            WHERE purchase_id = ?
            """,
            (purchase_id.strip().lower(),),
        ).fetchone()
        return None if row is None else self._purchase(row)

    def get_purchase_by_external_order(
        self,
        provider_id: str,
        external_order_id: str,
    ) -> CommercialPurchaseRecord | None:
        row = self._connection.execute(
            """
            SELECT purchase_id, provider_id, external_order_id, plan_id, state,
                   created_at, updated_at, last_event_at, last_event_id, price_id,
                   external_subscription_id, external_customer_id, buyer_email,
                   legal_name, tenant_id, account_id
            FROM fm_commercial_purchases
            WHERE provider_id = ? AND external_order_id = ?
            """,
            (provider_id.strip().lower(), external_order_id.strip()),
        ).fetchone()
        return None if row is None else self._purchase(row)

    def get_purchase_by_account(
        self,
        account_id: str,
    ) -> CommercialPurchaseRecord | None:
        row = self._connection.execute(
            """
            SELECT purchase_id, provider_id, external_order_id, plan_id, state,
                   created_at, updated_at, last_event_at, last_event_id, price_id,
                   external_subscription_id, external_customer_id, buyer_email,
                   legal_name, tenant_id, account_id
            FROM fm_commercial_purchases
            WHERE account_id = ?
            ORDER BY updated_at DESC, purchase_id DESC
            LIMIT 1
            """,
            (account_id.strip().lower(),),
        ).fetchone()
        return None if row is None else self._purchase(row)

    def put_purchase(
        self,
        purchase: CommercialPurchaseRecord,
    ) -> CommercialPurchaseRecord:
        current = self.get_purchase(purchase.purchase_id)
        if current is not None:
            immutable_current = (
                current.provider_id,
                current.external_order_id,
                current.plan_id,
                current.price_id,
            )
            immutable_candidate = (
                purchase.provider_id,
                purchase.external_order_id,
                purchase.plan_id,
                purchase.price_id,
            )
            if immutable_current != immutable_candidate:
                raise CommercialFulfillmentError(
                    "canonical purchase identity cannot be rewritten"
                )
            if purchase.last_event_at < current.last_event_at:
                raise CommercialFulfillmentError(
                    "cannot overwrite canonical purchase with stale event"
                )
            if (
                purchase.last_event_at == current.last_event_at
                and purchase.last_event_id != current.last_event_id
            ):
                raise CommercialFulfillmentError(
                    "canonical purchase event ordering is ambiguous"
                )
            if current.tenant_id is not None and purchase.tenant_id != current.tenant_id:
                raise CommercialFulfillmentError("canonical purchase tenant cannot change")
            if current.account_id is not None and purchase.account_id != current.account_id:
                raise CommercialFulfillmentError("canonical purchase account cannot change")
            if current.buyer_email is not None and purchase.buyer_email != current.buyer_email:
                raise CommercialFulfillmentError("canonical purchase buyer email cannot change")
            if current.legal_name is not None and purchase.legal_name != current.legal_name:
                raise CommercialFulfillmentError("canonical purchase legal name cannot change")

        try:
            self._connection.execute(
                """
                INSERT INTO fm_commercial_purchases (
                    purchase_id, provider_id, external_order_id, plan_id, state,
                    created_at, updated_at, last_event_at, last_event_id, price_id,
                    external_subscription_id, external_customer_id, buyer_email,
                    legal_name, tenant_id, account_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (purchase_id) DO UPDATE SET
                    state = excluded.state,
                    updated_at = excluded.updated_at,
                    last_event_at = excluded.last_event_at,
                    last_event_id = excluded.last_event_id,
                    external_subscription_id = excluded.external_subscription_id,
                    external_customer_id = excluded.external_customer_id,
                    buyer_email = excluded.buyer_email,
                    legal_name = excluded.legal_name,
                    tenant_id = excluded.tenant_id,
                    account_id = excluded.account_id
                """,
                (
                    purchase.purchase_id,
                    purchase.provider_id,
                    purchase.external_order_id,
                    purchase.plan_id,
                    purchase.state.value,
                    _iso(purchase.created_at),
                    _iso(purchase.updated_at),
                    _iso(purchase.last_event_at),
                    purchase.last_event_id,
                    purchase.price_id,
                    purchase.external_subscription_id,
                    purchase.external_customer_id,
                    purchase.buyer_email,
                    purchase.legal_name,
                    purchase.tenant_id,
                    purchase.account_id,
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise CommercialFulfillmentError(
                "canonical commercial purchase conflicts with durable state"
            ) from exc
        return purchase

    def get_claim_by_digest(self, token_sha256: str) -> CommercialClaimRecord | None:
        row = self._connection.execute(
            """
            SELECT claim_id, purchase_id, token_sha256, created_at, expires_at, used_at
            FROM fm_commercial_claims
            WHERE token_sha256 = ?
            """,
            (token_sha256.strip().lower(),),
        ).fetchone()
        return None if row is None else self._claim(row)

    def get_claim_for_purchase(self, purchase_id: str) -> CommercialClaimRecord | None:
        row = self._connection.execute(
            """
            SELECT claim_id, purchase_id, token_sha256, created_at, expires_at, used_at
            FROM fm_commercial_claims
            WHERE purchase_id = ?
            """,
            (purchase_id.strip().lower(),),
        ).fetchone()
        return None if row is None else self._claim(row)

    def put_claim(self, claim: CommercialClaimRecord) -> CommercialClaimRecord:
        try:
            self._connection.execute(
                """
                INSERT INTO fm_commercial_claims (
                    claim_id, purchase_id, token_sha256, created_at, expires_at, used_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT (purchase_id) DO UPDATE SET
                    claim_id = excluded.claim_id,
                    token_sha256 = excluded.token_sha256,
                    created_at = excluded.created_at,
                    expires_at = excluded.expires_at,
                    used_at = excluded.used_at
                """,
                (
                    claim.claim_id,
                    claim.purchase_id,
                    claim.token_sha256,
                    _iso(claim.created_at),
                    _iso(claim.expires_at),
                    None if claim.used_at is None else _iso(claim.used_at),
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise CommercialFulfillmentError(
                "commercial claim conflicts with durable state"
            ) from exc
        return claim

    def consume_claim(self, claim_id: str, used_at: datetime) -> bool:
        cursor = self._connection.execute(
            """
            UPDATE fm_commercial_claims
            SET used_at = ?
            WHERE claim_id = ? AND used_at IS NULL
            """,
            (_iso(used_at), claim_id.strip().lower()),
        )
        return cursor.rowcount == 1

    def get_subscription(
        self,
        subscription_id: str,
    ) -> DurableCommercialSubscription | None:
        row = self._connection.execute(
            """
            SELECT subscription_id, purchase_id, tenant_id, plan_id,
                   entitlement_ids_json, quotas_json, status, period_start, period_end,
                   usage_json, provider_id, external_subscription_id,
                   last_event_id, last_event_at
            FROM fm_commercial_subscriptions
            WHERE subscription_id = ?
            """,
            (subscription_id.strip().lower(),),
        ).fetchone()
        return None if row is None else self._subscription(row)

    def get_subscription_by_external_reference(
        self,
        provider_id: str,
        external_subscription_id: str,
    ) -> DurableCommercialSubscription | None:
        row = self._connection.execute(
            """
            SELECT subscription_id, purchase_id, tenant_id, plan_id,
                   entitlement_ids_json, quotas_json, status, period_start, period_end,
                   usage_json, provider_id, external_subscription_id,
                   last_event_id, last_event_at
            FROM fm_commercial_subscriptions
            WHERE provider_id = ? AND external_subscription_id = ?
            """,
            (provider_id.strip().lower(), external_subscription_id.strip()),
        ).fetchone()
        return None if row is None else self._subscription(row)

    def get_subscription_for_tenant(
        self,
        tenant_id: str,
    ) -> DurableCommercialSubscription | None:
        row = self._connection.execute(
            """
            SELECT subscription_id, purchase_id, tenant_id, plan_id,
                   entitlement_ids_json, quotas_json, status, period_start, period_end,
                   usage_json, provider_id, external_subscription_id,
                   last_event_id, last_event_at
            FROM fm_commercial_subscriptions
            WHERE tenant_id = ?
            ORDER BY last_event_at DESC, subscription_id DESC
            LIMIT 1
            """,
            (tenant_id.strip().lower(),),
        ).fetchone()
        return None if row is None else self._subscription(row)

    def put_subscription(
        self,
        subscription: DurableCommercialSubscription,
    ) -> DurableCommercialSubscription:
        current = self.get_subscription(subscription.subscription_id)
        if current is not None:
            if (
                current.purchase_id != subscription.purchase_id
                or current.provider_id != subscription.provider_id
                or current.checkpoint.tenant_id != subscription.checkpoint.tenant_id
            ):
                raise CommercialFulfillmentError(
                    "canonical subscription identity cannot be rewritten"
                )
            if subscription.last_event_at < current.last_event_at:
                raise CommercialFulfillmentError(
                    "cannot overwrite canonical subscription with stale event"
                )
            if (
                subscription.last_event_at == current.last_event_at
                and subscription.last_event_id != current.last_event_id
            ):
                raise CommercialFulfillmentError(
                    "canonical subscription event ordering is ambiguous"
                )

        plan = subscription.checkpoint.plan
        quotas = [
            {"metric_id": quota.metric_id, "limit": quota.limit}
            for quota in plan.quotas
        ]
        usage = dict(subscription.checkpoint.usage)
        try:
            self._connection.execute(
                """
                INSERT INTO fm_commercial_subscriptions (
                    subscription_id, purchase_id, tenant_id, plan_id,
                    entitlement_ids_json, quotas_json, status, period_start, period_end,
                    usage_json, provider_id, external_subscription_id,
                    last_event_id, last_event_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (subscription_id) DO UPDATE SET
                    entitlement_ids_json = excluded.entitlement_ids_json,
                    quotas_json = excluded.quotas_json,
                    status = excluded.status,
                    period_start = excluded.period_start,
                    period_end = excluded.period_end,
                    usage_json = excluded.usage_json,
                    external_subscription_id = excluded.external_subscription_id,
                    last_event_id = excluded.last_event_id,
                    last_event_at = excluded.last_event_at
                """,
                (
                    subscription.subscription_id,
                    subscription.purchase_id,
                    subscription.checkpoint.tenant_id,
                    plan.plan_id,
                    json.dumps(plan.entitlement_ids, separators=(",", ":")),
                    json.dumps(quotas, separators=(",", ":"), sort_keys=True),
                    subscription.checkpoint.status.value,
                    _iso(subscription.checkpoint.period_start),
                    _iso(subscription.checkpoint.period_end),
                    json.dumps(usage, separators=(",", ":"), sort_keys=True),
                    subscription.provider_id,
                    subscription.external_subscription_id,
                    subscription.last_event_id,
                    _iso(subscription.last_event_at),
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise CommercialFulfillmentError(
                "canonical commercial subscription conflicts with durable state"
            ) from exc
        return subscription

    @staticmethod
    def _acquisition(row: Sequence[object]) -> CommercialAcquisitionRecord:
        return CommercialAcquisitionRecord(
            acquisition_id=_text(row[0], "acquisition_id"),
            idempotency_sha256=_text(row[1], "idempotency_sha256"),
            request_sha256=_text(row[2], "request_sha256"),
            provider_id=_text(row[3], "provider_id"),
            plan_id=_text(row[4], "plan_id"),
            price_id=_text(row[5], "price_id"),
            buyer_email=_text(row[6], "buyer_email"),
            legal_name=_text(row[7], "legal_name"),
            created_at=_dt(row[8], "created_at"),
            expires_at=_dt(row[9], "expires_at"),
            linked_purchase_id=_optional_text(row[10]),
        )

    @staticmethod
    def _validate_event_replay(
        existing: CommercialEventReceipt,
        received: CommercialEventReceipt,
    ) -> None:
        if (
            existing.provider_id,
            existing.event_id,
            existing.event_type,
            existing.external_order_id,
            existing.purchase_id,
            existing.occurred_at,
        ) != (
            received.provider_id,
            received.event_id,
            received.event_type,
            received.external_order_id,
            received.purchase_id,
            received.occurred_at,
        ):
            raise CommercialFulfillmentError(
                "commercial event identity was replayed with different content"
            )

    @staticmethod
    def _purchase(row: Sequence[object]) -> CommercialPurchaseRecord:
        return CommercialPurchaseRecord(
            purchase_id=_text(row[0], "purchase_id"),
            provider_id=_text(row[1], "provider_id"),
            external_order_id=_text(row[2], "external_order_id"),
            plan_id=_text(row[3], "plan_id"),
            state=CommercialPurchaseState(_text(row[4], "state")),
            created_at=_dt(row[5], "created_at"),
            updated_at=_dt(row[6], "updated_at"),
            last_event_at=_dt(row[7], "last_event_at"),
            last_event_id=_text(row[8], "last_event_id"),
            price_id=_optional_text(row[9]),
            external_subscription_id=_optional_text(row[10]),
            external_customer_id=_optional_text(row[11]),
            buyer_email=_optional_text(row[12]),
            legal_name=_optional_text(row[13]),
            tenant_id=_optional_text(row[14]),
            account_id=_optional_text(row[15]),
        )

    @staticmethod
    def _claim(row: Sequence[object]) -> CommercialClaimRecord:
        return CommercialClaimRecord(
            claim_id=_text(row[0], "claim_id"),
            purchase_id=_text(row[1], "purchase_id"),
            token_sha256=_text(row[2], "token_sha256"),
            created_at=_dt(row[3], "created_at"),
            expires_at=_dt(row[4], "expires_at"),
            used_at=None if row[5] is None else _dt(row[5], "used_at"),
        )

    @staticmethod
    def _subscription(row: Sequence[object]) -> DurableCommercialSubscription:
        plan = CommercialPlan(
            plan_id=_text(row[3], "plan_id"),
            entitlement_ids=_json_string_tuple(row[4], "entitlement_ids_json"),
            quotas=_json_quotas(row[5]),
        )
        checkpoint = SubscriptionCheckpoint(
            tenant_id=_text(row[2], "tenant_id"),
            plan=plan,
            status=SubscriptionStatus(_text(row[6], "status")),
            period_start=_dt(row[7], "period_start"),
            period_end=_dt(row[8], "period_end"),
            usage=_json_usage(row[9]),
        )
        return DurableCommercialSubscription(
            subscription_id=_text(row[0], "subscription_id"),
            purchase_id=_text(row[1], "purchase_id"),
            checkpoint=checkpoint,
            provider_id=_text(row[10], "provider_id"),
            external_subscription_id=_optional_text(row[11]),
            last_event_id=_text(row[12], "last_event_id"),
            last_event_at=_dt(row[13], "last_event_at"),
        )


class CommercialSqlUnitOfWork:
    def __init__(self, acquire: ConnectionContextFactory) -> None:
        self._acquire = acquire
        self._context: AbstractContextManager[_Connection] | None = None
        self._connection: _Connection | None = None
        self._commercial: CommercialSqlStore | None = None
        self._committed = False

    def __enter__(self) -> Self:
        context = self._acquire()
        connection = context.__enter__()
        self._context = context
        self._connection = connection
        self._commercial = CommercialSqlStore(connection)
        self._committed = False
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        connection = self._connection
        context = self._context
        if connection is None or context is None:
            return
        try:
            if exc_type is not None or not self._committed:
                connection.rollback()
        finally:
            context.__exit__(exc_type, exc, traceback)
            self._connection = None
            self._commercial = None
            self._context = None

    @property
    def commercial(self) -> CommercialSqlStore:
        if self._commercial is None:
            raise CommercialFulfillmentError("commercial unit of work is not active")
        return self._commercial

    def commit(self) -> None:
        if self._connection is None:
            raise CommercialFulfillmentError("commercial unit of work is not active")
        self._connection.commit()
        self._committed = True


class CanonicalCommercialDatabase:
    """Canonical commercial unit-of-work factory over the NFCore PostgreSQL boundary."""

    def __init__(self, acquire: ConnectionContextFactory) -> None:
        self._acquire = acquire

    def __call__(self) -> CommercialSqlUnitOfWork:
        return CommercialSqlUnitOfWork(self._acquire)


def postgres_canonical_commercial_database(
    fiscal_database: object,
) -> CanonicalCommercialDatabase:
    connection = getattr(fiscal_database, "connection", None)
    if not callable(connection):
        raise CommercialFulfillmentError(
            "fiscal database does not expose certified connection boundary"
        )
    return CanonicalCommercialDatabase(cast(ConnectionContextFactory, connection))


__all__ = [
    "CanonicalCommercialDatabase",
    "CommercialSqlStore",
    "CommercialSqlUnitOfWork",
    "postgres_canonical_commercial_database",
]
