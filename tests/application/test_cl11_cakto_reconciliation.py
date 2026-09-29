from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

import psycopg
import pytest

from kordena_fiscal.application.cakto_reconciliation import (
    CaktoCanonicalCommercialBridgeService,
)
from kordena_fiscal.application.commercial_fulfillment import CommercialFulfillmentService
from kordena_fiscal.persistence.commercial_fulfillment import (
    postgres_canonical_commercial_database,
)
from kordena_fiscal.persistence.postgres import PostgresFiscalDatabase
from kordena_fiscal.product.billing import (
    CommercialPlan,
    CommercialSubscription,
    SubscriptionStatus,
)
from kordena_fiscal.product.cakto import (
    CaktoExternalSubscriptionStatus,
    CaktoPermanentProcessingError,
    CaktoPlanBinding,
    CaktoReconciliationSnapshot,
    CaktoWebhookEvent,
    CaktoWebhookInboxEntry,
)
from kordena_fiscal.product.commercial_fulfillment import (
    CommercialAcquisitionRecord,
    CommercialPurchaseRecord,
    CommercialPurchaseState,
    DurableCommercialSubscription,
    commercial_purchase_id,
)

DSN_ENV = "NFCORE_TEST_POSTGRES_DSN"
NOW = datetime(2026, 9, 28, 15, 0, tzinfo=UTC)
ACQUISITION_ID = "acq-0123456789abcdef0123456789abcdef"


class PricingHistory:
    def history(self) -> tuple[object, ...]:
        return ()


def _dsn() -> str:
    value = os.environ.get(DSN_ENV, "").strip()
    if not value:
        pytest.skip(f"{DSN_ENV} is required for Cakto canonical certification")
    return value


@pytest.fixture
def database() -> PostgresFiscalDatabase:
    dsn = _dsn()
    with psycopg.connect(dsn, autocommit=True) as connection:
        connection.execute("DROP SCHEMA public CASCADE")
        connection.execute("CREATE SCHEMA public")
    database = PostgresFiscalDatabase(dsn)
    database.initialize()
    try:
        yield database
    finally:
        database.close()


def _bridge(database: PostgresFiscalDatabase) -> CaktoCanonicalCommercialBridgeService:
    canonical = postgres_canonical_commercial_database(database)
    return CaktoCanonicalCommercialBridgeService(
        unit_of_work_factory=canonical,
        fulfillment=CommercialFulfillmentService(canonical),
        pricing=PricingHistory(),  # type: ignore[arg-type]
    )


def _binding() -> CaktoPlanBinding:
    return CaktoPlanBinding(
        external_product_id="product-1",
        external_offer_id="offer-1",
        plan_id="growth",
        entitlement_ids=("documents.issue",),
    )


def _entry(
    event_type: CaktoWebhookEvent,
    *,
    order_id: str,
    occurred_at: datetime,
    callback: str | None = None,
    subscription_id: str | None = "sub-1",
    customer_id: str = "481920",
    order_status: str = "paid",
) -> CaktoWebhookInboxEntry:
    return CaktoWebhookInboxEntry(
        event_key=f"{event_type.value}:{order_id}",
        event_type=event_type,
        order_id=order_id,
        external_product_id="product-1",
        external_offer_id="offer-1",
        external_customer_id=customer_id,
        order_status=order_status,
        occurred_at=occurred_at,
        payload_sha256="a" * 64,
        received_at=occurred_at + timedelta(seconds=1),
        callback_token=callback,
        external_subscription_id=subscription_id,
    )


def _acquisition(database: PostgresFiscalDatabase) -> CommercialAcquisitionRecord:
    record = CommercialAcquisitionRecord(
        acquisition_id=ACQUISITION_ID,
        idempotency_sha256="b" * 64,
        request_sha256="c" * 64,
        provider_id="cakto",
        plan_id="growth",
        price_id="growth-monthly",
        buyer_email="owner@example.com",
        legal_name="ACME Tecnologia LTDA",
        created_at=NOW - timedelta(minutes=5),
        expires_at=NOW + timedelta(hours=1),
    )
    canonical = postgres_canonical_commercial_database(database)
    with canonical() as uow:
        uow.commercial.put_acquisition(record)
        uow.commit()
    return record


