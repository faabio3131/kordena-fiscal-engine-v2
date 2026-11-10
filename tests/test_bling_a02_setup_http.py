"""A-02 activation surface: exact fiscal binding discovery and OAuth login gates."""
from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from test_bling_a02_oauth import FakeOAuthClient, installation

from kordena_fiscal.domain import (
    FiscalAccountBinding,
    FiscalAccountId,
    FiscalUnitId,
    HostNamespace,
    HostScope,
)
from kordena_fiscal.persistence.bling_installations import BlingInstallationRepository
from kordena_fiscal.persistence.sqlite import SqliteFiscalDatabase
from kordena_fiscal.runtime.bling_oauth_routes import build_bling_oauth_router
from kordena_fiscal.runtime.bling_oauth_service import BlingOAuthService, BlingTokenCipher
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
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    foreign_client, _ = login(foreign, tenant="foreign-tenant")
    path = "/v1/portal/integrations/bling/bindings/available?unit_id=unit"
    foreign_result = foreign_client.get(path)
    # The foreign tenant may list its own (empty) bindings, never another
    # tenant's binding IDs. A successful empty response is correct isolation.
    assert foreign_result.status_code == 200
    assert foreign_result.json()["rows"] == []
    assert "oauth-binding" not in foreign_result.text

    auditor = tmp_path / "auditor"
    auditor.mkdir()
    auditor_client, _ = login(auditor, role="auditor")
    assert auditor_client.get(path).status_code in (403, 404)


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
    created_for_session = client.post(url, json={"unit_id": "unit"}, headers=h)
    # The fixture's legacy Bling host scope is ext-tenant/ext-unit; it must
    # never be silently reused as this session's tenant/unit host authority.
    assert created_for_session.status_code == 201
    session_binding = created_for_session.json()["binding_id"]
    assert session_binding != "oauth-binding"
    assert created_for_session.json()["created"] is True
    repeated = client.post(url, json={"unit_id": "unit"}, headers=h)
    assert repeated.status_code == 200
    assert repeated.json() == {"binding_id": session_binding, "created": False}
    available = client.get(
        "/v1/portal/integrations/bling/bindings/available?unit_id=unit",
    )
    assert available.status_code == 200
    assert {row["binding_id"] for row in available.json()["rows"]} == {
        "oauth-binding", session_binding,
    }
    other = tmp_path / "new"
    other.mkdir()
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

def test_browser_oauth_callback_redirects_without_referrer_or_code(tmp_path: Path) -> None:
    from urllib.parse import parse_qs, urlsplit

    client, install_id = login(tmp_path)
    headers = {"X-CSRF-Token": client.cookies.get("nfcore_csrf")}
    connected = client.post(
        f"/v1/portal/integrations/bling/installations/{install_id}/connect",
        headers=headers,
    )
    assert connected.status_code == 200
    state = parse_qs(urlsplit(connected.json()["authorization_url"]).query)["state"][0]
    response = client.get(
        f"/v1/portal/integrations/bling/oauth/callback?state={state}&code=approved",
        headers={"Accept": "text/html"}, follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/?bling=connected"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert "approved" not in response.headers["location"]
