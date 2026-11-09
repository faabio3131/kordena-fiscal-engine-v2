from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from types import TracebackType

from fastapi.testclient import TestClient

from kordena_fiscal.control_plane.commercial_release import InMemoryCommercialReleaseCatalog
from kordena_fiscal.control_plane.models import (
    ControlPlaneAuditAction,
    ControlPlaneAuditEvent,
    FiscalOrganization,
    FiscalUnitRegistration,
)
from kordena_fiscal.domain import FiscalEnvironment
from kordena_fiscal.persistence.cakto import SqliteCaktoCommercialDatabase
from kordena_fiscal.persistence.commercial_period_schema import COMMERCIAL_PERIOD_VERSION
from kordena_fiscal.product.cakto import CaktoWebhookReceiver, CaktoWebhookVerifier
from kordena_fiscal.product.commercial_fulfillment import CommercialAcquisitionRecord
from kordena_fiscal.product.pricing import CommercialPricingRegistry
from kordena_fiscal.runtime import api as runtime_api
from kordena_fiscal.runtime import composition as composition_module
from kordena_fiscal.runtime.config import RuntimeSettings
from kordena_fiscal.security.human_identity import (
    HumanAccount,
    InMemoryHumanAccountRepository,
    InMemoryWebSessionRepository,
    PortalRole,
    ScryptPasswordHasher,
)
from kordena_fiscal.security.human_recovery import (
    InMemoryPasswordResetRepository,
    IssuedPasswordReset,
)
from kordena_fiscal.security.s2s import InMemoryWebhookKeyRing, WebhookSecurity
from kordena_fiscal.web.human_auth import CSRF_COOKIE, CSRF_HEADER

PASSWORD = "commercial-runtime-password-2026"
NOW = datetime(2026, 9, 16, 15, 30, tzinfo=UTC)


class _ResetDelivery:
    def deliver(
        self,
        *,
        email: str,
        reset: IssuedPasswordReset,
    ) -> None:
        del email, reset


class _MemoryCommercialAcquisitionStore:
    """Fake canonical commercial store: the shared `_RuntimeDatabase` fake used
    across this module answers every SQL `fetchone()` with a fixed `(1,)`
    tuple regardless of statement (see `_Cursor` below), so it cannot support
    a real idempotency lookup/insert round trip for acquisitions. This
    minimal in-memory store mirrors the one already proven in
    tests/application/test_cl11_first_party_acquisition.py, just for the
    narrow surface `CommercialAcquisitionService` actually calls."""

    def __init__(self) -> None:
        self.acquisitions: dict[str, CommercialAcquisitionRecord] = {}

    def get_acquisition_by_idempotency(
        self, idempotency_sha256: str
    ) -> CommercialAcquisitionRecord | None:
        return next(
            (
                item
                for item in self.acquisitions.values()
                if item.idempotency_sha256 == idempotency_sha256
            ),
            None,
        )

    def put_acquisition(
        self, acquisition: CommercialAcquisitionRecord
    ) -> CommercialAcquisitionRecord:
        self.acquisitions[acquisition.acquisition_id] = acquisition
        return acquisition


class _MemoryCommercialAcquisitionUow:
    def __init__(self, store: _MemoryCommercialAcquisitionStore) -> None:
        self.commercial = store

    def __enter__(self) -> _MemoryCommercialAcquisitionUow:
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        del exc_type, exc, traceback

    def commit(self) -> None:
        return None


class _MemoryCommercialAcquisitionDatabase:
    def __init__(self) -> None:
        self.store = _MemoryCommercialAcquisitionStore()

    def __call__(self) -> _MemoryCommercialAcquisitionUow:
        return _MemoryCommercialAcquisitionUow(self.store)


class _Cursor:
    def __init__(self, statement: str = "") -> None:
        self._statement = statement

    def fetchone(self) -> tuple[int]:
        return (1,)

    def fetchall(self) -> tuple[tuple[int, ...], ...]:
        if "FROM fm_cakto_schema_migrations" in self._statement:
            return ((1,), (2,), (3,))
        return ()


class _Connection:
    def execute(
        self,
        statement: str,
        _parameters: tuple[object, ...] = (),
    ) -> _Cursor:
        return _Cursor(statement)

    def commit(self) -> None:
        return None

    def rollback(self) -> None:
        return None


