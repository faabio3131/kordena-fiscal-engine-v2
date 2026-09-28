"""Provider-neutral commercial fulfillment application service.

Authenticated adapters emit ValidatedCommercialEvent values. This service owns the canonical
purchase transition and deliberately cannot create tenant, user, RBAC or fiscal authority.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime

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
            CommercialEventType.SUBSCRIPTION_RECOVERED,
        }
    )

    def __init__(self, unit_of_work_factory: CanonicalCommercialUnitOfWorkFactory) -> None:
        self._unit_of_work_factory = unit_of_work_factory

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
            if current is None:
                purchase = self._create_purchase(
                    event,
                    received_at,
                    acquisition=acquisition,
                )
            else:
                purchase = self._transition_purchase(current, event, received_at)

            uow.commercial.put_purchase(purchase)
            if acquisition is not None:
                uow.commercial.put_acquisition(
                    replace(acquisition, linked_purchase_id=purchase.purchase_id)
                )
            uow.commit()
            return CommercialFulfillmentResult(purchase=purchase, replay=False)

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
        if (
            event.occurred_at == current.last_event_at
            and event.event_id != current.last_event_id
        ):
            raise CommercialFulfillmentError("ambiguous same-time commercial event rejected")

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
