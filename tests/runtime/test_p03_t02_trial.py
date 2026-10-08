"""Canonical runtime trial proofs; PostgreSQL real, delivery/key/data synthetic."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier

import pytest
from fastapi.testclient import TestClient

# Reuse certified synthetic setup; never introduce another commercial authority.
from test_p03_t01_acquisition import composition, load, security
from test_p03_t01_acquisition import settings as postgres_settings

from kordena_fiscal.product.billing import CommercialSubscription, SubscriptionStatus
from kordena_fiscal.product.commercial_fulfillment import CommercialPurchaseState
from kordena_fiscal.runtime import api as runtime_api
from kordena_fiscal.runtime.observability import StructuredLogger
from kordena_fiscal.security.s2s import FixedWindowRateLimiter

settings = postgres_settings

trial = load("p03_trial_examples", "runtime/test_cl12_governed_trial.py")
ENDPOINT = "/v1/commercial/trials"
KEY = "synthetic-runtime-trial-0001"
BODY = {
    "plan_id": "growth",
    "price_id": "growth-monthly",
    "buyer_email": "trial-owner@example.com",
    "legal_name": "Synthetic Trial LTDA",
}


class Delivery:
    def __init__(self):
        self.calls = []
        self.fail = False

    def deliver(self, *, email, reset):
        self.calls.append((email, reset))
        if self.fail:
            raise RuntimeError("synthetic-delivery-private-material")


def options(delivery=None):
    return {
        "commercial_trial_security": security(),
        "password_reset_delivery": delivery if delivery is not None else Delivery(),
    }


def publish(app):
    trial._publish_trial_pricing(app.state.nfcore_runtime.database)


def post(client, *, body=None, key=KEY, signed=True, now=None):
    encoded = json.dumps(BODY if body is None else body).encode()
    headers = {"Content-Type": "application/json"}
    if key is not None:
        headers["Idempotency-Key"] = key
    if signed:
        headers["X-NFCore-Signature"] = (
            security().sign(encoded, now=now or datetime.now(UTC)).header_value
        )
    return client.post(ENDPOINT, content=encoded, headers=headers)


def counts(app):
    with app.state.nfcore_runtime.database.connection() as connection:
        return tuple(
            connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in (
                "fm_commercial_purchases",
                "fm_commercial_subscriptions",
                "fm_human_accounts",
                "fm_control_plane_organizations",
            )
        )


def purchase(app):
    database = app.state.nfcore_runtime.database
    with database.connection() as connection:
        identifier = connection.execute(
            "SELECT purchase_id FROM fm_commercial_purchases"
        ).fetchone()[0]
    from kordena_fiscal.persistence.commercial_fulfillment import (
        postgres_canonical_commercial_database,
    )

    with postgres_canonical_commercial_database(database)() as uow:
        return uow.commercial.get_purchase(
            identifier
        ), uow.commercial.get_subscription_for_purchase(identifier)


@pytest.mark.parametrize("missing", ("security", "delivery", "database"))
def test_trial_wiring_is_absent_without_required_dependency(monkeypatch, missing):
    monkeypatch.setattr(runtime_api, "PostgresFiscalDatabase", composition._RuntimeDatabase)
    configured = options()
    if missing == "security":
        configured["commercial_trial_security"] = None
    elif missing == "delivery":
        configured["password_reset_delivery"] = None
    else:

        def unavailable(_dsn):
            raise RuntimeError("synthetic database failure")

        monkeypatch.setattr(runtime_api, "PostgresFiscalDatabase", unavailable)
    app = runtime_api.create_runtime_app(composition._settings(), **configured)
    with TestClient(app, base_url="https://testserver") as client:
        assert not client.get("/runtime/profile").json()["commercial_trial_configured"]
        assert app.state.nfcore_commercial_trial is None
        assert post(client).status_code == 404


def test_postgres_trial_runtime_restart_activation_login_and_expiry(settings):
    delivery = Delivery()
    app = runtime_api.create_runtime_app(settings, **options(delivery))
    publish(app)
    with TestClient(app, base_url="https://testserver") as client:
        assert client.get("/runtime/profile").json()["commercial_trial_configured"]
        created = post(client)
        assert created.status_code == 201
        assert created.headers["cache-control"] == "no-store, max-age=0"
        assert counts(app) == (1, 1, 1, 1)
        record, subscription = purchase(app)
        assert record.state is CommercialPurchaseState.ACTIVATION_PENDING
        assert subscription.checkpoint.status is SubscriptionStatus.TRIAL
        assert (
            subscription.checkpoint.period_end - subscription.checkpoint.period_start
            == timedelta(days=14)
        )
        assert delivery.calls[0][0] == BODY["buyer_email"]
        assert delivery.calls[0][1].reset_token not in created.text
        for forbidden in ("tenant", "account_id", "subscription_id", "buyer_email", "legal_name"):
            assert forbidden not in created.text
        first = created.json()
        tenant = record.tenant_id
    restarted_delivery = Delivery()
    restarted = runtime_api.create_runtime_app(settings, **options(restarted_delivery))
    with TestClient(restarted, base_url="https://testserver") as client:
        replay = post(client)
        assert replay.status_code == 200 and replay.json()["replay"]
        assert replay.json()["trial_expires_at"] == first["trial_expires_at"]
        assert counts(restarted) == (1, 1, 1, 1)
        record, subscription = purchase(restarted)
        assert record.tenant_id == tenant
        reset = restarted_delivery.calls[-1][1]
        password = "Synthetic-Trial-Password-2026"
        activated = client.post(
            "/v1/auth/password-reset/complete",
            json={
                "reset_token": reset.reset_token,
                "new_password": password,
            },
        )
        assert activated.status_code == 204
        assert (
            client.post(
                "/v1/auth/login",
                json={
                    "email": BODY["buyer_email"],
                    "password": password,
                },
            ).status_code
            == 200
        )
        assert client.get("/v1/portal/bootstrap").status_code == 200
        active_record, _ = purchase(restarted)
        assert active_record.state is CommercialPurchaseState.ACTIVE
        replay_active = post(client)
        assert replay_active.status_code == 200
        assert len(restarted_delivery.calls) == 1
        profile = client.get("/runtime/profile").json()
        assert not profile["fiscal_production_activated"]
        expired = restarted.state.nfcore_commercial_trial.expire(
            purchase_id=record.purchase_id,
            now=subscription.checkpoint.period_end,
        )
        assert expired.checkpoint.status is SubscriptionStatus.SUSPENDED
        assert not CommercialSubscription.restore(
            expired.checkpoint
        ).accepts_new_commercial_operations
        assert post(client).status_code == 409
        assert post(client, key=KEY + "-new").status_code == 409
        assert counts(restarted) == (1, 1, 1, 1)


@pytest.mark.parametrize(
    "field",
    (
        "tenant_id",
        "unit_id",
        "payment_success",
        "entitlements",
        "subscription_id",
        "production_approved",
        "trial_days",
    ),
)
def test_postgres_trial_rejects_browser_authority_before_any_write(settings, field):
    app = runtime_api.create_runtime_app(settings, **options())
    publish(app)
    with TestClient(app, base_url="https://testserver") as client:
        assert post(client, body={**BODY, field: "untrusted"}).status_code == 400
        assert counts(app) == (0, 0, 0, 0)


@pytest.mark.parametrize("failure", ("unsigned", "expired_signature", "missing_key", "tampered"))
def test_postgres_trial_requires_auth_and_idempotency(settings, failure):
    app = runtime_api.create_runtime_app(settings, **options())
    publish(app)
    with TestClient(app, base_url="https://testserver") as client:
        if failure == "unsigned":
            response = post(client, signed=False)
        elif failure == "expired_signature":
            response = post(client, now=datetime.now(UTC) - timedelta(hours=1))
        elif failure == "missing_key":
            response = post(client, key=None)
        else:
            encoded = json.dumps(BODY).encode()
            response = client.post(
                ENDPOINT,
                content=encoded + b" ",
                headers={
                    "Idempotency-Key": KEY,
                    "X-NFCore-Signature": security()
                    .sign(encoded, now=datetime.now(UTC))
                    .header_value,
                },
            )
        assert response.status_code == (400 if failure == "missing_key" else 401)
        assert counts(app) == (0, 0, 0, 0)


def test_postgres_trial_rate_limit_and_canonical_duplicate_conflict(settings):
    configured = options()
    configured["commercial_trial_rate_limiter"] = FixedWindowRateLimiter(
        max_requests=1, window_seconds=3600
    )
    app = runtime_api.create_runtime_app(settings, **configured)
    publish(app)
    with TestClient(app, base_url="https://testserver") as client:
        assert post(client).status_code == 201
        assert post(client, key=KEY + "-different").status_code == 429
    restarted = runtime_api.create_runtime_app(settings, **options())
    with TestClient(restarted, base_url="https://testserver") as client:
        assert post(client, key=KEY + "-different").status_code == 409
        assert post(client, body={**BODY, "buyer_email": "other@example.com"}).status_code == 409
        assert counts(restarted) == (1, 1, 1, 1)


@pytest.mark.parametrize("published", (False, True))
def test_postgres_trial_missing_pricing_or_ineligible_plan_writes_nothing(settings, published):
    app = runtime_api.create_runtime_app(settings, **options())
    if published:
        publish(app)
    with TestClient(app, base_url="https://testserver") as client:
        assert (
            post(client, body={**BODY, "plan_id": "foundation"} if published else None).status_code
            == 409
        )
        assert counts(app) == (0, 0, 0, 0)


def test_postgres_trial_delivery_failure_retries_same_state_and_redacts(settings):
    delivery = Delivery()
    delivery.fail = True
    logs = []
    app = runtime_api.create_runtime_app(
        settings,
        **options(delivery),
        logger=StructuredLogger(
            service="synthetic-trial",
            environment="test",
            sink=logs.append,
        ),
    )
    publish(app)
    with TestClient(app, base_url="https://testserver") as client:
        response = post(client)
        assert response.status_code == 503
        record, subscription = purchase(app)
        expiry = subscription.checkpoint.period_end
        delivery.fail = False
        retry = post(client)
        assert retry.status_code == 200
        retried, after = purchase(app)
        assert retried.tenant_id == record.tenant_id
        assert after.checkpoint.period_end == expiry
        assert counts(app) == (1, 1, 1, 1)
        assert delivery.calls[0][1].reset_token != delivery.calls[-1][1].reset_token
        rendered = response.text + retry.text + "".join(logs)
        for secret in (
            BODY["buyer_email"],
            BODY["legal_name"],
            "synthetic-delivery-private-material",
            delivery.calls[-1][1].reset_token,
        ):
            assert secret not in rendered


def test_postgres_trial_failure_before_owner_reserves_email_and_recovers(settings, monkeypatch):
    app = runtime_api.create_runtime_app(settings, **options())
    publish(app)
    service = app.state.nfcore_runtime_composition.commercial_provisioning
    original = service.provision

    def failed(**kwargs):
        raise RuntimeError("synthetic-private-storage-failure")

    monkeypatch.setattr(service, "provision", failed)
    with TestClient(app, base_url="https://testserver") as client:
        assert post(client).status_code == 503
        assert counts(app) == (1, 0, 0, 0)
        assert post(client, key=KEY + "-another").status_code == 409
        monkeypatch.setattr(service, "provision", original)
        assert post(client).status_code == 200
        assert counts(app) == (1, 1, 1, 1)


@pytest.mark.parametrize("collision", ("same_key", "same_email", "changed_payload"))
def test_postgres_concurrent_replicas_preserve_trial_identity(settings, collision):
    app = runtime_api.create_runtime_app(settings, **options())
    publish(app)
    other = runtime_api.create_runtime_app(settings, **options())
    barrier = Barrier(2)
    with (
        TestClient(app, base_url="https://testserver") as first,
        TestClient(other, base_url="https://testserver") as second,
    ):

        def request(client, index):
            barrier.wait(timeout=10)
            key = KEY + "-different" if collision == "same_email" and index else KEY
            body = (
                {**BODY, "buyer_email": "different@example.com"}
                if collision == "changed_payload" and index
                else BODY
            )
            return post(client, key=key, body=body).status_code

        with ThreadPoolExecutor(max_workers=2) as executor:
            statuses = list(executor.map(lambda item: request(*item), ((first, 0), (second, 1))))
        assert sorted(statuses) == ([200, 201] if collision == "same_key" else [201, 409])
        assert counts(app) == (1, 1, 1, 1)


def test_postgres_trial_contended_lock_times_out_without_state_and_recovers(settings):
    import hashlib

    app = runtime_api.create_runtime_app(settings, **options())
    publish(app)
    identity = "trial-owner:" + hashlib.sha256(BODY["buyer_email"].encode()).hexdigest()
    database = app.state.nfcore_runtime.database
    with TestClient(app, base_url="https://testserver") as client:
        with database.connection() as connection:
            connection.execute("SELECT pg_advisory_xact_lock(hashtextextended(?, 0))", (identity,))
            response = post(client)
            assert response.status_code == 503
            assert "lock" not in response.text
            assert counts(app) == (0, 0, 0, 0)
            connection.rollback()
        assert post(client).status_code == 201
        assert counts(app) == (1, 1, 1, 1)