class _ControlPlane:
    def __init__(self) -> None:
        self.organization = FiscalOrganization(
            tenant_id="tenant-a",
            legal_name="Empresa Piloto Ltda",
        )
        self.unit = FiscalUnitRegistration(
            tenant_id="tenant-a",
            unit_id="unit-a",
            display_name="Matriz",
            enabled_environments=frozenset({FiscalEnvironment.HOMOLOGATION}),
        )
        self.events = (
            ControlPlaneAuditEvent(
                event_id="audit-unit-a",
                occurred_at=NOW,
                actor_id="admin-a",
                action=ControlPlaneAuditAction.UNIT_ONBOARDED,
                target_type="unit",
                target_id="unit-a",
                correlation_id="corr-unit-a",
                tenant_id="tenant-a",
                unit_id="unit-a",
            ),
        )

    def get_organization(self, tenant_id: str) -> FiscalOrganization | None:
        return self.organization if tenant_id == "tenant-a" else None

    def get_unit(self, tenant_id: str, unit_id: str) -> FiscalUnitRegistration | None:
        if tenant_id == "tenant-a" and unit_id == "unit-a":
            return self.unit
        return None

    def list_audit(self, tenant_id: str | None = None) -> tuple[ControlPlaneAuditEvent, ...]:
        if tenant_id is None or tenant_id == "tenant-a":
            return self.events
        return ()


class _UnitOfWork:
    def __init__(self, control_plane: _ControlPlane) -> None:
        self.control_plane = control_plane

    def __enter__(self) -> _UnitOfWork:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc, traceback


class _RuntimeDatabase:
    last: _RuntimeDatabase | None = None

    def __init__(self, _dsn: str) -> None:
        type(self).last = self
        hasher = ScryptPasswordHasher()
        self.accounts = InMemoryHumanAccountRepository(
            (
                HumanAccount(
                    account_id="owner-a",
                    email="owner@example.com",
                    password_hash=hasher.hash(PASSWORD),
                    tenant_id="tenant-a",
                    role=PortalRole.OWNER,
                ),
                HumanAccount(
                    account_id="platform-admin-a",
                    email="platform-admin@example.com",
                    password_hash=hasher.hash(PASSWORD),
                    tenant_id="fm-platform",
                    role=PortalRole.OWNER,
                    platform_admin=True,
                ),
            )
        )
        self.sessions = InMemoryWebSessionRepository()
        self.resets = InMemoryPasswordResetRepository()
        self.pricing = CommercialPricingRegistry()
        self.commercial_release = InMemoryCommercialReleaseCatalog()
        self.control_plane = _ControlPlane()
        self.closed = False

    def initialize(self) -> tuple[int]:
        raise AssertionError("staging API startup must never apply migrations")

    def require_current_schema(self) -> tuple[int]:
        return self.applied_migrations()

    @contextmanager
    def connection(self) -> Iterator[_Connection]:
        yield _Connection()

    def applied_migrations(self) -> tuple[int]:
        return (1,)

    def human_accounts(self) -> InMemoryHumanAccountRepository:
        return self.accounts

    def web_sessions(self) -> InMemoryWebSessionRepository:
        return self.sessions

    def password_resets(self) -> InMemoryPasswordResetRepository:
        return self.resets

    def pricing_catalog(self) -> CommercialPricingRegistry:
        return self.pricing

    def commercial_release_catalog(self) -> InMemoryCommercialReleaseCatalog:
        return self.commercial_release

    def __call__(self) -> _UnitOfWork:
        return _UnitOfWork(self.control_plane)

    def close(self) -> None:
        self.closed = True


def _settings() -> RuntimeSettings:
    return RuntimeSettings.from_mapping(
        {
            "NFCORE_ENVIRONMENT": "staging",
            "NFCORE_PERSISTENCE_BACKEND": "postgres",
            "DATABASE_URL": "postgresql://user:password@db:5432/nfcore",
            "NFCORE_SECRET_BACKEND": "external",
            "NFCORE_REQUIRE_HTTPS": "true",
        }
    )


