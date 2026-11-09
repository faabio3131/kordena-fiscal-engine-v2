"""A-02: AES-GCM scoped OAuth state, company verification and refresh CAS."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from kordena_fiscal.application.service import FiscalApplicationService
from kordena_fiscal.connectors.bling_oauth import (
    BlingOAuthClient,
    BlingOAuthError,
    BlingTokenSet,
)
from kordena_fiscal.domain import (
    FiscalAccountBinding,
    FiscalAccountId,
    FiscalEnvironment,
    FiscalUnitId,
    HostNamespace,
    HostScope,
)
from kordena_fiscal.integrations.bling_contracts import BlingInstallationState
from kordena_fiscal.persistence.bling_installations import BlingInstallationRepository
from kordena_fiscal.persistence.ports import PersistenceConflictError
from kordena_fiscal.persistence.sqlite import SqliteFiscalDatabase
from kordena_fiscal.runtime.bling_oauth_service import (
    BlingOAuthService,
    BlingOAuthUnavailable,
    BlingTokenCipher,
)


class FakeOAuthClient:
    def __init__(self) -> None:
        self.exchange_calls = 0
        self.refresh_calls = 0
        self.fail_refresh: BlingOAuthError | None = None
        self.verified_token: str | None = None

    def authorization_url(self, state: str) -> str:
        return "https://www.bling.com.br/Api/v3/oauth/authorize?state=" + state

    def exchange(self, code: str) -> BlingTokenSet:
        self.exchange_calls += 1
        if code != "approved":
            raise BlingOAuthError(retryable=False, needs_reauth=True)
        return token_set("access-one", "refresh-one")

    def refresh(self, refresh_token: str) -> BlingTokenSet:
        self.refresh_calls += 1
        if self.fail_refresh is not None:
            raise self.fail_refresh
        if refresh_token != "refresh-one":
            raise BlingOAuthError(retryable=False, needs_reauth=True)
        return token_set("access-two", "refresh-two")


def token_set(access: str, refresh: str) -> BlingTokenSet:
    now = datetime.now(UTC)
    return BlingTokenSet(
        access_token=access, refresh_token=refresh,
        access_expires_at=now + timedelta(hours=1),
        scopes=frozenset({"pedidos_vendas", "empresas"}),
        refresh_expires_at=now + timedelta(days=30),
    )


def installation(tmp_path: Path):
    db = SqliteFiscalDatabase(tmp_path / "bling-oauth.sqlite")
    db.initialize()
    host = HostScope(HostNamespace("bling"), "ext-tenant", "ext-unit")
    with db() as uow:
        uow.bindings.add(FiscalAccountBinding(
            binding_id="oauth-binding", host_scope=host,
            fiscal_account_id=FiscalAccountId("tenant"),
            fiscal_unit_id=FiscalUnitId("unit"),
        ))
        uow.commit()
    store = BlingInstallationRepository(db)
    record = store.create(
        host_scope=host, company_id="expected-company",
        environment=FiscalEnvironment.HOMOLOGATION,
    )
    scope = FiscalApplicationService(db).resolve_scope(
        host, environment=FiscalEnvironment.HOMOLOGATION, correlation_id="oauth",
    )
    client = FakeOAuthClient()
    seen: list[tuple[str, str]] = []

    def verify(access: str, expected: str) -> None:
        seen.append((access, expected))
        if expected != "expected-company":
            raise RuntimeError("company mismatch")

    cipher = BlingTokenCipher(b"K" * 32)
    svc = BlingOAuthService(
        db, store, cipher, client, verify, required_scopes=frozenset({"pedidos_vendas"}),
        webhook_secret="synthetic-app-secret-123456",
    )
    return db, store, record, scope, client, svc, seen


def test_scoped_cipher_rejects_other_installation_or_purpose() -> None:
    cipher = BlingTokenCipher(b"A" * 32)
    encrypted = cipher.seal("a" * 32, "access", "opaque-secret")
    assert "opaque-secret" not in encrypted
    assert cipher.open("a" * 32, "access", encrypted) == "opaque-secret"
    with pytest.raises(BlingOAuthUnavailable):
        cipher.open("b" * 32, "access", encrypted)
    with pytest.raises(BlingOAuthUnavailable):
        cipher.open("a" * 32, "refresh", encrypted)


def test_state_is_one_use_and_bound_to_session_and_company(tmp_path: Path) -> None:
    db, store, record, scope, client, svc, seen = installation(tmp_path)
    url = svc.begin(scope, record.installation_id, actor_id="actor", session_id="session")
    state = url.split("state=")[1]
    with pytest.raises(BlingOAuthUnavailable):
        svc.complete(
            scope, state=state, code="approved", actor_id="actor", session_id="other",
        )
    assert client.exchange_calls == 0
    svc.complete(
        scope, state=state, code="approved", actor_id="actor", session_id="session",
    )
    assert client.exchange_calls == 1
    assert seen == [("access-one", "expected-company")]
    assert store.get_for_scope(scope, record.installation_id).state is BlingInstallationState.CONNECTED
    assert svc.access_token(scope, record.installation_id) == "access-one"
    assert svc.webhook_secret(record.installation_id) == b"synthetic-app-secret-123456"
    with pytest.raises(BlingOAuthUnavailable):
        svc.complete(
            scope, state=state, code="approved", actor_id="actor", session_id="session",
        )
    with db.connection() as connection:
        row = connection.execute(
            "SELECT access_ciphertext, refresh_ciphertext, webhook_secret_ciphertext "
            "FROM fm_bling_credentials WHERE installation_id = ?",
            (record.installation_id,),
        ).fetchone()
    assert row is not None
    assert all("access-one" not in str(field) for field in row)
    assert all("refresh-one" not in str(field) for field in row)


def test_refresh_uses_one_lease_and_rotates_without_leaking(tmp_path: Path) -> None:
    db, _, record, scope, client, svc, _ = installation(tmp_path)
    state = svc.begin(scope, record.installation_id, actor_id="a", session_id="s").split("state=")[1]
    svc.complete(scope, state=state, code="approved", actor_id="a", session_id="s")
    past = (datetime.now(UTC) - timedelta(seconds=20)).isoformat()
    with db.connection() as connection:
        connection.execute(
            "UPDATE fm_bling_credentials SET access_expires_at = ? "
            "WHERE installation_id = ?", (past, record.installation_id),
        )
        connection.commit()
    assert svc.access_token(scope, record.installation_id) == "access-two"
    assert client.refresh_calls == 1
    assert svc.access_token(scope, record.installation_id) == "access-two"
    assert client.refresh_calls == 1


def test_concurrent_refresh_lease_fails_closed(tmp_path: Path) -> None:
    db, _, record, scope, client, svc, _ = installation(tmp_path)
    state = svc.begin(scope, record.installation_id, actor_id="a", session_id="s").split("state=")[1]
    svc.complete(scope, state=state, code="approved", actor_id="a", session_id="s")
    with db.connection() as connection:
        connection.execute(
            "UPDATE fm_bling_credentials SET access_expires_at = ?, "
            "refresh_lease_until = ?, refresh_lease_owner = ? "
            "WHERE installation_id = ?",
            (
                (datetime.now(UTC) - timedelta(minutes=1)).isoformat(),
                (datetime.now(UTC) + timedelta(seconds=30)).isoformat(),
                "in-flight", record.installation_id,
            ),
        )
        connection.commit()
    with pytest.raises(BlingOAuthUnavailable) as exc:
        svc.access_token(scope, record.installation_id)
    assert exc.value.retryable
    assert client.refresh_calls == 0


def test_refresh_invalid_grant_sets_needs_reauth(tmp_path: Path) -> None:
    db, store, record, scope, client, svc, _ = installation(tmp_path)
    state = svc.begin(scope, record.installation_id, actor_id="a", session_id="s").split("state=")[1]
    svc.complete(scope, state=state, code="approved", actor_id="a", session_id="s")
    with db.connection() as connection:
        connection.execute(
            "UPDATE fm_bling_credentials SET access_expires_at = ? "
            "WHERE installation_id = ?",
            ((datetime.now(UTC) - timedelta(minutes=2)).isoformat(), record.installation_id),
        )
        connection.commit()
    client.fail_refresh = BlingOAuthError(retryable=False, needs_reauth=True)
    with pytest.raises(BlingOAuthUnavailable):
        svc.access_token(scope, record.installation_id)
    assert store.get_for_scope(scope, record.installation_id).state is BlingInstallationState.NEEDS_REAUTH


def test_oauth_transport_validates_access_and_expires() -> None:
    client = BlingOAuthClient(client_id="client-123", client_secret="secret-123")
    url = client.authorization_url("123456")
    assert "client_id=client-123" in url and "state=123456" in url
    token = BlingOAuthClient._parse({
        "access_token": "opaque-a", "refresh_token": "opaque-r",
        "token_type": "Bearer", "expires_in": 3600,
        "scope": "pedidos_vendas empresas",
    }, datetime.now(UTC))
    assert token.scopes == frozenset({"pedidos_vendas", "empresas"})
    with pytest.raises(BlingOAuthError):
        BlingOAuthClient._parse({
            "access_token": "a", "refresh_token": "",
            "token_type": "Bearer", "expires_in": 3600,
        }, datetime.now(UTC))
