from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from kordena_fiscal.security.human_identity import (
    HumanAccount,
    HumanIdentityService,
    InMemoryHumanAccountRepository,
    InMemoryWebSessionRepository,
    PortalRole,
    ScryptPasswordHasher,
)
from kordena_fiscal.web import create_app
from kordena_fiscal.web.human_auth import CSRF_COOKIE, CSRF_HEADER, SESSION_COOKIE

NOW = datetime(2026, 9, 14, 16, 45, tzinfo=UTC)
PASSWORD = "correct-horse-nfcore-2026"


def identity() -> HumanIdentityService:
    hasher = ScryptPasswordHasher()
    account = HumanAccount(
        account_id="account-web-1",
        email="owner@example.com",
        password_hash=hasher.hash(PASSWORD),
        tenant_id="tenant-real-authority",
        role=PortalRole.OWNER,
        unit_ids=frozenset({"unit-a"}),
    )
    return HumanIdentityService(
        accounts=InMemoryHumanAccountRepository((account,)),
        sessions=InMemoryWebSessionRepository(),
        password_hasher=hasher,
        session_ttl=timedelta(hours=8),
    )


def client() -> TestClient:
    return TestClient(create_app(human_identity=identity()), base_url="https://nfcore.test")


def test_auth_routes_are_not_exposed_without_identity_dependency() -> None:
    anonymous = TestClient(create_app(), base_url="https://nfcore.test")

    assert anonymous.post("/v1/auth/login", json={}).status_code == 404


def test_login_sets_secure_http_only_session_and_separate_csrf_cookie() -> None:
    web = client()

    response = web.post(
        "/v1/auth/login",
        json={"email": "OWNER@example.com", "password": PASSWORD},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["account"]["tenant_id"] == "tenant-real-authority"
    assert body["account"]["role"] == "owner"
    assert "password" not in str(body).lower()
    assert "session_token" not in body

    set_cookies = response.headers.get_list("set-cookie")
    session_cookie = next(value for value in set_cookies if value.startswith(f"{SESSION_COOKIE}="))
    csrf_cookie = next(value for value in set_cookies if value.startswith(f"{CSRF_COOKIE}="))
    assert "HttpOnly" in session_cookie
    assert "Secure" in session_cookie
    assert "SameSite=lax" in session_cookie
    assert "HttpOnly" not in csrf_cookie
    assert "Secure" in csrf_cookie


def test_me_derives_tenant_from_authenticated_account_not_spoofable_header() -> None:
    web = client()
    login = web.post(
        "/v1/auth/login",
        json={"email": "owner@example.com", "password": PASSWORD},
    )
    assert login.status_code == 200

    me = web.get("/v1/auth/me", headers={"X-FM-Tenant-Id": "attacker-tenant"})

    assert me.status_code == 200
    assert me.json()["account"]["tenant_id"] == "tenant-real-authority"


def test_me_requires_valid_session() -> None:
    web = client()

    response = web.get("/v1/auth/me")

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "SESSION_REQUIRED"


def test_logout_requires_csrf_and_revokes_session() -> None:
    web = client()
    login = web.post(
        "/v1/auth/login",
        json={"email": "owner@example.com", "password": PASSWORD},
    )
    assert login.status_code == 200

    without_csrf = web.post("/v1/auth/logout")
    assert without_csrf.status_code == 403
    assert web.get("/v1/auth/me").status_code == 200

    csrf = web.cookies.get(CSRF_COOKIE)
    assert csrf
    logout = web.post("/v1/auth/logout", headers={CSRF_HEADER: csrf})

    assert logout.status_code == 204
    assert web.get("/v1/auth/me").status_code == 401


def test_invalid_credentials_return_generic_response() -> None:
    web = client()

    response = web.post(
        "/v1/auth/login",
        json={"email": "owner@example.com", "password": "wrong-password-value"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == {
        "code": "INVALID_CREDENTIALS",
        "message": "Invalid email or password",
    }
