"""Runtime wiring and durable first-party acquisition; no real provider transaction."""

from __future__ import annotations

import importlib.util
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import psycopg
import pytest
from fastapi.testclient import TestClient

from kordena_fiscal.control_plane.models import AdminPrincipal, ControlPlanePermission
from kordena_fiscal.product.command_commercial import CommandBinding
from kordena_fiscal.product.commercial_release import (
    CommercialReleaseDecision,
    CommercialReleaseStatus,
)
from kordena_fiscal.runtime import api as runtime_api
from kordena_fiscal.runtime.config import RuntimeSettings
from kordena_fiscal.security.s2s import (
    FixedWindowRateLimiter,
    InMemoryWebhookKeyRing,
    WebhookSecurity,
)
from kordena_fiscal.security.secrets import InMemorySecretBackend, SecretResolver


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).parents[1] / relative)
    assert spec and spec.loader
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


acquisition = load("p03_acquisition_examples", "application/test_cl11_first_party_acquisition.py")
composition = load("p03_composition_examples", "runtime/test_cl01_production_composition.py")
ENDPOINT = "/v1/commercial/acquisitions"
KEY = "synthetic-runtime-acquisition-0001"
ACTOR = AdminPrincipal(
    actor_id="synthetic-platform",
    permissions=frozenset({ControlPlanePermission.COMMERCIAL_CONFIG_WRITE}),
    global_scope=True,
)


class Checkout(acquisition.SyntheticCheckout):
    provider_id = "command"


class SyntheticBackend(InMemorySecretBackend):
    @property
    def production_safe(self):
        return True  # CI harness only; never proof of an external provider.


def receiver_binding():
    return CommandBinding(
        key_id="synthetic-acquisition-command",
        binding_id="synthetic-acquisition-channel",
        product_id="nfcore",
        environment="staging",
        secret_reference="sec_synthetic_acquisition_key_0001",
        secret_version=1,
        not_after=datetime.now(UTC) + timedelta(days=1),
    )


def security():
    return WebhookSecurity(
        key_resolver=InMemoryWebhookKeyRing(
            active_key_id=acquisition.KEY_ID,
            keys={acquisition.KEY_ID: acquisition.SECRET},
        ),
        signing_key_id=acquisition.KEY_ID,
    )


def options():
    checkout = Checkout()
    binding = receiver_binding()
    secrets = SyntheticBackend()
    secrets.put(
        reference_id=binding.secret_reference,
        scope=binding.scope,
        value=acquisition.SECRET,
    )
    return {
        "commercial_checkout_projector": checkout,
        "commercial_checkout_starter": checkout,
        "commercial_checkout_processing_configured": True,
        "commercial_acquisition_security": security(),
        "password_reset_delivery": composition._ResetDelivery(),
        "command_secret_resolver": SecretResolver(secrets, environment="staging"),
    }


def publish(app, *, pricing=True, release=True, receiver=False):
    services = app.state.nfcore_runtime_composition
    assert services is not None
    if pricing:
        services.pricing_administration.publish(
            actor=ACTOR,
            configuration=acquisition.pricing(),
            expected_version=None,
        )
    if release:
        services.commercial_release_administration.publish(
            actor=ACTOR,
            decision=acquisition.approved_release(),
            expected_version=None,
        )
    if receiver and app.state.nfcore_command_commercial is not None:
        app.state.nfcore_command_commercial.store.configure(
            actor=AdminPrincipal(
                actor_id="synthetic-platform-command",
                global_scope=True,
                permissions=frozenset(
                    {
                        ControlPlanePermission.COMMERCIAL_CONFIG_WRITE,
                        ControlPlanePermission.SECRET_REFERENCE_WRITE,
                    }
                ),
            ),
            binding=receiver_binding(),
            expected_revision=None,
            now=datetime.now(UTC),
        )


def post(client, signing, *, body=None, key=KEY):
    encoded = acquisition.acquisition_body() if body is None else json.dumps(body).encode()
    return client.post(
        ENDPOINT,
        content=encoded,
        headers={
            "Content-Type": "application/json",
            "Idempotency-Key": key,
            "X-NFCore-Signature": signing.sign(encoded, now=datetime.now(UTC)).header_value,
        },
    )