def test_first_party_cakto_sale_creates_canonical_purchase_not_provider_tenant(
    database: PostgresFiscalDatabase,
) -> None:
    acquisition = _acquisition(database)
    bridge = _bridge(database)

    outcome = bridge.process(
        _entry(
            CaktoWebhookEvent.PURCHASE_APPROVED,
            order_id="order-1",
            occurred_at=NOW,
            callback=acquisition.acquisition_id,
        ),
        _binding(),
    )

    canonical = postgres_canonical_commercial_database(database)
    with canonical() as uow:
        purchase = uow.commercial.get_purchase_by_external_order("cakto", "order-1")
        linked = uow.commercial.get_acquisition(acquisition.acquisition_id)

    assert purchase is not None
    assert purchase.state is CommercialPurchaseState.UNCLAIMED
    assert purchase.billing_status is SubscriptionStatus.ACTIVE
    assert purchase.buyer_email == acquisition.buyer_email
    assert purchase.legal_name == acquisition.legal_name
    assert purchase.external_customer_id == "481920"
    assert purchase.tenant_id is None
    assert purchase.account_id is None
    assert linked is not None and linked.linked_purchase_id == purchase.purchase_id
    assert "481920" not in purchase.purchase_id
    assert "canonical_purchase:" in outcome

    replay = bridge.process(
        _entry(
            CaktoWebhookEvent.PURCHASE_APPROVED,
            order_id="order-1",
            occurred_at=NOW,
            callback=acquisition.acquisition_id,
        ),
        _binding(),
    )
    assert replay == outcome


def test_cakto_lifecycle_resolves_original_purchase_by_subscription_id(
    database: PostgresFiscalDatabase,
) -> None:
    _acquisition(database)
    bridge = _bridge(database)
    bridge.process(
        _entry(
            CaktoWebhookEvent.PURCHASE_APPROVED,
            order_id="opening-order",
            occurred_at=NOW,
            callback=ACQUISITION_ID,
        ),
        _binding(),
    )

    bridge.process(
        _entry(
            CaktoWebhookEvent.SUBSCRIPTION_PAUSED,
            order_id="different-order-from-provider",
            occurred_at=NOW + timedelta(minutes=1),
        ),
        _binding(),
    )
    canonical = postgres_canonical_commercial_database(database)
    with canonical() as uow:
        purchase = uow.commercial.get_purchase_by_external_subscription("cakto", "sub-1")
    assert purchase is not None
    assert purchase.external_order_id == "opening-order"
    assert purchase.billing_status is SubscriptionStatus.SUSPENDED

    bridge.process(
        _entry(
            CaktoWebhookEvent.SUBSCRIPTION_RESUMED,
            order_id="another-provider-order",
            occurred_at=NOW + timedelta(minutes=2),
        ),
        _binding(),
    )
    with canonical() as uow:
        recovered = uow.commercial.get_purchase(purchase.purchase_id)
    assert recovered is not None
    assert recovered.billing_status is SubscriptionStatus.ACTIVE

    bridge.process(
        _entry(
            CaktoWebhookEvent.REFUND,
            order_id="refund-provider-order",
            occurred_at=NOW + timedelta(minutes=3),
        ),
        _binding(),
    )
    with canonical() as uow:
        refunded = uow.commercial.get_purchase(purchase.purchase_id)
    assert refunded is not None
    assert refunded.state is CommercialPurchaseState.REFUNDED
    assert refunded.billing_status is SubscriptionStatus.CANCELED

    with pytest.raises(CaktoPermanentProcessingError, match="terminal"):
        bridge.process(
            _entry(
                CaktoWebhookEvent.SUBSCRIPTION_RESUMED,
                order_id="illegal-reactivation",
                occurred_at=NOW + timedelta(minutes=4),
            ),
            _binding(),
        )


def test_direct_cakto_sale_without_nfcore_callback_stays_identity_required(
    database: PostgresFiscalDatabase,
) -> None:
    canonical = postgres_canonical_commercial_database(database)
    direct = CommercialPurchaseRecord(
        purchase_id=commercial_purchase_id("cakto", "direct-order"),
        provider_id="cakto",
        external_order_id="direct-order",
        plan_id="growth",
        price_id="growth-monthly",
        state=CommercialPurchaseState.IDENTITY_REQUIRED,
        created_at=NOW,
        updated_at=NOW,
        last_event_at=NOW,
        last_event_id="purchase_approved:direct-order",
        external_subscription_id="direct-sub",
        external_customer_id="provider-customer-999",
        billing_status=SubscriptionStatus.ACTIVE,
    )
    with canonical() as uow:
        uow.commercial.put_purchase(direct)
        uow.commit()

    with canonical() as uow:
        restored = uow.commercial.get_purchase(direct.purchase_id)
    assert restored == direct
    assert restored is not None
    assert restored.tenant_id is None
    assert restored.account_id is None
    assert "provider-customer-999" not in restored.purchase_id


