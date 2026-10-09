"""Authenticated Command facts reuse local purchase, claim and activation authority."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from kordena_fiscal.application.commercial_acquisition import (
    CommercialPricingCurrentReader,
    CommercialReleaseCurrentReader,
)
from kordena_fiscal.application.commercial_activation import CommercialCustomerActivationService
from kordena_fiscal.application.commercial_fulfillment import CommercialFulfillmentService
from kordena_fiscal.persistence.command_commercial import CommandCommercialStore
from kordena_fiscal.product.command_commercial import (
    CommandBinding,
    CommandCommercialEvent,
    command_identity,
)
from kordena_fiscal.product.commercial_fulfillment import (
    CanonicalCommercialUnitOfWorkFactory,
    CommercialEventType,
    CommercialFulfillmentError,
    CommercialPurchaseState,
    ValidatedCommercialEvent,
    commercial_purchase_id,
)
from kordena_fiscal.security.s2s import InMemoryWebhookKeyRing, WebhookSecurity, WebhookSignature
from kordena_fiscal.security.secrets import SecretReference, SecretResolver
from kordena_fiscal.web.human_recovery import PasswordResetDelivery


@dataclass(frozen=True, slots=True)
class CommandCommercialResult:
    purchase_id: str
    replay: bool


class CommandCommercialReceiver:
    def __init__(
        self,
        *,
        store: CommandCommercialStore,
        secrets: SecretResolver,
        product_id: str,
        environment: str,
        unit_of_work_factory: CanonicalCommercialUnitOfWorkFactory,
        fulfillment: CommercialFulfillmentService,
        activation: CommercialCustomerActivationService,
        delivery: PasswordResetDelivery | None,
        pricing: CommercialPricingCurrentReader,
        release: CommercialReleaseCurrentReader,
    ) -> None:
        if secrets.environment != environment:
            raise CommercialFulfillmentError("Command secret environment mismatch")
        self.store = store
        self._secrets = secrets
        self._product_id = product_id
        self._environment = environment
        self._uow = unit_of_work_factory
        self._fulfillment = fulfillment
        self._activation = activation
        self._delivery = delivery
        self._pricing = pricing
        self._release = release

    def ready(self, *, now: datetime) -> bool:
        """Revalidate governed ingress without creating a commercial effect."""
        try:
            if now.tzinfo is None or now.utcoffset() is None:
                return False
            candidates = self.store.readiness_bindings(
                product_id=self._product_id, environment=self._environment,
            )
            for binding in candidates:
                if (
                    not binding.enabled or now >= binding.not_after
                    or binding.product_id != self._product_id
                    or binding.environment != self._environment
                    or binding.contract_version != 1
                ):
                    continue
                try:
                    with self._secrets.resolve(
                        SecretReference(binding.secret_reference, binding.secret_version),
                        scope=binding.scope,
                    ) as material:
                        valid_key = len(material.reveal()) >= 32
                    current = self.store.binding(binding.key_id)
                    if valid_key and current is not None and current[0] == binding:
                        return True
                except Exception:
                    # Rotation may leave an older candidate revoked. Another exact,
                    # currently usable binding may still serve this channel.
                    continue
        except Exception:
            pass
        return False

    def authenticate(
        self, body: bytes, signature: WebhookSignature, now: datetime
    ) -> CommandBinding:
        configured = self.store.binding(signature.key_id)
        if configured is None:
            raise CommercialFulfillmentError("Command binding unavailable")
        binding, _ = configured
        if (
            not binding.enabled
            or now >= binding.not_after
            or (binding.product_id != self._product_id or binding.environment != self._environment)
        ):
            raise CommercialFulfillmentError("Command binding unavailable")
        # The governed resolver enforces purpose/scope/version/revocation/expiry;
        # no raw key is stored in the receiver between requests.
        with self._secrets.resolve(
            SecretReference(binding.secret_reference, binding.secret_version),
            scope=binding.scope,
        ) as material:
            security = WebhookSecurity(
                key_resolver=InMemoryWebhookKeyRing(
                    active_key_id=binding.key_id,
                    keys={binding.key_id: material.reveal()},
                ),
                signing_key_id=binding.key_id,
            )
            security.verify(body, signature, now=now)
        return binding

    def receive(
        self, *, event: CommandCommercialEvent, binding: CommandBinding, now: datetime
    ) -> CommandCommercialResult:
        if (event.product_id, event.environment, event.version) != (
            binding.product_id,
            binding.environment,
            binding.contract_version,
        ) or event.occurred_at > now:
            raise CommercialFulfillmentError("Command event scope/time mismatch")
        with self.store.guard(event):
            # Recheck revocation/rotation after waiting for durable locks.
            current = self.store.binding(binding.key_id)
            if current is None or current[0] != binding or now >= binding.not_after:
                raise CommercialFulfillmentError("Command binding changed")
            with self._secrets.resolve(
                SecretReference(binding.secret_reference, binding.secret_version),
                scope=binding.scope,
            ):
                pass
            correlation = self.store.correlation(event)
            opening = correlation is None
            if opening:
                if event.event_type not in {
                    CommercialEventType.SALE_CONFIRMED,
                    CommercialEventType.SUBSCRIPTION_ACTIVATED,
                }:
                    raise CommercialFulfillmentError("unknown Command subscription")
                purchase_id = commercial_purchase_id(
                    "command",
                    command_identity(
                        "invoice", event.product_id, event.environment, event.command_invoice_id
                    ),
                )
                with self._uow() as uow:
                    acquisition = uow.commercial.get_acquisition(event.acquisition_id)
                if acquisition is None or (
                    acquisition.provider_id != "command"
                    or acquisition.plan_id != event.plan_id
                    or acquisition.price_id != event.price_id
                    or now >= acquisition.expires_at
                    or now < acquisition.created_at
                    or acquisition.linked_purchase_id is not None
                ):
                    raise CommercialFulfillmentError("Command acquisition mismatch")
                pricing = self._pricing.current
                release = self._release.current
                if pricing is None or release is None or not release.commercially_approved:
                    raise CommercialFulfillmentError("Command commercial path unavailable")
                if not any(
                    plan.enabled
                    and plan.plan_id == event.plan_id
                    and event.price_id in plan.price_ids
                    for plan in pricing.plans
                ):
                    raise CommercialFulfillmentError("Command canonical plan unavailable")
                if not pricing.price(event.price_id).enabled:
                    raise CommercialFulfillmentError("Command canonical price unavailable")
                external_order = command_identity(
                    "invoice", event.product_id, event.environment, event.command_invoice_id
                )
            else:
                assert correlation is not None
                customer, acquisition_id, invoice, purchase_id = correlation
                if customer != event.command_customer_id or acquisition_id != event.acquisition_id:
                    raise CommercialFulfillmentError("Command customer correlation mismatch")
                if (
                    event.event_type
                    in {
                        CommercialEventType.SALE_CONFIRMED,
                        CommercialEventType.SUBSCRIPTION_ACTIVATED,
                    }
                    and event.command_invoice_id != invoice
                ):
                    raise CommercialFulfillmentError("Command opening invoice mismatch")
                external_order = command_identity(
                    "invoice", event.product_id, event.environment, invoice
                )
            payment_reference = command_identity(
                "invoice",
                event.product_id,
                event.environment,
                event.command_invoice_id,
            )
            validated = ValidatedCommercialEvent(
                payment_reference=payment_reference,
                provider_id="command",
                event_id=command_identity(
                    "event", event.product_id, event.environment, event.event_id
                ),
                event_type=event.event_type,
                external_order_id=external_order,
                plan_id=event.plan_id,
                price_id=event.price_id,
                occurred_at=event.occurred_at,
                external_subscription_id=command_identity(
                    "subscription",
                    event.product_id,
                    event.environment,
                    event.command_subscription_id,
                ),
                external_customer_id=command_identity(
                    "customer", event.product_id, event.environment, event.command_customer_id
                ),
                # Lifecycle events must remain recoverable after acquisition TTL.
                acquisition_id=event.acquisition_id if opening else None,
            )
            replay, received_at, existing = self.store.reserve(
                event=event,
                binding_id=binding.binding_id,
                purchase_id=purchase_id,
                opening=opening,
                now=now,
            )
            if replay:
                with self._uow() as uow:
                    purchase = uow.commercial.get_purchase(purchase_id)
                if purchase is None:
                    raise CommercialFulfillmentError("Command processed result missing")
                return CommandCommercialResult(purchase_id, True)
            # If inbox commit survived but fulfillment failed, its correlation
            # exists. Recover opening identity from the persisted acquisition.
            with self._uow() as uow:
                purchase = uow.commercial.get_purchase(purchase_id)
                acquisition = uow.commercial.get_acquisition(event.acquisition_id)
            if purchase is None and not opening:
                if not existing:
                    raise CommercialFulfillmentError("Command opening event still pending")
                if (
                    acquisition is None
                    or acquisition.provider_id != "command"
                    or (
                        acquisition.plan_id != event.plan_id
                        or acquisition.price_id != event.price_id
                    )
                ):
                    raise CommercialFulfillmentError("pending Command acquisition mismatch")
                # Original authenticated receipt is durable, so processing delay
                # does not turn an already accepted acquisition into expired data.
                validated = ValidatedCommercialEvent(
                    payment_reference=validated.payment_reference,
                    provider_id=validated.provider_id,
                    event_id=validated.event_id,
                    event_type=validated.event_type,
                    external_order_id=validated.external_order_id,
                    plan_id=validated.plan_id,
                    price_id=validated.price_id,
                    occurred_at=validated.occurred_at,
                    external_subscription_id=validated.external_subscription_id,
                    external_customer_id=validated.external_customer_id,
                    acquisition_id=event.acquisition_id,
                )
            result = self._fulfillment.process(event=validated, received_at=received_at)
            if event.event_type in {
                CommercialEventType.SALE_CONFIRMED,
                CommercialEventType.SUBSCRIPTION_ACTIVATED,
            } and result.purchase.state in {
                CommercialPurchaseState.READY_TO_PROVISION,
                CommercialPurchaseState.ACTIVATION_PENDING,
            }:
                if self._delivery is None:
                    raise CommercialFulfillmentError("Command activation delivery unavailable")
                activated = self._activation.provision(purchase_id=purchase_id, now=now)
                assert activated.purchase.buyer_email is not None
                self._delivery.deliver(
                    email=activated.purchase.buyer_email, reset=activated.activation_reset
                )
            self.store.processed(event, now)
            return CommandCommercialResult(purchase_id, result.replay)