@pytest.mark.parametrize("missing", ("security", "starter", "mismatched_starter"))
def test_offer_cannot_advertise_purchase_without_signed_matching_acquisition(monkeypatch, missing):
    # Wiring regression only; this fixture is not evidence of durable persistence.
    monkeypatch.setattr(runtime_api, "PostgresFiscalDatabase", composition._RuntimeDatabase)
    configured = options()
    if missing == "security":
        configured["commercial_acquisition_security"] = None
    elif missing == "starter":
        configured["commercial_checkout_starter"] = None
    else:

        class OtherStarter(acquisition.SyntheticCheckout):
            provider_id = "other-synthetic"

        configured["commercial_checkout_starter"] = OtherStarter()
    app = runtime_api.create_runtime_app(composition._settings(), **configured)
    publish(app)
    with TestClient(app, base_url="https://testserver") as client:
        assert (
            client.get("/runtime/profile").json()["commercial_first_party_acquisition_configured"]
            is False
        )
        offer = client.get("/v1/commercial/offer").json()
        assert offer["purchase_enabled"] is False
        assert "https://payments.example" not in json.dumps(offer)
        assert post(client, security()).status_code == 404


@pytest.fixture
def settings():
    dsn = os.environ.get("NFCORE_TEST_POSTGRES_DSN")
    if not dsn:
        pytest.skip("real PostgreSQL DSN required; remote CI supplies it")
    with psycopg.connect(dsn, autocommit=True) as connection:
        connection.execute("DROP SCHEMA public CASCADE")
        connection.execute("CREATE SCHEMA public")
    return RuntimeSettings.from_mapping(
        {
            "NFCORE_ENVIRONMENT": "staging",
            "NFCORE_PERSISTENCE_BACKEND": "postgres",
            "DATABASE_URL": dsn,
            "NFCORE_SECRET_BACKEND": "external",
            "NFCORE_REQUIRE_HTTPS": "true",
        }
    )


def assert_counts(app, acquisitions):
    database = app.state.nfcore_runtime.database
    with database.connection() as connection:
        assert (
            connection.execute("SELECT COUNT(*) FROM fm_commercial_acquisitions").fetchone()[0]
            == acquisitions
        )
        for table in (
            "fm_commercial_purchases",
            "fm_commercial_subscriptions",
            "fm_human_accounts",
            "fm_control_plane_organizations",
            "fm_password_resets",
        ):
            assert connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0


def test_postgres_signed_runtime_acquisition_replays_after_restart_without_provisioning(settings):
    configured = options()
    app = runtime_api.create_runtime_app(settings, **configured)
    publish(app, receiver=True)
    with TestClient(app, base_url="https://testserver") as client:
        assert client.get("/health/ready").status_code == 200
        assert client.get("/runtime/profile").json()[
            "commercial_first_party_acquisition_configured"
        ]
        assert client.get("/v1/commercial/offer").json()["purchase_enabled"]
        first = post(client, configured["commercial_acquisition_security"])
        assert first.status_code == 201
        assert first.headers["cache-control"] == "no-store, max-age=0"
        result = first.json()
        assert "buyer_email" not in result and "legal_name" not in result
        assert_counts(app, 1)
    restarted = runtime_api.create_runtime_app(settings, **options())
    with TestClient(restarted, base_url="https://testserver") as client:
        replay = post(client, security())
        assert replay.status_code == 200 and replay.json()["replay"]
        assert replay.json()["acquisition_reference"] == result["acquisition_reference"]
        assert replay.json()["expires_at"] == result["expires_at"]
        body = json.loads(acquisition.acquisition_body())
        body["buyer_email"] = "different@example.com"
        assert post(client, security(), body=body).status_code == 409
        assert_counts(restarted, 1)


@pytest.mark.parametrize("missing", ("pricing", "release", "processing", "activation"))
def test_postgres_runtime_missing_dependency_blocks_offer_and_acquisition(settings, missing):
    configured = options()
    if missing == "processing":
        configured["command_secret_resolver"] = None
    if missing == "activation":
        configured["password_reset_delivery"] = None
    app = runtime_api.create_runtime_app(settings, **configured)
    publish(app, pricing=missing != "pricing", release=missing != "release", receiver=True)
    with TestClient(app, base_url="https://testserver") as client:
        assert client.get("/v1/commercial/offer").json()["purchase_enabled"] is False
        assert post(client, security()).status_code == 503
        assert_counts(app, 0)


@pytest.mark.parametrize(
    "field", ("payment_success", "tenant_id", "entitlements", "subscription_id")
)
def test_postgres_runtime_rejects_browser_authority_before_persistence(settings, field):
    app = runtime_api.create_runtime_app(settings, **options())
    publish(app, receiver=True)
    with TestClient(app, base_url="https://testserver") as client:
        assert client.post(ENDPOINT, content=acquisition.acquisition_body()).status_code == 401
        body = json.loads(acquisition.acquisition_body())
        body[field] = "synthetic-untrusted"
        assert post(client, security(), body=body).status_code == 400
        assert_counts(app, 0)