def test_postgres_runtime_composes_human_identity_recovery_and_durable_portal(
    monkeypatch,
) -> None:
    monkeypatch.setattr(runtime_api, "PostgresFiscalDatabase", _RuntimeDatabase)

    with TestClient(
        runtime_api.create_runtime_app(_settings()),
        base_url="https://testserver",
    ) as client:
        profile = client.get("/runtime/profile").json()
        assert profile["human_identity_configured"] is True
        assert profile["portal_executor_configured"] is True
        assert profile["bridge_security_configured"] is True
        assert profile["bridge_executor_configured"] is True
        assert profile["bridge_workload_identity_configured"] is False
        assert profile["portal_fiscal_operation_executor_configured"] is True
        assert profile["fiscal_operation_handlers_configured"] == ["queryArchiveReference"]
        assert profile["fiscal_provider_transport_real_configured"] is False
        assert profile["fiscal_external_secret_client_configured"] is False
        assert profile["fiscal_signer_configured"] is False
        assert profile["fiscal_runtime_external_execution_ready"] is False
        assert profile["password_recovery_configured"] is True
        assert profile["commercial_release_admin_configured"] is True
        assert profile["commercial_release_status"] == "unavailable"
        assert profile["commercial_checkout_provider_configured"] is None
        assert profile["commercial_checkout_provider_active"] is None
        assert profile["commercial_checkout_status"] == "unconfigured"
        assert profile["commercial_checkout_processing_configured"] is False
        assert profile["canonical_commercial_persistence_configured"] is True
        assert profile["commercial_fulfillment_configured"] is True
        assert profile["commercial_provisioning_configured"] is True
        assert profile["commercial_activation_delivery_configured"] is False
        assert profile["commercial_delivery_path_ready"] is False
        assert profile["commercial_first_party_acquisition_configured"] is False
        assert profile["cakto_checkout_admin_configured"] is False
        assert profile["cakto_checkout_status"] == "unconfigured"
        assert profile["cakto_webhook_configured"] is False
        assert profile["fiscal_production_activated"] is False

        login = client.post(
            "/v1/auth/login",
            json={"email": "owner@example.com", "password": PASSWORD},
        )
        assert login.status_code == 200

        bootstrap = client.get("/v1/portal/bootstrap")
        assert bootstrap.status_code == 200
        projection = bootstrap.json()["projection"]
        assert projection["organization_onboarded"] is True
        assert projection["legal_name"] == "Empresa Piloto Ltda"
        assert projection["unit_count"] == 1
        assert projection["fiscal_operation_executor_configured"] is True
        assert projection["fiscal_operations_configured"] is True
        assert projection["configured_fiscal_operations"] == ["queryArchiveReference"]
        assert not set(projection["configured_fiscal_operations"]) & {
            "issueFiscalDocument",
            "cancelFiscalDocument",
            "inutilizeFiscalRange",
        }

        units = client.get("/v1/portal/surfaces/units")
        assert units.status_code == 200
        assert units.json()["rows"][0]["unit_id"] == "unit-a"

        unsupported = client.get("/v1/portal/surfaces/users")
        assert unsupported.status_code == 503
        assert unsupported.json()["detail"]["code"] == "PORTAL_RUNTIME_NOT_READY"

        bridge = client.post(
            "/v1/queries",
            headers={
                "Authorization": f"Bearer {'s' * 32}",
                "X-FM-Workload-Credential-Id": "missing-runtime-credential",
                "X-FM-Host-Namespace": "fm-nfcore",
                "X-FM-Tenant-Id": "tenant-a",
                "X-FM-Unit-Id": "unit-a",
                "X-FM-Environment": "homologation",
                "X-Correlation-Id": "corr-bridge-t02",
            },
            json={"reference": "DOC-1"},
        )
        assert bridge.status_code == 401
        assert bridge.json()["code"] == "WORKLOAD_AUTHENTICATION_FAILED"

        csrf = client.cookies.get(CSRF_COOKIE)
        assert csrf
        portal_operation = client.post(
            "/v1/portal/operations/queryFiscalDocument",
            headers={CSRF_HEADER: csrf},
            json={"unit_id": "unit-a", "document_id": "DOC-1"},
        )
        assert portal_operation.status_code == 503
        assert portal_operation.json()["detail"]["code"] == "FISCAL_RUNTIME_NOT_READY"

        # A read-only archive handler never activates fiscal write commands.
        # Keep the real authenticated session and CSRF/idempotency requirements.
        for operation, payload in (
            ("issueFiscalDocument", {"unit_id": "unit-a", "document": {"model": "55"}}),
            ("cancelFiscalDocument", {"unit_id": "unit-a", "document_id": "DOC-1"}),
            ("inutilizeFiscalRange", {
                "unit_id": "unit-a", "model": 55, "series": 1,
                "first_number": 1, "last_number": 1,
                "justification": "Falha tecnica na numeracao de documento fiscal",
            }),
        ):
            blocked = client.post(
                f"/v1/portal/operations/{operation}",
                headers={CSRF_HEADER: csrf, "Idempotency-Key": f"blocked-{operation}"},
                json=payload,
            )
            assert blocked.status_code == 503
            assert blocked.json()["detail"]["code"] == "FISCAL_RUNTIME_NOT_READY"

    database = _RuntimeDatabase.last
    assert database is not None
    assert database.closed is True


