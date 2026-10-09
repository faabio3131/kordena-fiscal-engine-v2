"""Provider-neutral commercial fulfillment application service.

Authenticated adapters emit ValidatedCommercialEvent values. This service owns the canonical
purchase transition and deliberately cannot create tenant, user, RBAC or fiscal authority.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime

from kordena_fiscal.product.billing import (
    CommercialSubscription,
    SubscriptionStatus,
    UsagePeriodCheckpoint,
)
from kordena_fiscal.product.commercial_fulfillment import (
    CanonicalCommercialUnitOfWorkFactory,
    CommercialAcquisitionRecord,
    CommercialEventReceipt,
    CommercialEventType,
    CommercialFulfillmentError,
    CommercialPurchaseRecord,
    CommercialPurchaseState,
    ValidatedCommercialEvent,
)
from kordena_fiscal.product.commercial_lifecycle import CommercialContract


@dataclass(frozen=True, slots=True)
class CommercialFulfillmentResult:
    purchase: CommercialPurchaseRecord
    replay: bool


class CommercialFulfillmentService:
    """Turn one authenticated external commercial fact into canonical purchase state."""

    _OPENING_EVENTS = frozenset(
        {
            CommercialEventType.SALE_CONFIRMED,
            CommercialEventType.SUBSCRIPTION_ACTIVATED,
        }
    )
    _NON_TERMINAL_EVENTS = frozenset(
        {
            CommercialEventType.SALE_CONFIRMED,
            CommercialEventType.SUBSCRIPTION_ACTIVATED,
            CommercialEventType.SUBSCRIPTION_RENEWED,
            CommercialEventType.SUBSCRIPTION_PAYMENT_LATE,
            CommercialEventType.SUBSCRIPTION_PAUSED,
            CommercialEventType.SUBSCRIPTION_RECOVERED,
        }
    )

    def __init__(
        self,
        unit_of_work_factory: CanonicalCommercialUnitOfWorkFactory,
        *,
        contract_factory: Callable[[CommercialPurchaseRecord, datetime, str], CommercialContract]
        | None = None,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._contract_factory = contract_factory

    def process(
        self,
        *,
        event: ValidatedCommercialEvent,
        received_at: datetime,
    ) -> CommercialFulfillmentResult:
        if not isinstance(event, ValidatedCommercialEvent):
            raise CommercialFulfillmentError("event must be ValidatedCommercialEvent")
        if received_at.tzinfo is None or received_at.utcoffset() is None:
            raise CommercialFulfillmentError("received_at must be timezone-aware")

        receipt = CommercialEventReceipt(
            provider_id=event.provider_id,
            event_id=event.event_id,
            event_type=event.event_type,
            external_order_id=event.external_order_id,
            purchase_id=event.purchase_id,
            occurred_at=event.occurred_at,
            received_at=received_at,
            payment_reference=event.payment_reference,
        )

        with self._unit_of_work_factory() as uow:
            _, replay = uow.commercial.receive_event(receipt)
            if replay:
                purchase = uow.commercial.get_purchase(event.purchase_id)
                if purchase is None:
                    raise CommercialFulfillmentError(
                        "commercial event receipt exists without canonical purchase"
                    )
                return CommercialFulfillmentResult(purchase=purchase, replay=True)

            acquisition = self._resolve_acquisition(
                uow.commercial,
                event,
                received_at=received_at,
            )
            current = uow.commercial.get_purchase(event.purchase_id)
            if current is not None:
                self._require_same_identity(current, event)
            contract = self._contract_for_event(uow.commercial, current, event)
            if (
                contract is not None
                and event.event_type is CommercialEventType.SUBSCRIPTION_RENEWED
            ):
                if event.payment_reference is None:
                    raise CommercialFulfillmentError("renewal requires authenticated paid invoice")
                _, credited = contract.renew(event.payment_reference, event.occurred_at)
                if credited:
                    assert current is not None
                    uow.commit()
                    return CommercialFulfillmentResult(purchase=current, replay=True)
            if current is None:
                purchase = self._create_purchase(
                    event,
                    received_at,
                    acquisition=acquisition,
                )
            else:
                purchase = self._transition_purchase(current, event, received_at)

            if contract is None and self._contract_factory is not None:
                contract = self._contract_factory(
                    purchase, event.occurred_at, event.payment_reference or event.external_order_id
                )
            if (
                contract is not None
                and event.event_type is CommercialEventType.SUBSCRIPTION_RENEWED
            ):
                assert event.payment_reference is not None
                durable = uow.commercial.get_subscription_for_purchase(purchase.purchase_id)
                if durable is not None:
                    contract = replace(
                        contract,
                        periods=tuple(
                            replace(p, usage=h.usage)
                            for p, h in zip(
                                contract.periods[:-1],
                                durable.checkpoint.previous_periods,
                                strict=True,
                            )
                        )
                        + (replace(contract.periods[-1], usage=durable.checkpoint.usage),),
                    )
                contract, _ = contract.renew(event.payment_reference, event.occurred_at)
            uow.commercial.put_purchase(purchase)
            if contract is not None:
                uow.commercial.put_contract(contract)
            self._sync_subscription_status(
                uow.commercial,
                purchase=purchase,
                event=event,
                contract=contract,
            )
            if acquisition is not None:
                uow.commercial.put_acquisition(
                    replace(acquisition, linked_purchase_id=purchase.purchase_id)
                )
            uow.commit()
            return CommercialFulfillmentResult(purchase=purchase, replay=False)

    def _contract_for_event(
        self,
        store: object,
        current: CommercialPurchaseRecord | None,
        event: ValidatedCommercialEvent,
    ) -> CommercialContract | None:
        get_contract = getattr(store, "get_contract", None)
        contract = get_contract(event.purchase_id) if callable(get_contract) else None
        if isinstance(contract, CommercialContract):
            return contract
        if current is None:
            return None
        if self._contract_factory is None:
            if event.event_type is CommercialEventType.SUBSCRIPTION_RENEWED:
                self._transition_purchase(current, event, event.occurred_at)
                raise CommercialFulfillmentError("contracted cadence snapshot is unavailable")
            return None
        get_first = getattr(store, "get_first_event", None)
        first = get_first(current.purchase_id) if callable(get_first) else None
        if first is None:
            raise CommercialFulfillmentError("original paid event is unavailable")
        contract = self._contract_factory(current, first.occurred_at, current.external_order_id)
        get_sub = getattr(store, "get_subscription_for_purchase", None)
        durable = get_sub(current.purchase_id) if callable(get_sub) else None
        if durable is not None:
            contract = replace(
                contract,
                plan=durable.checkpoint.plan,
                periods=(
                    replace(
                        contract.periods[0],
                        start=durable.checkpoint.period_start,
                        end=durable.checkpoint.period_end,
                        usage=durable.checkpoint.usage,
                    ),
                ),
            )
        return contract

    @classmethod
    def _create_purchase(
        cls,
        event: ValidatedCommercialEvent,
        received_at: datetime,
        *,
        acquisition: CommercialAcquisitionRecord | None = None,
    ) -> CommercialPurchaseRecord:
        if event.event_type not in cls._OPENING_EVENTS:
            raise CommercialFulfillmentError(
                "commercial lifecycle event cannot create an unknown purchase"
            )
        buyer_email = (
            event.buyer_email
            if event.buyer_email is not None
            else None if acquisition is None else acquisition.buyer_email
        )
        state = (
            CommercialPurchaseState.UNCLAIMED
            if buyer_email is not None
            else CommercialPurchaseState.IDENTITY_REQUIRED
        )
        return CommercialPurchaseRecord(
            purchase_id=event.purchase_id,
            provider_id=event.provider_id,
            external_order_id=event.external_order_id,
            plan_id=event.plan_id,
            price_id=event.price_id,
            state=state,
            created_at=received_at,
            updated_at=received_at,
            last_event_at=event.occurred_at,
            last_event_id=event.event_id,
            external_subscription_id=event.external_subscription_id,
            external_customer_id=event.external_customer_id,
            buyer_email=buyer_email,
            legal_name=None if acquisition is None else acquisition.legal_name,
            billing_status=cls._billing_status(event.event_type),
        )

    @classmethod
    def _transition_purchase(
        cls,
        current: CommercialPurchaseRecord,
        event: ValidatedCommercialEvent,
        received_at: datetime,
    ) -> CommercialPurchaseRecord:
        cls._require_same_identity(current, event)
        if event.occurred_at < current.last_event_at:
            raise CommercialFulfillmentError("stale commercial event rejected")
        if event.occurred_at == current.last_event_at and event.event_id != current.last_event_id:
            raise CommercialFulfillmentError("ambiguous same-time commercial event rejected")

        if event.event_type in cls._OPENING_EVENTS and current.billing_status in {
            SubscriptionStatus.SUSPENDED,
            SubscriptionStatus.CANCELED,
        }:
            raise CommercialFulfillmentError("opening event cannot resume blocked subscription")
        state = current.state
        if event.event_type in cls._NON_TERMINAL_EVENTS:
            if current.state in {
                CommercialPurchaseState.CANCELED,
                CommercialPurchaseState.REFUNDED,
            }:
                raise CommercialFulfillmentError(
                    "terminal commercial purchase cannot be reactivated by provider event"
                )
        elif event.event_type is CommercialEventType.SUBSCRIPTION_CANCELED:
            if current.state is not CommercialPurchaseState.REFUNDED:
                state = CommercialPurchaseState.CANCELED
        elif event.event_type in {
            CommercialEventType.REFUND_CONFIRMED,
            CommercialEventType.CHARGEBACK_CONFIRMED,
        }:
            state = CommercialPurchaseState.REFUNDED
        else:
            raise CommercialFulfillmentError("unsupported commercial event transition")

        return replace(
            current,
            state=state,
            billing_status=cls._billing_status(event.event_type),
            updated_at=received_at,
            last_event_at=event.occurred_at,
            last_event_id=event.event_id,
            external_subscription_id=(
                current.external_subscription_id or event.external_subscription_id
            ),
            external_customer_id=current.external_customer_id or event.external_customer_id,
            buyer_email=current.buyer_email or event.buyer_email,
        )

    @staticmethod
    def _billing_status(event_type: CommercialEventType) -> SubscriptionStatus:
        if event_type in {
            CommercialEventType.SALE_CONFIRMED,
            CommercialEventType.SUBSCRIPTION_ACTIVATED,
            CommercialEventType.SUBSCRIPTION_RENEWED,
            CommercialEventType.SUBSCRIPTION_RECOVERED,
        }:
            return SubscriptionStatus.ACTIVE
        if event_type is CommercialEventType.SUBSCRIPTION_PAYMENT_LATE:
            return SubscriptionStatus.GRACE
        if event_type is CommercialEventType.SUBSCRIPTION_PAUSED:
            return SubscriptionStatus.SUSPENDED
        if event_type in {
            CommercialEventType.SUBSCRIPTION_CANCELED,
            CommercialEventType.REFUND_CONFIRMED,
            CommercialEventType.CHARGEBACK_CONFIRMED,
        }:
            return SubscriptionStatus.CANCELED
        raise CommercialFulfillmentError("unsupported commercial billing transition")

    @staticmethod
    def _sync_subscription_status(
        store: object,
        *,
        purchase: CommercialPurchaseRecord,
        event: ValidatedCommercialEvent,
        contract: CommercialContract | None = None,
    ) -> None:
        get_subscription = getattr(store, "get_subscription_for_purchase", None)
        put_subscription = getattr(store, "put_subscription", None)
        if not callable(get_subscription) or not callable(put_subscription):
            return
        durable = get_subscription(purchase.purchase_id)
        if durable is None:
            return
        target = purchase.billing_status
        if target is None:
            return
        checkpoint = durable.checkpoint
        if contract is not None:
            last = contract.periods[-1]
            checkpoint = replace(
                checkpoint,
                plan=contract.plan,
                period_start=last.start,
                period_end=last.end,
                usage=last.usage,
                grace_days=contract.grace_days,
                previous_periods=tuple(
                    UsagePeriodCheckpoint(p.start, p.end, p.usage) for p in contract.periods[:-1]
                ),
            )
        subscription = CommercialSubscription.restore(checkpoint)
        try:
            subscription.transition(target)
        except ValueError as exc:
            raise CommercialFulfillmentError(
                "canonical subscription lifecycle transition is invalid"
            ) from exc
        put_subscription(
            replace(
                durable,
                checkpoint=subscription.checkpoint(),
                external_subscription_id=(
                    durable.external_subscription_id or event.external_subscription_id
                ),
                last_event_id=event.event_id,
                last_event_at=event.occurred_at,
            )
        )

    @staticmethod
    def _resolve_acquisition(
        store: object,
        event: ValidatedCommercialEvent,
        *,
        received_at: datetime,
    ) -> CommercialAcquisitionRecord | None:
        if event.acquisition_id is None:
            return None
        get_acquisition = getattr(store, "get_acquisition", None)
        if not callable(get_acquisition):
            raise CommercialFulfillmentError(
                "canonical acquisition persistence is unavailable"
            )
        acquisition = get_acquisition(event.acquisition_id)
        if not isinstance(acquisition, CommercialAcquisitionRecord):
            raise CommercialFulfillmentError("commercial acquisition was not found")
        if received_at >= acquisition.expires_at:
            raise CommercialFulfillmentError(
                "commercial acquisition reference has expired"
            )
        if acquisition.linked_purchase_id not in {None, event.purchase_id}:
            raise CommercialFulfillmentError(
                "commercial acquisition is already linked to another purchase"
            )
        if acquisition.provider_id != event.provider_id:
            raise CommercialFulfillmentError("acquisition provider identity mismatch")
        if acquisition.plan_id != event.plan_id:
            raise CommercialFulfillmentError("acquisition plan identity mismatch")
        if event.price_id is None or acquisition.price_id != event.price_id:
            raise CommercialFulfillmentError("acquisition price identity mismatch")
        if (
            event.buyer_email is not None
            and event.buyer_email != acquisition.buyer_email
        ):
            raise CommercialFulfillmentError("acquisition buyer email identity mismatch")
        return acquisition

    @staticmethod
    def _require_same_identity(
        current: CommercialPurchaseRecord,
        event: ValidatedCommercialEvent,
    ) -> None:
        if current.provider_id != event.provider_id:
            raise CommercialFulfillmentError("provider identity mismatch")
        if current.external_order_id != event.external_order_id:
            raise CommercialFulfillmentError("external order identity mismatch")
        if current.plan_id != event.plan_id:
            raise CommercialFulfillmentError("canonical plan cannot change")
        if (
            current.price_id is not None
            and event.price_id is not None
            and current.price_id != event.price_id
        ):
            raise CommercialFulfillmentError("canonical price cannot change")
        if (
            current.external_subscription_id is not None
            and event.external_subscription_id is not None
            and current.external_subscription_id != event.external_subscription_id
        ):
            raise CommercialFulfillmentError("external subscription identity conflict")
        if (
            current.external_customer_id is not None
            and event.external_customer_id is not None
            and current.external_customer_id != event.external_customer_id
        ):
            raise CommercialFulfillmentError("external customer identity conflict")
        if (
            current.buyer_email is not None
            and event.buyer_email is not None
            and current.buyer_email != event.buyer_email
        ):
            raise CommercialFulfillmentError("buyer email identity conflict")


__all__ = ["CommercialFulfillmentResult", "CommercialFulfillmentService"]