def test_postgres_runtime_rate_limit_and_release_revocation_prevent_new_acquisition(settings):
    configured = options()
    configured["commercial_acquisition_rate_limiter"] = FixedWindowRateLimiter(
        max_requests=1,
        window_seconds=60,
    )
    app = runtime_api.create_runtime_app(settings, **configured)
    publish(app, receiver=True)
    with TestClient(app, base_url="https://testserver") as client:
        assert post(client, security()).status_code == 201
        assert post(client, security(), key=KEY + "-other").status_code == 429
        assert_counts(app, 1)
    restarted = runtime_api.create_runtime_app(settings, **options())
    restarted.state.nfcore_runtime_composition.commercial_release_administration.publish(
        actor=ACTOR,
        expected_version=1,
        decision=CommercialReleaseDecision(version=2, status=CommercialReleaseStatus.WAITLIST),
    )
    with TestClient(restarted, base_url="https://testserver") as client:
        assert client.get("/v1/commercial/offer").json()["purchase_enabled"] is False
        assert post(client, security(), key=KEY + "-new").status_code == 503
        assert_counts(restarted, 1)


def test_postgres_runtime_checkout_response_loss_reuses_committed_reference(settings):
    class LosingCheckout(Checkout):
        references = []

        def start_checkout(self, *, item, acquisition_reference):
            self.references.append(acquisition_reference)
            if len(self.references) == 1:
                raise RuntimeError("synthetic provider response loss")
            return super().start_checkout(item=item, acquisition_reference=acquisition_reference)

    checkout = LosingCheckout()
    configured = options()
    configured.update(commercial_checkout_projector=checkout, commercial_checkout_starter=checkout)
    app = runtime_api.create_runtime_app(settings, **configured)
    publish(app, receiver=True)
    with TestClient(app, base_url="https://testserver", raise_server_exceptions=False) as client:
        assert post(client, security()).status_code == 500
        assert_counts(app, 1)
        replay = post(client, security())
        assert replay.status_code == 200 and replay.json()["replay"]
        assert checkout.references == [replay.json()["acquisition_reference"]] * 2
        assert_counts(app, 1)


def test_postgres_runtime_signature_tampering_and_expiration(settings):
    app = runtime_api.create_runtime_app(settings, **options())
    publish(app, receiver=True)
    with TestClient(app, base_url="https://testserver") as client:
        body = acquisition.acquisition_body()
        signed = security().sign(body, now=datetime.now(UTC))
        response = client.post(
            ENDPOINT,
            content=body.replace(b"ACME", b"EVIL"),
            headers={"Idempotency-Key": KEY, "X-NFCore-Signature": signed.header_value},
        )
        assert response.status_code == 401
        assert_counts(app, 0)
        assert post(client, security()).status_code == 201
        database = app.state.nfcore_runtime.database
        with database.connection() as connection:
            now = datetime.now(UTC)
            connection.execute(
                "UPDATE fm_commercial_acquisitions SET created_at = ?, expires_at = ?",
                ((now - timedelta(hours=2)).isoformat(), (now - timedelta(hours=1)).isoformat()),
            )
            connection.commit()
        assert post(client, security()).status_code == 409
        assert_counts(app, 1)


def test_postgres_runtime_failed_persistence_never_starts_checkout(settings, monkeypatch):
    from kordena_fiscal.persistence.commercial_fulfillment import CommercialSqlStore

    class RecordingCheckout(Checkout):
        references = []

        def start_checkout(self, *, item, acquisition_reference):
            self.references.append(acquisition_reference)
            return super().start_checkout(item=item, acquisition_reference=acquisition_reference)

    checkout = RecordingCheckout()
    configured = options()
    configured.update(commercial_checkout_projector=checkout, commercial_checkout_starter=checkout)
    app = runtime_api.create_runtime_app(settings, **configured)
    publish(app, receiver=True)
    original = CommercialSqlStore.put_acquisition

    def fail_write(*args):
        raise RuntimeError("synthetic persistence unavailable")

    with TestClient(app, base_url="https://testserver", raise_server_exceptions=False) as client:
        monkeypatch.setattr(CommercialSqlStore, "put_acquisition", fail_write)
        assert post(client, security()).status_code == 500
        assert checkout.references == []
        assert_counts(app, 0)
        monkeypatch.setattr(CommercialSqlStore, "put_acquisition", original)
        assert post(client, security()).status_code == 201
        assert len(checkout.references) == 1
        assert_counts(app, 1)