def test_postgres_runtime_projects_ready_delivery_path_only_with_activation_delivery(
    monkeypatch,
) -> None:
    monkeypatch.setattr(runtime_api, "PostgresFiscalDatabase", _RuntimeDatabase)

    with TestClient(
        runtime_api.create_runtime_app(
            _settings(),
            password_reset_delivery=_ResetDelivery(),
        ),
        base_url="https://testserver",
    ) as client:
        profile = client.get("/runtime/profile").json()
        assert profile["canonical_commercial_persistence_configured"] is True
        assert profile["commercial_fulfillment_configured"] is True
        assert profile["commercial_provisioning_configured"] is True
        assert profile["commercial_activation_delivery_configured"] is True
        assert profile["commercial_delivery_path_ready"] is True
        assert profile["commercial_first_party_acquisition_configured"] is False


def test_postgres_runtime_activates_cakto_checkout_only_by_explicit_provider_config(
    monkeypatch,
) -> None:
    monkeypatch.setattr(runtime_api, "PostgresFiscalDatabase", _RuntimeDatabase)
    settings = RuntimeSettings.from_mapping(
        {
            "NFCORE_ENVIRONMENT": "staging",
            "NFCORE_PERSISTENCE_BACKEND": "postgres",
            "DATABASE_URL": "postgresql://user:password@db:5432/nfcore",
            "NFCORE_SECRET_BACKEND": "external",
            "NFCORE_REQUIRE_HTTPS": "true",
            "NFCORE_COMMERCIAL_CHECKOUT_PROVIDER": "cakto",
        }
    )

    with TestClient(
        runtime_api.create_runtime_app(settings),
        base_url="https://testserver",
    ) as client:
        profile = client.get("/runtime/profile").json()
        assert profile["commercial_checkout_provider_configured"] == "cakto"
        assert profile["commercial_checkout_provider_active"] == "cakto"
        assert profile["commercial_checkout_status"] == "unconfigured"
        assert profile["commercial_checkout_processing_configured"] is False
        assert profile["cakto_checkout_admin_configured"] is True
        assert profile["cakto_webhook_configured"] is False


def test_postgres_runtime_treats_cakto_as_authoritative_processing_channel(
    monkeypatch, tmp_path
) -> None:
    """A pessoa-física seller has no Command counterpart: a real, explicitly
    injected Cakto webhook receiver must be treated as an equally authoritative
    processing/fulfillment/activation channel as Command, not a degraded one."""
    monkeypatch.setattr(runtime_api, "PostgresFiscalDatabase", _RuntimeDatabase)
    settings = RuntimeSettings.from_mapping(
        {
            "NFCORE_ENVIRONMENT": "staging",
            "NFCORE_PERSISTENCE_BACKEND": "postgres",
            "DATABASE_URL": "postgresql://user:password@db:5432/nfcore",
            "NFCORE_SECRET_BACKEND": "external",
            "NFCORE_REQUIRE_HTTPS": "true",
            "NFCORE_COMMERCIAL_CHECKOUT_PROVIDER": "cakto",
        }
    )
    cakto_database = SqliteCaktoCommercialDatabase(tmp_path / "cakto-authority.sqlite3")
    cakto_database.initialize()
    receiver = CaktoWebhookReceiver(
        verifier=CaktoWebhookVerifier(b"test-only-webhook-authority-key"),
        unit_of_work_factory=cakto_database,
    )

    with TestClient(
        runtime_api.create_runtime_app(settings, cakto_receiver=receiver),
        base_url="https://testserver",
    ) as client:
        profile = client.get("/runtime/profile").json()
        assert profile["commercial_checkout_provider_configured"] == "cakto"
        assert profile["commercial_checkout_provider_active"] == "cakto"
        assert profile["cakto_checkout_admin_configured"] is True
        assert profile["cakto_webhook_configured"] is True
        # This is the fix: previously only "command" ever set this flag, so
        # a fully configured direct Cakto channel still reported unconfigured
        # and never exposed a real checkout_url to anonymous buyers.
        assert profile["commercial_checkout_processing_configured"] is True


