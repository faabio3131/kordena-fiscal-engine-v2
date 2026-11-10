"""A-02 activation surface: exact fiscal binding discovery and OAuth login gates."""
from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from test_bling_a02_oauth import installation

from kordena_fiscal.domain import (
    FiscalAccountBinding,
    FiscalAccountId,
    FiscalUnitId,
    HostNamespace,
    HostScope,
)
from kordena_fiscal.runtime.bling_oauth_routes import build_bling_oauth_router
from kordena_fiscal.security.human_identity import (
    HumanAccount,
    HumanIdentityService,
    InMemoryHumanAccountRepository,
    InMemoryWebSessionRepository,
    PortalRole,
    ScryptPasswordHasher,
)
from kordena_fiscal.web import create_app


def login(tmp_path: Path, *, tenant: str = "tenant", unit: str = "unit",
          role: str = "owner") -> tuple[TestClient, str]:
    db, store, record, _scope, _client, svc, _seen = installation(tmp_path)
    with db() as uow:
        uow.bindings.add(FiscalAccountBinding(
            binding_id="unrelated-binding",
            host_scope=HostScope(HostNamespace("other"), "other-ext-tenant", "other-ext-unit"),
            fiscal_account_id=FiscalAccountId("tenant"),
            fiscal_unit_id=FiscalUnitId("unit"),
        ))
        uow.commit()
    password = "synthetic-setup-password"
    hasher = ScryptPasswordHasher()
    identity = HumanIdentityService(
        accounts=InMemoryHumanAccountRepository((
            HumanAccount(
                account_id="operator", email="operator@example.test",
                password_hash=hasher.hash(password), tenant_id=tenant,
                role=PortalRole(role), unit_ids=frozenset({unit}),
            ),
        )),
        sessions=InMemoryWebSessionRepository(), password_hasher=hasher,
    )
    app = create_app(human_identity=identity)
    app.include_router(build_bling_oauth_router(identity, store, svc))
    client = TestClient(app, base_url="https://nfcore.test")
    assert client.post("/v1/auth/login", json={
        "email": "operator@example.test", "password": password,
    }).status_code == 200
    return client, record.installation_id


def test_eligible_bindings_exact_tenant_unit_and_bling_only(tmp_path: Path) -> None:
    c, _ = login(tmp_path)
    url = "/v1/portal/integrations/bling/bindings/available"
    result = c.get(url + "?unit_id=unit")
    assert result.status_code == 200
    assert result.headers["cache-control"] == "no-store"
    assert result.json()["rows"] == [{"binding_id": "oauth-binding", "unit_id": "unit"}]
    assert "other-ext-tenant" not in result.text
    assert c.get(url + "?unit_id=other-unit").status_code == 403
    assert c.get(url + "?unit_id=unit&offset=-1").status_code == 422
    c.cookies.clear()
    assert c.get(url + "?unit_id=unit").status_code == 401


def test_eligible_bindings_fail_closed_for_wrong_tenant_and_role(tmp_path: Path) -> None:
    for title, kwargs in [
        ("foreign", {"tenant": "foreign-tenant"}),
        ("auditor", {"role": "auditor"}),
    ]:
        path = tmp_path / title
        path.mkdir()
        client, _ = login(path, **kwargs)
        result = client.get(
            "/v1/portal/integrations/bling/bindings/available?unit_id=unit",
        )
        assert result.status_code in (403, 404)


def test_connect_requires_same_session_and_csrf(tmp_path: Path) -> None:
    client, installation_id = login(tmp_path)
    url = f"/v1/portal/integrations/bling/installations/{installation_id}/connect"
    assert client.post(url).status_code == 403
    result = client.post(url, headers={
        "X-CSRF-Token": client.cookies.get("nfcore_csrf"),
    })
    assert result.status_code == 200
    assert result.json()["authorization_url"].startswith(
        "https://www.bling.com.br/Api/v3/oauth/authorize?state=",
    )

def test_create_binding_is_same_tenant_unit_idempotent_and_csrf_protected(tmp_path: Path) -> None:
    client, _ = login(tmp_path)
    url = "/v1/portal/integrations/bling/bindings"
    assert client.post(url, json={"unit_id": "unit"}).status_code == 403
    h = {"X-CSRF-Token": client.cookies.get("nfcore_csrf")}
    blocked = client.post(
        url, json={"unit_id": "unit", "tenant_id": "spoof"}, headers=h,
    )
    assert blocked.status_code == 422
    assert client.post(url, json={"unit_id": "other-unit"}, headers=h).status_code == 403
    existed = client.post(url, json={"unit_id": "unit"}, headers=h)
    assert existed.status_code == 200
    assert existed.json() == {"binding_id": "oauth-binding", "created": False}
    other = tmp_path / "new"
    other.mkdir()
    from kordena_fiscal.persistence.sqlite import SqliteFiscalDatabase
    from kordena_fiscal.persistence.bling_installations import BlingInstallationRepository
    db = SqliteFiscalDatabase(other / "blank.sqlite")
    db.initialize(enable_bling=True)
    password = "synthetic"
    hasher = ScryptPasswordHasher()
    identity = HumanIdentityService(
        accounts=InMemoryHumanAccountRepository((
            HumanAccount(
                account_id="operator", email="operator@example.test",
                password_hash=hasher.hash(password), tenant_id="tenant",
                role=PortalRole.OWNER, unit_ids=frozenset({"unit"}),
            ),
        )),
        sessions=InMemoryWebSessionRepository(), password_hasher=hasher,
    )
    from test_bling_a02_oauth import FakeOAuthClient
    from kordena_fiscal.runtime.bling_oauth_service import (
        BlingOAuthService, BlingTokenCipher,
    )
    store = BlingInstallationRepository(db)
    svc = BlingOAuthService(
        db, store, BlingTokenCipher(b"K" * 32), FakeOAuthClient(),
        lambda token, company: None, required_scopes=frozenset({"pedidos_vendas"}),
        webhook_secret="synthetic-app-secret-123456",
    )
    app = create_app(human_identity=identity)
    app.include_router(build_bling_oauth_router(identity, store, svc))
    with TestClient(app, base_url="https://nfcore.test") as fresh:
        assert fresh.post("/v1/auth/login", json={
            "email": "operator@example.test", "password": password,
        }).status_code == 200
        headers = {"X-CSRF-Token": fresh.cookies.get("nfcore_csrf")}
        created = fresh.post(url, json={"unit_id": "unit"}, headers=headers)
        assert created.status_code == 201
        assert created.json()["created"] is True
        second = fresh.post(url, json={"unit_id": "unit"}, headers=headers)
        assert second.status_code == 200
        assert second.json()["binding_id"] == created.json()["binding_id"]
        available = fresh.get(
            "/v1/portal/integrations/bling/bindings/available?unit_id=unit",
        )
        assert available.json()["rows"] == [{
            "binding_id": created.json()["binding_id"], "unit_id": "unit",
        }]
