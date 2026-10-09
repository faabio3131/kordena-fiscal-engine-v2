"""Live purchase gates; harness is synthetic, PostgreSQL tests use CI's isolated DB."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from test_p03_t01_acquisition import acquisition, composition, publish, security
from test_p03_t01_acquisition import post as start_acquisition
from test_p03_t03_command import (
    ACTOR,
    REF,
    SECRET,
    Checkout,
    Delivery,
    SyntheticExternalBackend,
    backend,
    binding,
    count,
    setup,
)
from test_p03_t03_command import settings as postgres_settings

from kordena_fiscal.persistence.commercial_fulfillment import CommercialSqlStore
from kordena_fiscal.product.commercial_fulfillment import CommercialFulfillmentError
from kordena_fiscal.product.commercial_release import (
    CommercialReleaseDecision,
    CommercialReleaseStatus,
)
from kordena_fiscal.runtime import api as runtime_api
from kordena_fiscal.security.s2s import FixedWindowRateLimiter
from kordena_fiscal.security.secrets import SecretReference, SecretResolver, SecretScope

settings = postgres_settings
OFFER = "/v1/commercial/offer"


class ReadyHarnessDatabase(composition._RuntimeDatabase):
    def applied_migrations(self):
        return tuple(range(1, 16))


def harness(monkeypatch, **overrides):
    monkeypatch.setattr(runtime_api, "PostgresFiscalDatabase", ReadyHarnessDatabase)
    secrets = backend()
    resolver = SecretResolver(secrets, environment="staging")
    checkout = Checkout()
    options = dict(
        command_secret_resolver=resolver,
        commercial_checkout_projector=checkout,
        commercial_checkout_starter=checkout,
        commercial_acquisition_security=security(),
        password_reset_delivery=Delivery(),
    )
    options.update(overrides)
    app = runtime_api.create_runtime_app(composition._settings(), **options)
    publish(app)
    chosen = binding()
    state = {"binding": chosen}
    receiver = app.state.nfcore_command_commercial
    if receiver is not None:
        monkeypatch.setattr(
            receiver.store,
            "readiness_bindings",
            lambda **_kwargs: () if state["binding"] is None else (state["binding"],),
        )
        monkeypatch.setattr(
            receiver.store,
            "binding",
            lambda _key: None if state["binding"] is None else (state["binding"], 1),
        )
    return app, secrets, state, resolver


def assert_blocked(client):
    response = client.get(OFFER)
    assert response.status_code == 200
    assert response.json()["purchase_enabled"] is False
    assert "payments.example" not in response.text
    assert REF not in response.text and SECRET.decode() not in response.text
    assert "private" not in response.text
    assert response.headers["cache-control"] == "no-store, max-age=0"
    assert start_acquisition(client, security()).status_code in {404, 503}


def test_live_valid_readiness_is_read_only_and_material_is_zeroized(monkeypatch):
    app, _, _, resolver = harness(monkeypatch)
    original = resolver.resolve
    resolved = []

    def recording(*args, **kwargs):
        material = original(*args, **kwargs)
        resolved.append(material)
        return material

    monkeypatch.setattr(resolver, "resolve", recording)
    with TestClient(app, base_url="https://testserver") as client:
        assert client.get(OFFER).json()["purchase_enabled"] is True
        assert client.get(OFFER).json()["purchase_enabled"] is True
    assert len(resolved) == 2  # No positive cache; one assessment per GET.
    for material in resolved:
        with pytest.raises(RuntimeError, match="no longer available"):
            material.reveal()


@pytest.mark.parametrize("variant", ("absent", "disabled", "expired", "product", "environment"))
def test_binding_denial_blocks_offer_and_signed_acquisition(monkeypatch, variant):
    app, _, state, _ = harness(monkeypatch)
    chosen = state["binding"]
    if variant == "absent":
        state["binding"] = None
    elif variant == "disabled":
        state["binding"] = replace(chosen, enabled=False)
    elif variant == "expired":
        state["binding"] = replace(chosen, not_after=datetime.now(UTC) - timedelta(seconds=1))
    elif variant == "product":
        state["binding"] = replace(chosen, product_id="other-saas")
    else:
        state["binding"] = replace(chosen, environment="production")
    with TestClient(app, base_url="https://testserver") as client:
        assert_blocked(client)


@pytest.mark.parametrize(
    "variant",
    ("missing", "revoked", "expired", "scope", "version", "unavailable", "short"),
)
def test_secret_denial_never_leaks_or_starts_checkout(monkeypatch, variant):
    app, secrets, state, resolver = harness(monkeypatch)
    if variant == "revoked":
        secrets.revoke(SecretReference(REF, 1))
    elif variant in {"missing", "version"}:
        state["binding"] = replace(
            state["binding"],
            **(
                {"secret_version": 2}
                if variant == "version"
                else {
                    "secret_reference": "sec_synthetic_missing_material_0001",
                }
            ),
        )
    elif variant == "unavailable":

        def fail(*_args, **_kwargs):
            raise RuntimeError("synthetic-private-backend-error")

        monkeypatch.setattr(resolver, "resolve", fail)
    else:
        replacement = SyntheticExternalBackend()
        replacement.put(
            reference_id=REF,
            scope=state["binding"].scope
            if variant != "scope"
            else SecretScope(
                "other",
                None,
                "commercial.command.webhook",
            ),
            value=b"short" if variant == "short" else SECRET,
            not_after=datetime.now(UTC) - timedelta(seconds=1) if variant == "expired" else None,
        )
        resolver._backend = replacement
    with TestClient(app, base_url="https://testserver") as client:
        assert_blocked(client)


@pytest.mark.parametrize(
    "missing", ("receiver", "fulfillment", "provisioning", "activation", "delivery")
)
def test_every_composed_delivery_dependency_is_required(monkeypatch, missing):
    overrides = {}
    if missing == "receiver":
        overrides["command_secret_resolver"] = None
    if missing == "delivery":
        overrides["password_reset_delivery"] = None
    app, _, _, _ = harness(monkeypatch, **overrides)
    if missing in {"fulfillment", "provisioning", "activation"}:
        object.__setattr__(
            app.state.nfcore_runtime_composition,
            "commercial_" + missing,
            None,
        )
    with TestClient(app, base_url="https://testserver") as client:
        assert_blocked(client)


@pytest.mark.parametrize("missing", ("database", "migrations", "reader", "binding-store"))
def test_live_persistence_losses_fail_closed(monkeypatch, missing):
    app, _, _, _ = harness(monkeypatch)
    runtime = app.state.nfcore_runtime
    if missing == "database":
        monkeypatch.setattr(runtime, "ready", lambda: (False, "database_unavailable"))
    elif missing == "migrations":
        monkeypatch.setattr(runtime.database, "applied_migrations", lambda: (1,))
    else:

        def fail(*_args, **_kwargs):
            raise RuntimeError("synthetic-private-database-error")

        if missing == "reader":
            monkeypatch.setattr(
                type(runtime.composition.pricing_administration._catalog),
                "current",
                property(fail),
            )
        else:
            monkeypatch.setattr(
                app.state.nfcore_command_commercial.store, "readiness_bindings", fail
            )
    with TestClient(app, base_url="https://testserver") as client:
        assert_blocked(client)


def test_global_budget_limits_public_secret_resolution_without_client_keys(monkeypatch):
    app, _, _, resolver = harness(
        monkeypatch,
        commercial_readiness_rate_limiter=FixedWindowRateLimiter(
            max_requests=1, window_seconds=3600
        ),
    )
    original = resolver.resolve
    calls = []

    def recording(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(resolver, "resolve", recording)
    with TestClient(app, base_url="https://testserver") as client:
        assert client.get(OFFER).json()["purchase_enabled"] is True
        for index in range(3):
            response = client.get(OFFER, params={"key": f"untrusted-{index}", "reference": REF})
            assert response.json()["purchase_enabled"] is False
        assert client.get(OFFER, headers={"X-Forwarded-For": "192.0.2.1"}).status_code == 400
        assert start_acquisition(client, security()).status_code == 503
    assert len(calls) == 1


def test_processing_flag_cannot_substitute_for_a_supported_composed_receiver(monkeypatch):
    class UnsupportedCheckout(Checkout):
        provider_id = "unsupported-synthetic"

    checkout = UnsupportedCheckout()
    app, _, _, _ = harness(
        monkeypatch,
        commercial_checkout_projector=checkout,
        commercial_checkout_starter=checkout,
        commercial_checkout_processing_configured=True,
    )
    with TestClient(app, base_url="https://testserver") as client:
        assert_blocked(client)


@pytest.mark.parametrize("changed", ("release", "pricing", "plan", "price", "projection"))
def test_offer_and_acquisition_follow_canonical_catalog_not_stale_checkout(monkeypatch, changed):
    app, _, _, _ = harness(monkeypatch)
    services = app.state.nfcore_runtime_composition
    with TestClient(app, base_url="https://testserver") as client:
        assert client.get(OFFER).json()["purchase_enabled"] is True
        if changed == "release":
            services.commercial_release_administration.publish(
                actor=ACTOR,
                expected_version=1,
                decision=CommercialReleaseDecision(
                    version=2,
                    status=CommercialReleaseStatus.WAITLIST,
                ),
            )
        elif changed == "pricing":
            monkeypatch.setattr(
                type(services.pricing_administration._catalog),
                "current",
                property(lambda _self: None),
            )
        elif changed == "projection":
            checkout = app.state.nfcore_commercial_acquisition._checkout
            original = checkout.project
            monkeypatch.setattr(
                checkout,
                "project",
                lambda pricing: replace(
                    original(pricing),
                    provider="other",
                    items=tuple(
                        replace(item, provider="other") for item in original(pricing).items
                    ),
                ),
            )
        else:
            pricing = acquisition.pricing()
            changed_pricing = replace(
                pricing,
                version=2,
                plans=tuple(replace(plan, enabled=False) for plan in pricing.plans)
                if changed == "plan"
                else pricing.plans,
                prices=tuple(replace(price, enabled=False) for price in pricing.prices)
                if changed == "price"
                else pricing.prices,
            )
            services.pricing_administration.publish(
                actor=ACTOR,
                configuration=changed_pricing,
                expected_version=1,
            )
        assert_blocked(client)


def test_postgres_rotation_and_revocation_revalidate_without_restart(settings):
    app, _, secrets, _ = setup(settings)
    receiver = app.state.nfcore_command_commercial
    with TestClient(app, base_url="https://testserver") as client:
        assert client.get(OFFER).json()["purchase_enabled"] is True
        secrets.revoke(SecretReference(REF, 1))
        assert_blocked(client)
        assert count(app, "fm_commercial_acquisitions") == 0
        secrets.put(reference_id=REF, scope=binding().scope, value=SECRET)
        receiver.store.configure(
            actor=ACTOR,
            binding=replace(binding(), secret_version=2),
            expected_revision=1,
            now=datetime.now(UTC),
        )
        assert client.get(OFFER).json()["purchase_enabled"] is True
        assert start_acquisition(client, security()).status_code == 201
        assert count(app, "fm_commercial_acquisitions") == 1
        assert count(app, "fm_commercial_purchases") == 0


def test_postgres_budget_and_scope_are_bounded_in_canonical_store(settings):
    app, _, _, _ = setup(settings)
    store = app.state.nfcore_command_commercial.store
    for index in range(8):
        store.configure(
            actor=ACTOR,
            binding=replace(binding(), key_id=f"extra-{index}"),
            expected_revision=None,
            now=datetime.now(UTC),
        )
    with TestClient(app, base_url="https://testserver") as client:
        assert_blocked(client)
        assert count(app, "fm_commercial_acquisitions") == 0
        with pytest.raises(CommercialFulfillmentError, match="budget exceeded"):
            store.readiness_bindings(product_id="nfcore", environment="staging")
        assert store.readiness_bindings(product_id="other", environment="staging") == ()
        assert store.readiness_bindings(product_id="nfcore", environment="production") == ()


def test_postgres_revocation_after_reference_commit_never_starts_checkout(settings, monkeypatch):
    app, options, secrets, _ = setup(settings)
    original = CommercialSqlStore.put_acquisition
    checkout_calls = []

    def revoke_after_write(self, record):
        original(self, record)
        secrets.revoke(SecretReference(REF, 1))

    monkeypatch.setattr(CommercialSqlStore, "put_acquisition", revoke_after_write)
    monkeypatch.setattr(
        options["commercial_checkout_starter"],
        "start_checkout",
        lambda **kwargs: checkout_calls.append(kwargs),
    )
    with TestClient(app, base_url="https://testserver") as client:
        assert client.get(OFFER).json()["purchase_enabled"] is True
        assert start_acquisition(client, security()).status_code == 503
        assert count(app, "fm_commercial_acquisitions") == 1
        assert count(app, "fm_commercial_purchases") == 0
        assert checkout_calls == []
        assert "command-v1" not in json.dumps(client.get(OFFER).json())