def test_provider_lifecycle_updates_existing_canonical_subscription(
    database: PostgresFiscalDatabase,
) -> None:
    canonical = postgres_canonical_commercial_database(database)
    with database.connection() as connection:
        connection.execute(
            "INSERT INTO fm_control_plane_organizations (tenant_id, legal_name) VALUES (?, ?)",
            ("tenant-core-1", "Canonical Tenant"),
        )
        connection.commit()

    purchase = CommercialPurchaseRecord(
        purchase_id=commercial_purchase_id("cakto", "provisioned-order"),
        provider_id="cakto",
        external_order_id="provisioned-order",
        plan_id="growth",
        price_id="growth-monthly",
        state=CommercialPurchaseState.ACTIVE,
        created_at=NOW,
        updated_at=NOW,
        last_event_at=NOW,
        last_event_id="purchase_approved:provisioned-order",
        external_subscription_id="sub-provisioned",
        external_customer_id="481920",
        buyer_email="owner@example.com",
        legal_name="Canonical Tenant",
        tenant_id="tenant-core-1",
        account_id="owner-core-1",
        billing_status=SubscriptionStatus.ACTIVE,
    )
    subscription = CommercialSubscription(
        tenant_id="tenant-core-1",
        plan=CommercialPlan("growth", ("documents.issue",)),
        status=SubscriptionStatus.ACTIVE,
        period_start=NOW,
        period_end=NOW + timedelta(days=30),
    )
    durable = DurableCommercialSubscription(
        subscription_id="commercial-subscription-test",
        purchase_id=purchase.purchase_id,
        checkpoint=subscription.checkpoint(),
        provider_id="cakto",
        external_subscription_id="sub-provisioned",
        last_event_id=purchase.last_event_id,
        last_event_at=NOW,
    )
    with canonical() as uow:
        uow.commercial.put_purchase(purchase)
        uow.commercial.put_subscription(durable)
        uow.commit()

    bridge = _bridge(database)
    bridge.process(
        _entry(
            CaktoWebhookEvent.SUBSCRIPTION_PAUSED,
            order_id="pause-new-order",
            occurred_at=NOW + timedelta(minutes=1),
            subscription_id="sub-provisioned",
        ),
        _binding(),
    )

    with canonical() as uow:
        updated_purchase = uow.commercial.get_purchase(purchase.purchase_id)
        updated_subscription = uow.commercial.get_subscription_for_purchase(
            purchase.purchase_id
        )
    assert updated_purchase is not None
    assert updated_purchase.billing_status is SubscriptionStatus.SUSPENDED
    assert updated_subscription is not None
    assert updated_subscription.checkpoint.status is SubscriptionStatus.SUSPENDED


def test_reconciliation_detects_provider_core_drift_without_mutating_state(
    database: PostgresFiscalDatabase,
) -> None:
    _acquisition(database)
    bridge = _bridge(database)
    bridge.process(
        _entry(
            CaktoWebhookEvent.PURCHASE_APPROVED,
            order_id="reconcile-order",
            occurred_at=NOW,
            callback=ACQUISITION_ID,
            subscription_id="reconcile-sub",
        ),
        _binding(),
    )

    active = bridge.reconcile(
        CaktoReconciliationSnapshot(
            external_customer_id="481920",
            external_product_id="product-1",
            external_offer_id="offer-1",
            status=CaktoExternalSubscriptionStatus.ACTIVE,
            observed_at=NOW + timedelta(minutes=1),
            external_subscription_id="reconcile-sub",
        ),
        _binding(),
    )
    paused = bridge.reconcile(
        CaktoReconciliationSnapshot(
            external_customer_id="481920",
            external_product_id="product-1",
            external_offer_id="offer-1",
            status=CaktoExternalSubscriptionStatus.PAUSED,
            observed_at=NOW + timedelta(minutes=2),
            external_subscription_id="reconcile-sub",
        ),
        _binding(),
    )
    assert active.drift is False
    assert active.canonical_status == "active"
    assert paused.drift is True
    assert paused.canonical_status == "active"