def test_postgres_runtime_exposes_real_cakto_checkout_url_to_anonymous_buyers(
    monkeypatch, tmp_path
) -> None:
    """Regression for the second Cakto-authority gap: even with
    commercial_checkout_processing_configured=True (the PR #391 fix), the
    public /v1/commercial/offer endpoint gates purchase_enabled through a
    SEPARATE operational_readiness probe (commercial_operational_readiness in
    runtime/api.py) that, before this fix, only ever returned True for the
    "command" provider -- unconditionally returning False for Cakto regardless
    of how fully configured pricing/release/checkout were.

    This test supplies commercial_acquisition_security so the signed
    first-party acquisition route is wired (a separate, intentional gate: the
    public offer must not advertise a purchase without it -- see the comment
    at the create_app(...) call site in runtime/api.py). That isolates the
    one behavior this fix changes: operational_readiness no longer hard-codes
    "command" as the only viable provider."""
    class _FullyMigratedRuntimeDatabase(_RuntimeDatabase):
        """commercial_operational_readiness additionally requires every
        commercial-period migration to be applied before probing any
        provider's channel; the base fixture reports only migration 1
        applied (sufficient for the other tests in this module, which do
        not exercise that function), so give this test a database that
        reports the real, full commercial schema version."""

        def applied_migrations(self) -> tuple[int, ...]:
            return tuple(range(1, COMMERCIAL_PERIOD_VERSION + 1))

    monkeypatch.setattr(runtime_api, "PostgresFiscalDatabase", _FullyMigratedRuntimeDatabase)
    cakto_bindings_database = SqliteCaktoCommercialDatabase(
        tmp_path / "cakto-public-offer-bindings.sqlite3"
    )
    cakto_bindings_database.initialize()
    # _RuntimeDatabase is a thin fiscal/control-plane fake (see _Connection /
    # _Cursor above); it never implements real Cakto plan-binding storage. The
    # production code path is identical regardless of which backing store
    # postgres_cakto_commercial_database wraps, so give the admin service a
    # real, persistent SQLite-backed store instead of faking raw SQL rows.
    monkeypatch.setattr(
        composition_module,
        "postgres_cakto_commercial_database",
        lambda _database: cakto_bindings_database,
    )
    settings = RuntimeSettings.from_mapping(
        {
            "NFCORE_ENVIRONMENT": "staging",
            "NFCORE_PERSISTENCE_BACKEND": "postgres",
            "DATABASE_URL": "postgresql://user:password@db:5432/nfcore",
            "NFCORE_SECRET_BACKEND": "external",
            "NFCORE_REQUIRE_HTTPS": "true",
            "NFCORE_COMMERCIAL_CHECKOUT_PROVIDER": "cakto",
        }
    )
    cakto_database = SqliteCaktoCommercialDatabase(tmp_path / "cakto-public-offer.sqlite3")
    cakto_database.initialize()
    receiver = CaktoWebhookReceiver(
        verifier=CaktoWebhookVerifier(b"test-only-webhook-authority-key"),
        unit_of_work_factory=cakto_database,
    )
    acquisition_security = WebhookSecurity(
        key_resolver=InMemoryWebhookKeyRing(
            active_key_id="synthetic-acquisition-key",
            keys={"synthetic-acquisition-key": b"synthetic-acquisition-secret-0001"},
        ),
        signing_key_id="synthetic-acquisition-key",
    )

    with TestClient(
        runtime_api.create_runtime_app(
            settings,
            cakto_receiver=receiver,
            password_reset_delivery=_ResetDelivery(),
            commercial_acquisition_security=acquisition_security,
        ),
        base_url="https://testserver",
    ) as client:
        login = client.post(
            "/v1/auth/login",
            json={"email": "platform-admin@example.com", "password": PASSWORD},
        )
        assert login.status_code == 200
        csrf = client.cookies.get(CSRF_COOKIE)
        assert csrf

        publish = client.post(
            "/v1/admin/pricing",
            headers={CSRF_HEADER: csrf},
            json={
                "configuration": {
                    "configuration_id": "nfcore-public-offer",
                    "version": 1,
                    "prices": [
                        {
                            "price_id": "nfcore-monthly",
                            "currency": "BRL",
                            "cadence": "monthly",
                            "base_amount": "123.45",
                            "external_price_reference": "cakto://product-nfcore/offer-monthly",
                        }
                    ],
                    "plans": [
                        {
                            "plan_id": "nfcore-pro",
                            "display_name": "NFCore Pro",
                            "edition_id": "pro",
                            "price_ids": ["nfcore-monthly"],
                        }
                    ],
                },
                "expected_version": None,
            },
        )
        assert publish.status_code == 200

        release = client.post(
            "/v1/admin/commercial-release",
            headers={CSRF_HEADER: csrf},
            json={
                "decision": {
                    "version": 1,
                    "status": "commercial_approved",
                    "public_message": "Oferta sintética aprovada.",
                    "human_decision_reference": "synthetic-human-release-evidence",
                },
                "expected_version": None,
            },
        )
        assert release.status_code == 200

        binding = client.post(
            "/v1/admin/checkout/cakto",
            headers={CSRF_HEADER: csrf},
            json={
                "external_product_id": "product-nfcore",
                "external_offer_id": "offer-monthly",
                "plan_id": "nfcore-pro",
                "entitlement_ids": ["portal", "fiscal-core"],
                "enabled": True,
            },
        )
        assert binding.status_code == 200

        offer = client.get("/v1/commercial/offer")
        assert offer.status_code == 200
        body = offer.json()
        assert body["checkout"]["status"] == "configured"
        # This is the fix under test: previously always False for Cakto.
        assert body["purchase_enabled"] is True
        assert body["checkout"]["items"][0]["checkout_url"] is not None


