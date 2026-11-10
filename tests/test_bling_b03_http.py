"""B-03: real portal identity, RBAC, CSRF, tenant and unit isolation."""
from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from kordena_fiscal.runtime.bling_operations import build_bling_operations_router
from kordena_fiscal.security.human_identity import (
    HumanAccount,
    HumanIdentityService,
    InMemoryHumanAccountRepository,
    InMemoryWebSessionRepository,
    PortalRole,
    ScryptPasswordHasher,
)
from kordena_fiscal.web import create_app

from test_bling_b02_operations import setup


def login_client(tmp_path: Path, *, tenant: str = "tenant", unit: str = "unit",
                 role: str = "owner"):
    _db, store, record, scope, service, seen, fetched, _pauses = setup(tmp_path)
    password = "synthetic-bling-operations-password"
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
    app.include_router(build_bling_operations_router(identity, store, service))
    client = TestClient(app, base_url="https://nfcore.test")
    assert client.post("/v1/auth/login", json={
        "email": "operator@example.test", "password": password,
    }).status_code == 200
    return client, record, scope, service, seen, fetched


def test_portal_lists_installs_only_on_authorized_unit(tmp_path: Path) -> None:
    client, view, scope, _service, _seen, _fetched = login_client(tmp_path)
    available = client.get(
        "/v1/portal/integrations/bling/installations/available?unit_id=unit"
    )
    assert available.status_code == 200
    assert available.headers["cache-control"] == "no-store"
    assert available.json()["rows"][0]["installation_id"] == view.installation_id
    assert "refresh_token" not in available.text
    assert "access_token" not in available.text
    wrong_unit = client.get(
        "/v1/portal/integrations/bling/installations/available?unit_id=other-unit"
    )
    assert wrong_unit.status_code == 403
    client.cookies.clear()
    assert client.get(
        "/v1/portal/integrations/bling/installations/available?unit_id=unit"
    ).status_code == 401


def test_operator_recovers_reviews_and_observes_without_second_auth(
    tmp_path: Path,
) -> None:
    client, view, _scope, _service, _seen, fetched = login_client(tmp_path)
    base = f"/v1/portal/integrations/bling/installations/{view.installation_id}"
    assert client.get(base + "/orders").status_code == 200
    assert client.get(base + "/provider-orders?limit=5").status_code == 200
    assert client.post(
        base + "/orders/105/recover", json={"request_id": "first-recover"},
    ).status_code == 403
    headers = {"X-CSRF-Token": client.cookies.get("nfcore_csrf")}
    blocked = client.post(
        base + "/orders/105/recover",
        json={"request_id": "first-recover", "tenant_id": "spoof"},
        headers=headers,
    )
    assert blocked.status_code == 422
    recovered = client.post(
        base + "/orders/105/recover",
        json={"request_id": "first-recover"}, headers=headers,
    )
    assert recovered.status_code == 200
    assert recovered.json()["outcome"] == "requires_review"
    assert fetched == [105]
    dashboard = client.get(base + "/orders")
    assert dashboard.status_code == 200
    assert dashboard.json()["rows"][0]["order_id"] == 105
    assert "total" not in dashboard.text
    assert client.get(base + "/metrics").status_code == 200
    assert client.get(base + "/jobs").status_code == 200
    detail = client.get(base + "/orders/105")
    assert detail.status_code == 200
    assert detail.json()["order"]["state"] == "review_required"


def test_role_and_tenant_isolation_block_listing_and_mutations(tmp_path: Path) -> None:
    for kwargs in ({"tenant": "wrong-tenant"}, {"unit": "wrong-unit"}, {"role": "auditor"}):
        path = tmp_path / ("isolated-" + next(iter(kwargs.values())))
        path.mkdir()
        client, view, _scope, _service, _seen, fetched = login_client(path, **kwargs)
        base = f"/v1/portal/integrations/bling/installations/{view.installation_id}"
        assert client.get(base + "/orders").status_code in {403, 404}
        headers = {"X-CSRF-Token": client.cookies.get("nfcore_csrf")}
        assert client.post(
            base + "/orders/105/recover",
            json={"request_id": "no-access"}, headers=headers,
        ).status_code in {403, 404}
        assert fetched == []


def test_batch_backfill_is_auth_and_csrf_protected(tmp_path: Path) -> None:
    client, view, _scope, _service, _seen, fetched = login_client(tmp_path)
    path = (
        f"/v1/portal/integrations/bling/installations/"
        f"{view.installation_id}/recovery/backfill"
    )
    body = {"page": 1, "limit": 2, "request_id": "operator-backfill"}
    assert client.post(path, json=body).status_code == 403
    response = client.post(
        path, json=body, headers={"X-CSRF-Token": client.cookies.get("nfcore_csrf")},
    )
    assert response.status_code == 200
    assert response.json()["recovered"] == 2
    assert response.json()["fiscal_issuance_started"] is False
    assert fetched == [105, 103]
