"""Command ingress: synthetic keys/checkout, real PostgreSQL when CI supplies DSN."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from test_p03_t01_acquisition import acquisition, composition, publish, security
from test_p03_t01_acquisition import post as start_acquisition
from test_p03_t01_acquisition import settings as postgres_settings

from kordena_fiscal.application.command_commercial import CommandCommercialReceiver
from kordena_fiscal.control_plane.models import AdminPrincipal, ControlPlanePermission
from kordena_fiscal.persistence.commercial_fulfillment import postgres_canonical_commercial_database
from kordena_fiscal.product.command_commercial import CommandBinding, CommandCommercialEvent
from kordena_fiscal.product.commercial_fulfillment import CommercialFulfillmentError
from kordena_fiscal.runtime import api as runtime_api
from kordena_fiscal.security.s2s import (
    FixedWindowRateLimiter,
    InMemoryWebhookKeyRing,
    WebhookSecurity,
)
from kordena_fiscal.security.secrets import (
    InMemorySecretBackend,
    SecretReference,
    SecretResolutionError,
    SecretResolver,
    SecretScope,
)
from kordena_fiscal.web.command_commercial import create_command_commercial_router

settings = postgres_settings
ENDPOINT = "/v1/commercial/command/events"
SECRET = b"synthetic-command-webhook-material-only-2026"
REF = "sec_synthetic_command_key_0001"
ACTOR = AdminPrincipal(
    actor_id="synthetic-platform-command",
    permissions=frozenset(
        {
            ControlPlanePermission.COMMERCIAL_CONFIG_WRITE,
            ControlPlanePermission.SECRET_REFERENCE_WRITE,
        }
    ),
    global_scope=True,
)


class SyntheticExternalBackend(InMemorySecretBackend):
    """Only a CI harness; NOT proof of a real external backend (P6)."""

    @property
    def production_safe(self):
        return True


def binding():
    return CommandBinding(
        key_id="command-v1",
        binding_id="command-channel",
        product_id="nfcore",
        environment="staging",
        secret_reference=REF,
        secret_version=1,
        not_after=datetime.now(UTC) + timedelta(days=1),
    )


def backend():
    result = SyntheticExternalBackend()
    result.put(reference_id=REF, scope=binding().scope, value=SECRET)
    return result


def signing(key="command-v1", secret=SECRET):
    return WebhookSecurity(
        key_resolver=InMemoryWebhookKeyRing(
            active_key_id=key,
            keys={key: secret},
        ),
        signing_key_id=key,
    )


def envelope(acquisition_id="acq-synthetic"):
    return {
        "version": 1,
        "event_id": "evt-synthetic-1",
        "event_type": "sale_confirmed",
        "occurred_at": (datetime.now(UTC) - timedelta(minutes=1)).isoformat(),
        "product_id": "nfcore",
        "environment": "staging",
        "command_customer_id": "customer-synthetic-1",
        "command_subscription_id": "subscription-synthetic-1",
        "command_invoice_id": "invoice-synthetic-1",
        "acquisition_id": acquisition_id,
        "plan_id": "growth",
        "price_id": "growth-monthly",
    }


def post(client, payload, *, signer=None, at=None, raw=None, signed=True):
    encoded = json.dumps(payload).encode() if raw is None else raw
    headers = {"Content-Type": "application/json"}
    if signed:
        headers["X-NFCore-Signature"] = (
            (signer or signing())
            .sign(
                encoded,
                now=at or datetime.now(UTC),
            )
            .header_value
        )
    return client.post(ENDPOINT, content=encoded, headers=headers)


def auth_app(secret_backend=None, configured=None):
    chosen = binding() if configured is None else configured
    store = SimpleNamespace(binding=lambda _key: (chosen, 1) if _key == chosen.key_id else None)
    receiver = CommandCommercialReceiver(
        store=store,
        secrets=SecretResolver(secret_backend or backend(), environment="staging"),
        product_id="nfcore",
        environment="staging",
        unit_of_work_factory=None,
        fulfillment=None,
        activation=None,
        delivery=None,
        pricing=None,
        release=None,
    )
    app = FastAPI()
    app.include_router(
        create_command_commercial_router(
            receiver,
            rate_limiter=FixedWindowRateLimiter(max_requests=10, window_seconds=60),
        )
    )
    return app


@pytest.mark.parametrize(
    "field",
    (
        "tenant_id",
        "unit_id",
        "role",
        "permissions",
        "buyer_email",
        "payment_status",
        "gateway_secret",
        "cpf",
        "unknown",
    ),
)
def test_schema_rejects_authority_pii_and_unknown_fields(field):
    payload = {**envelope(), field: "forged"}
    with TestClient(auth_app()) as client:
        assert post(client, payload).status_code == 400


@pytest.mark.parametrize("raw", (b"null", b"[]", b"{}", b'{"version":1,"version":1}', b"\xff"))
def test_strict_envelope_denies_invalid_json_and_duplicate_fields(raw):
    with TestClient(auth_app()) as client:
        assert post(client, None, raw=raw).status_code == 400


@pytest.mark.parametrize("variant", ("unsigned", "stale", "future", "wrong-key", "wrong-secret"))
def test_command_authentication_fails_closed(variant):
    options = {}
    if variant == "unsigned":
        options["signed"] = False
    elif variant == "stale":
        options["at"] = datetime.now(UTC) - timedelta(seconds=301)
    elif variant == "future":
        options["at"] = datetime.now(UTC) + timedelta(minutes=2)
    elif variant == "wrong-key":
        options["signer"] = signing("unknown")
    else:
        options["signer"] = signing(secret=b"synthetic-wrong-secret-material-2026")
    with TestClient(auth_app()) as client:
        assert post(client, envelope(), **options).status_code == 401


@pytest.mark.parametrize(
    "variant",
    (
        "disabled",
        "expired",
        "product",
        "environment",
        "revoked",
        "scope",
        "unavailable",
        "secret-expired",
        "secret-version",
    ),
)
def test_binding_and_secret_resolution_denials_are_sanitized(variant):
    configured = binding()
    secret_backend = backend()
    if variant == "disabled":
        configured = replace(configured, enabled=False)
    elif variant == "expired":
        configured = replace(configured, not_after=datetime.now(UTC) - timedelta(seconds=1))
    elif variant == "product":
        configured = replace(configured, product_id="other-saas")
    elif variant == "environment":
        configured = replace(configured, environment="production")
    elif variant == "revoked":
        secret_backend.revoke(SecretReference(REF, 1))
    elif variant == "secret-expired":
        secret_backend = SyntheticExternalBackend()
        secret_backend.put(
            reference_id=REF,
            scope=configured.scope,
            value=SECRET,
            not_after=datetime.now(UTC) - timedelta(seconds=1),
        )
    elif variant == "secret-version":
        configured = replace(configured, secret_version=2)
    elif variant == "scope":
        secret_backend = SyntheticExternalBackend()
        secret_backend.put(
            reference_id=REF,
            scope=SecretScope("other", None, "commercial.command.webhook"),
            value=SECRET,
        )
    else:

        def unavailable(_ref):
            raise RuntimeError("synthetic-private-secret-backend-information")

        secret_backend.resolve = unavailable
    with TestClient(auth_app(secret_backend, configured)) as client:
        response = post(client, envelope())
        assert response.status_code == 401
        assert "private" not in response.text and REF not in response.text


def test_http_body_is_bounded_even_without_content_length():
    with TestClient(auth_app()) as client:
        response = client.post(ENDPOINT, content=iter([b"x" * 32000, b"x" * 34000]))
        assert response.status_code == 413


class Checkout(acquisition.SyntheticCheckout):
    provider_id = "command"


class Delivery:
    def __init__(self):
        self.calls = []
        self.fail = False

    def deliver(self, *, email, reset):
        if self.fail:
            raise RuntimeError("synthetic-private-delivery-details")
        self.calls.append((email, reset))


def setup(settings):
    secrets = backend()
    checkout = Checkout()
    delivery = Delivery()
    options = dict(
        command_secret_resolver=SecretResolver(secrets, environment="staging"),
        commercial_checkout_projector=checkout,
        commercial_checkout_starter=checkout,
        commercial_acquisition_security=security(),
        password_reset_delivery=delivery,
    )
    app = runtime_api.create_runtime_app(settings, **options)
    publish(app)
    app.state.nfcore_command_commercial.store.configure(
        actor=ACTOR,
        binding=binding(),
        expected_revision=None,
        now=datetime.now(UTC),
    )
    return app, options, secrets, delivery


def begin(client):
    response = start_acquisition(client, security())
    assert response.status_code == 201, response.text
    return envelope(response.json()["acquisition_reference"])


def count(app, table):
    with app.state.nfcore_runtime.database.connection() as connection:
        return connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def test_postgres_event_replay_rotation_and_restart_preserve_one_purchase(settings):
    app, options, secrets, _ = setup(settings)
    with TestClient(app, base_url="https://testserver") as client:
        payload = begin(client)
        response = post(client, payload)
        assert response.status_code == 202, response.text
        purchase_id = response.json()["purchase_id"]
        assert post(client, payload).json()["replay"]
        assert count(app, "fm_commercial_purchases") == 1
        assert count(app, "fm_command_commercial_inbox") == 1
        assert count(app, "fm_human_accounts") == count(app, "fm_control_plane_organizations") == 0
        rotated = replace(binding(), key_id="command-v2")
        app.state.nfcore_command_commercial.store.configure(
            actor=ACTOR,
            binding=rotated,
            expected_revision=None,
            now=datetime.now(UTC),
        )
        assert post(client, payload, signer=signing("command-v2")).json()["replay"]
        assert post(client, {**payload, "plan_id": "other-plan"}).status_code == 409
    restarted = runtime_api.create_runtime_app(settings, **options)
    with TestClient(restarted, base_url="https://testserver") as client:
        replay = post(client, payload)
        assert replay.status_code == 200 and replay.json()["purchase_id"] == purchase_id
        assert count(restarted, "fm_commercial_purchases") == 1
        assert count(restarted, "fm_command_commercial_correlations") == 1


@pytest.mark.parametrize(
    "field",
    (
        "product_id",
        "environment",
        "command_customer_id",
        "command_subscription_id",
        "acquisition_id",
        "plan_id",
        "price_id",
        "command_invoice_id",
    ),
)
def test_postgres_correlation_rejects_other_customer_product_and_purchase(settings, field):
    app, _, _, _ = setup(settings)
    with TestClient(app, base_url="https://testserver") as client:
        payload = begin(client)
        assert post(client, payload).status_code == 202
        altered = {
            **payload,
            "event_id": "evt-2",
            "event_type": "subscription_activated",
            field: "other-synthetic",
        }
        assert post(client, altered).status_code == 409
        assert count(app, "fm_commercial_purchases") == 1


def test_postgres_failure_after_inbox_commit_recovers_after_restart(settings, monkeypatch):
    app, options, _, _ = setup(settings)
    with TestClient(app, base_url="https://testserver") as client:
        payload = begin(client)
        service = app.state.nfcore_runtime_composition.commercial_fulfillment
        original = service.process

        def fail(**_kwargs):
            raise RuntimeError("synthetic-private-failure-after-inbox")

        monkeypatch.setattr(service, "process", fail)
        response = post(client, payload)
        assert response.status_code == 503 and "private" not in response.text
        assert count(app, "fm_command_commercial_inbox") == 1
        assert count(app, "fm_commercial_purchases") == 0
        monkeypatch.setattr(service, "process", original)
    restarted = runtime_api.create_runtime_app(settings, **options)
    with TestClient(restarted, base_url="https://testserver") as client:
        assert post(client, payload).status_code == 202
        assert count(restarted, "fm_commercial_purchases") == 1
        assert post(client, payload).status_code == 200


def test_postgres_concurrent_duplicate_serializes_canonical_effects(settings):
    app, _, _, _ = setup(settings)
    with TestClient(app, base_url="https://testserver") as client:
        payload = begin(client)
        with ThreadPoolExecutor(max_workers=2) as executor:
            responses = list(executor.map(lambda _: post(client, payload), range(2)))
        assert sorted(response.status_code for response in responses) == [200, 202]
        assert count(app, "fm_commercial_purchases") == 1
        assert count(app, "fm_command_commercial_inbox") == 1


def test_postgres_claim_activation_delivery_failure_replays_without_duplicate_owner(settings):
    app, _, _, delivery = setup(settings)
    with TestClient(app, base_url="https://testserver") as client:
        payload = begin(client)
        first = post(client, payload)
        assert first.status_code == 202
        purchase_id = first.json()["purchase_id"]
        services = app.state.nfcore_runtime_composition
        claim = services.commercial_claim.issue(purchase_id=purchase_id, now=datetime.now(UTC))
        services.commercial_claim.complete(
            claim_token=claim.claim_token, legal_name="Synthetic LTDA", now=datetime.now(UTC)
        )
        activation = {
            **payload,
            "event_id": "evt-activation",
            "event_type": "subscription_activated",
            "occurred_at": (datetime.now(UTC) - timedelta(seconds=1)).isoformat(),
        }
        delivery.fail = True
        assert post(client, activation).status_code == 503
        assert count(app, "fm_human_accounts") == 1
        assert count(app, "fm_control_plane_organizations") == 1
        delivery.fail = False
        assert post(client, activation).status_code == 200
        assert len(delivery.calls) == 1
        assert post(client, activation).status_code == 200
        assert len(delivery.calls) == 1
        assert count(app, "fm_commercial_subscriptions") == 1
        commercial = postgres_canonical_commercial_database(app.state.nfcore_runtime.database)
        with commercial() as uow:
            purchase = uow.commercial.get_purchase(purchase_id)
        assert purchase.state.value == "activation_pending"
        assert (
            not app.state.nfcore_runtime.database.human_accounts()
            .by_id(purchase.account_id)
            .platform_admin
        )


def test_postgres_binding_admin_requires_global_scope_permissions_and_revision(settings):
    app, _, _, _ = setup(settings)
    try:
        store = app.state.nfcore_command_commercial.store
        for actor in (
            replace(ACTOR, global_scope=False),
            replace(ACTOR, permissions=frozenset({ControlPlanePermission.COMMERCIAL_CONFIG_WRITE})),
        ):
            with pytest.raises(CommercialFulfillmentError):
                store.configure(
                    actor=actor, binding=binding(), expected_revision=1, now=datetime.now(UTC)
                )
        current, revision = store.binding("command-v1")
        with pytest.raises(CommercialFulfillmentError):
            store.configure(
                actor=ACTOR, binding=current, expected_revision=revision + 1, now=datetime.now(UTC)
            )
        assert (
            store.configure(
                actor=ACTOR,
                binding=replace(current, enabled=False),
                expected_revision=revision,
                now=datetime.now(UTC),
            )
            == 2
        )
        assert count(app, "fm_command_binding_audit") == 2
    finally:
        app.state.nfcore_runtime.close()


def test_command_route_absent_without_configured_secret_resolver(monkeypatch):
    monkeypatch.setattr(runtime_api, "PostgresFiscalDatabase", composition._RuntimeDatabase)
    app = runtime_api.create_runtime_app(composition._settings())
    with TestClient(app, base_url="https://testserver") as client:
        assert post(client, envelope()).status_code == 404
        assert not client.get("/runtime/profile").json()["command_webhook_configured"]


def test_postgres_secret_revocation_after_authentication_prevents_any_effect(settings):
    app, _, secrets, _ = setup(settings)
    try:
        receiver = app.state.nfcore_command_commercial
        payload = envelope()
        encoded = json.dumps(payload).encode()
        now = datetime.now(UTC)
        authenticated = receiver.authenticate(encoded, signing().sign(encoded, now=now), now)
        secrets.revoke(SecretReference(REF, 1))
        with pytest.raises(SecretResolutionError, match="revoked"):
            receiver.receive(
                event=CommandCommercialEvent.parse(encoded), binding=authenticated, now=now
            )
        assert count(app, "fm_command_commercial_inbox") == 0
        assert count(app, "fm_commercial_purchases") == 0
    finally:
        app.state.nfcore_runtime.close()


def test_postgres_failure_after_fulfillment_commit_recovers_original_result(settings, monkeypatch):
    app, options, _, _ = setup(settings)
    with TestClient(app, base_url="https://testserver") as client:
        payload = begin(client)

        def fail(*_args):
            raise RuntimeError("synthetic-private-result-commit-failure")

        monkeypatch.setattr(app.state.nfcore_command_commercial.store, "processed", fail)
        assert post(client, payload).status_code == 503
        assert count(app, "fm_commercial_purchases") == 1
        assert count(app, "fm_command_commercial_inbox") == 1
    restarted = runtime_api.create_runtime_app(settings, **options)
    with TestClient(restarted, base_url="https://testserver") as client:
        assert post(client, payload).status_code == 200
        assert post(client, payload).status_code == 200
        assert count(restarted, "fm_commercial_purchases") == 1
        with restarted.state.nfcore_runtime.database.connection() as connection:
            assert (
                connection.execute(
                    "SELECT processed_at FROM fm_command_commercial_inbox"
                ).fetchone()[0]
                is not None
            )


def test_postgres_expired_acquisition_cannot_open_purchase(settings):
    app, _, _, _ = setup(settings)
    with TestClient(app, base_url="https://testserver") as client:
        payload = begin(client)
        commercial = postgres_canonical_commercial_database(app.state.nfcore_runtime.database)
        with commercial() as uow:
            acquired = uow.commercial.get_acquisition(payload["acquisition_id"])
            uow.commercial.put_acquisition(
                replace(
                    acquired,
                    created_at=datetime.now(UTC) - timedelta(hours=1),
                    expires_at=datetime.now(UTC) - timedelta(minutes=1),
                )
            )
            uow.commit()
        assert post(client, payload).status_code == 409
        assert count(app, "fm_commercial_purchases") == 0
        assert count(app, "fm_command_commercial_inbox") == 0


def test_contract_version_and_timestamps_do_not_allow_coercion():
    for value in (True, "1", 2, 0):
        with pytest.raises(CommercialFulfillmentError):
            CommandCommercialEvent.parse(json.dumps({**envelope(), "version": value}).encode())
    for value in ("not-a-time", "2026-10-08T12:00:00", None):
        with pytest.raises(CommercialFulfillmentError):
            CommandCommercialEvent.parse(json.dumps({**envelope(), "occurred_at": value}).encode())


@pytest.mark.parametrize("missing", ("_release", "_pricing"))
def test_postgres_missing_canonical_release_or_pricing_cannot_open_purchase(settings, missing):
    app, _, _, _ = setup(settings)
    with TestClient(app, base_url="https://testserver") as client:
        payload = begin(client)
        setattr(app.state.nfcore_command_commercial, missing, SimpleNamespace(current=None))
        assert post(client, payload).status_code == 409
        assert count(app, "fm_commercial_purchases") == 0
        assert count(app, "fm_command_commercial_inbox") == 0