def test_postgres_runtime_public_acquisition_route_issues_real_checkout_url(
    monkeypatch, tmp_path
) -> None:
    """The signed /v1/commercial/acquisitions route requires an HMAC signature
    the static portal (no backend of its own) can never hold. This is the
    end-to-end regression for its browser-facing counterpart,
    /v1/public/acquisitions: an anonymous, same-origin POST with no signature
    and no cookie/Authorization still produces a real, provider-redirectable
    checkout_url -- by calling the same in-process CommercialAcquisitionService
    the signed route uses, never a second authority."""
    from kordena_fiscal.runtime.public_trial_abuse import PostgresPublicTrialAbuseGate

    class _FullyMigratedRuntimeDatabase(_RuntimeDatabase):
        def applied_migrations(self) -> tuple[int, ...]:
            return tuple(range(1, COMMERCIAL_PERIOD_VERSION + 1))

    monkeypatch.setattr(runtime_api, "PostgresFiscalDatabase", _FullyMigratedRuntimeDatabase)
    cakto_bindings_database = SqliteCaktoCommercialDatabase(
        tmp_path / "cakto-public-acquisition-bindings.sqlite3"
    )
    cakto_bindings_database.initialize()
    monkeypatch.setattr(
        composition_module,
        "postgres_cakto_commercial_database",
        lambda _database: cakto_bindings_database,
    )
    # The shared `_RuntimeDatabase` fake's `_Connection.execute()` answers every
    # statement with a fixed `(1,)` row (see `_Cursor` above) -- it was built
    # only for the simple probes (migrations/health) this module's other
    # tests need, not for a real idempotency-keyed insert/lookup round trip.
    # `CommercialAcquisitionService.begin()` genuinely reads and writes
    # through `postgres_canonical_commercial_database(runtime.database)`, so
    # give it a real (in-memory, but behaviorally real) store instead of
    # letting it decode that fixed row as acquisition data.
    monkeypatch.setattr(
        runtime_api,
        "postgres_canonical_commercial_database",
        lambda _database: _MemoryCommercialAcquisitionDatabase(),
    )
    settings = RuntimeSettings.from_mapping(
        {
            "NFCORE_ENVIRONMENT": "staging",
            "NFCORE_PERSISTENCE_BACKEND": "postgres",
            "DATABASE_URL": "postgresql://user:password@db:5432/nfcore",
            "NFCORE_SECRET_BACKEND": "external",
            "NFCORE_REQUIRE_HTTPS": "true",
            "NFCORE_COMMERCIAL_CHECKOUT_PROVIDER": "cakto",
            "NFCORE_ALLOWED_ORIGINS": "https://app.nfcore.com.br",
        }
    )
    cakto_database = SqliteCaktoCommercialDatabase(
        tmp_path / "cakto-public-acquisition.sqlite3"
    )
    cakto_database.initialize()
    receiver = CaktoWebhookReceiver(
        verifier=CaktoWebhookVerifier(b"test-only-webhook-authority-key"),
        unit_of_work_factory=cakto_database,
    )
    acquisition_security = WebhookSecurity(
        key_resolver=InMemoryWebhookKeyRing(
            active_key_id="synthetic-acquisition-key",
            keys={"synthetic-acquisition-key": b"synthetic-acquisition-secret-0001"},
        ),
        signing_key_id="synthetic-acquisition-key",
    )

    with TestClient(
        runtime_api.create_runtime_app(
            settings,
            cakto_receiver=receiver,
            password_reset_delivery=_ResetDelivery(),
            commercial_acquisition_security=acquisition_security,
            public_commercial_acquisition_allowed_origins=("https://app.nfcore.com.br",),
            public_commercial_acquisition_rate_limiter=PostgresPublicTrialAbuseGate(
                # Resolved lazily at request time, after create_runtime_app has
                # already constructed the real (fake, for this test) database
                # instance and assigned it to .last.
                lambda: _FullyMigratedRuntimeDatabase.last.connection(),
                scope_prefix="public-acquisition",
            ),
        ),
        base_url="https://testserver",
    ) as client:
        login = client.post(
            "/v1/auth/login",
            json={"email": "platform-admin@example.com", "password": PASSWORD},
        )
        assert login.status_code == 200
        csrf = client.cookies.get(CSRF_COOKIE)
        assert csrf

        publish = client.post(
            "/v1/admin/pricing",
            headers={CSRF_HEADER: csrf},
            json={
                "configuration": {
                    "configuration_id": "nfcore-public-offer",
                    "version": 1,
                    "prices": [
                        {
                            "price_id": "nfcore-monthly",
                            "currency": "BRL",
                            "cadence": "monthly",
                            "base_amount": "123.45",
                            "external_price_reference": "cakto://product-nfcore/offer-monthly",
                        }
                    ],
                    "plans": [
                        {
                            "plan_id": "nfcore-pro",
                            "display_name": "NFCore Pro",
                            "edition_id": "pro",
                            "price_ids": ["nfcore-monthly"],
                        }
                    ],
                },
                "expected_version": None,
            },
        )
        assert publish.status_code == 200

        release = client.post(
            "/v1/admin/commercial-release",
            headers={CSRF_HEADER: csrf},
            json={
                "decision": {
                    "version": 1,
                    "status": "commercial_approved",
                    "public_message": "Oferta sintética aprovada.",
                    "human_decision_reference": "synthetic-human-release-evidence",
                },
                "expected_version": None,
            },
        )
        assert release.status_code == 200

        binding = client.post(
            "/v1/admin/checkout/cakto",
            headers={CSRF_HEADER: csrf},
            json={
                "external_product_id": "product-nfcore",
                "external_offer_id": "offer-monthly",
                "plan_id": "nfcore-pro",
                "entitlement_ids": ["portal", "fiscal-core"],
                "enabled": True,
            },
        )
        assert binding.status_code == 200

        # A fresh, cookie-less client stands in for the anonymous browser
        # visitor: no session, no Authorization, only the same-origin header.
        with TestClient(client.app, base_url="https://testserver") as anonymous:
            acquisition = anonymous.post(
                "/v1/public/acquisitions",
                json={
                    "plan_id": "nfcore-pro",
                    "price_id": "nfcore-monthly",
                    "buyer_email": "buyer@example.com",
                    "legal_name": "Comprador Sintético LTDA",
                },
                headers={
                    "Origin": "https://app.nfcore.com.br",
                    "Idempotency-Key": "public-acquisition-e2e-0001",
                },
            )
        assert acquisition.status_code == 201
        acquisition_body = acquisition.json()
        assert acquisition_body["provider"] == "cakto"
        assert acquisition_body["checkout_url"].startswith("https://pay.cakto.com.br/")
        assert acquisition_body["acquisition_reference"].startswith("acq-")
        assert acquisition.headers["access-control-allow-origin"] == "https://app.nfcore.com.br"

        profile = client.get("/runtime/profile")
        assert profile.status_code == 200
        assert profile.json()["public_commercial_acquisition_configured"] is True


def test_postgres_runtime_reports_composition_failure_separately(monkeypatch) -> None:
    monkeypatch.setattr(runtime_api, "PostgresFiscalDatabase", _RuntimeDatabase)

    def fail_composition(*_args, **_kwargs):
        raise RuntimeError("synthetic composition failure")

    monkeypatch.setattr(runtime_api, "build_postgres_runtime_composition", fail_composition)
    client = TestClient(runtime_api.create_runtime_app(_settings()), base_url="https://testserver")

    response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json() == {"status": "not_ready", "reason": "composition_unavailable"}


def test_fiscal_provider_handlers_bind_to_one_canonical_runtime_application(monkeypatch) -> None:
    """Opt-in client uses the runtime-owned durable application, never a second one."""
    from kordena_fiscal.application.service import FiscalApplicationService
    from kordena_fiscal.operations import FakeFiscalOperationsGateway, FiscalOperationsClient
    from kordena_fiscal.runtime.provider_operation_wiring import build_provider_operation_handlers

    monkeypatch.setattr(runtime_api, "PostgresFiscalDatabase", _RuntimeDatabase)
    observed: list[FiscalApplicationService] = []

    def approved_handler_factory(
        application: FiscalApplicationService,
    ):
        observed.append(application)
        return build_provider_operation_handlers(
            FiscalOperationsClient(FakeFiscalOperationsGateway())
        )

    with TestClient(
        runtime_api.create_runtime_app(
            _settings(), fiscal_operation_handler_factory=approved_handler_factory
        ),
        base_url="https://testserver",
    ) as client:
        assert client.get("/health/ready").status_code == 200
        composition = client.app.state.nfcore_runtime_composition
        assert len(observed) == 1
        assert observed[0] is composition.fiscal_application
        assert set(composition.fiscal_operation_path.configured_operations) == {
            "queryArchiveReference",
            "queryFiscalDocument",
            "cancelFiscalDocument",
            "inutilizeFiscalRange",
        }
        profile = client.get("/runtime/profile").json()
        assert set(profile["fiscal_operation_handlers_configured"]) == set(
            composition.fiscal_operation_path.configured_operations
        )
        # Synthetic client composition is not an official provider or a valid certificate.
        assert profile["fiscal_provider_transport_real_configured"] is False
        assert profile["fiscal_runtime_external_execution_ready"] is False
        assert client.post("/v1/portal/operations/queryFiscalDocument", json={}).status_code == 401


def test_duplicate_or_invalid_fiscal_factory_fails_closed(monkeypatch) -> None:
    monkeypatch.setattr(runtime_api, "PostgresFiscalDatabase", _RuntimeDatabase)
    for kwargs in (
        {
            "fiscal_operation_handlers": {},
            "fiscal_operation_handler_factory": lambda _app: {},
        },
        {"fiscal_operation_handler_factory": lambda _app: ["invalid"]},
        {"fiscal_operation_handler_factory": lambda _app: (_ for _ in ()).throw(
            RuntimeError("configured dependency unavailable")
        )},
    ):
        with TestClient(
            runtime_api.create_runtime_app(_settings(), **kwargs),
            base_url="https://testserver",
        ) as client:
            ready = client.get("/health/ready")
            assert ready.status_code == 503
            assert ready.json()["reason"] == "composition_unavailable"
            assert client.get("/runtime/profile").json()[
                "fiscal_operation_handlers_configured"
            ] == []
