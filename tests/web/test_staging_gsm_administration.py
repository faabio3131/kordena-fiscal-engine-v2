"""P05 tests for staging binding and egress administration without live credentials."""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from kordena_fiscal.domain import FiscalEnvironment
from kordena_fiscal.runtime.api_staging_gsm_probe import staging_probe_verifier
from kordena_fiscal.runtime.config import RuntimeConfigurationError
from kordena_fiscal.web.staging_gsm_binding_admin import create_staging_gsm_binding_router
from kordena_fiscal.web.staging_webhook_approval import create_staging_webhook_egress_router

COOKIES = {"nfcore_session": "signed-cookie", "nfcore_csrf": "csrf-proof"}
HEADERS = {"X-CSRF-Token": "csrf-proof"}


@dataclass
class _Account:
    account_id: str = "pilot-admin"
    tenant_id: str = "nfcore-staging-e2e"
    enabled: bool = True
    is_platform_admin: bool = True


class _Actor:
    def __init__(self, admin: bool = True, allow_integration: bool = True) -> None:
        self.account = _Account(is_platform_admin=admin)
        self.allow_integration = allow_integration

    def assert_permission(self, permission: object, *, unit_id: str | None = None) -> None:
        if not self.allow_integration or unit_id != "pilot-gsm-staging":
            raise ValueError("permission denied")


class _Identity:
    def __init__(self, actor: _Actor) -> None:
        self.actor = actor

    def authenticate_session(self, *, session_token: str, now: object) -> _Actor:
        assert session_token == "signed-cookie"
        return self.actor

    def assert_csrf(self, actor: _Actor, token: str) -> None:
        assert actor is self.actor and token == "csrf-proof"


class _BindingAdmin:
    def __init__(self) -> None:
        self.bound: list[Any] = []

    def put(
        self, *, actor: _Actor, binding: Any, expected_revision: int, correlation_id: str
    ) -> None:
        assert actor.account.is_platform_admin
        assert expected_revision == 0
        assert correlation_id
        self.bound.append(binding)


def _client(router: object) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_binding_requires_session_and_platform_admin() -> None:
    administration = _BindingAdmin()
    client = _client(create_staging_gsm_binding_router(_Identity(_Actor()), administration))
    assert client.post("/internal/staging/gsm-binding").status_code == 401
    client.cookies.update(COOKIES)
    assert client.post("/internal/staging/gsm-binding").status_code == 403
    response = client.post("/internal/staging/gsm-binding", headers=HEADERS)
    assert response.status_code == 200
    assert {b.workload_id for b in administration.bound} == {"nfcore-worker", "nfcore-api"}
    assert all(
        b.resource.endswith("nfcore-stg-pilot-webhook-signing")
        for b in administration.bound
    )


def test_binding_rejects_non_platform_admin() -> None:
    administration = _BindingAdmin()
    client = _client(
        create_staging_gsm_binding_router(_Identity(_Actor(admin=False)), administration)
    )
    client.cookies.update(COOKIES)
    assert client.post("/internal/staging/gsm-binding", headers=HEADERS).status_code == 403
    assert not administration.bound


class _Store:
    def __init__(self) -> None:
        self.version = 0
        self.record: dict[str, Any] | None = None
        self.audits: list[Any] = []
        self.committed = False

    def configuration_version(self, scope: Any, surface: str, destination: str) -> int:
        assert surface == "webhooks"
        return self.version

    def put_webhook_destination(self, destination: Any) -> Any:
        self.record = {"url": destination.url, "enabled": True, "approval_status": "pending",
                       "requested_by": "", "approved_by": None}
        return destination

    def advance_configuration_version(
        self, scope: Any, surface: str, destination: str, expected: int
    ) -> int:
        assert expected == self.version
        self.version += 1
        return self.version

    def record_webhook_approval(
        self, scope: Any, destination: str, *, status: str, version: int | None,
        expires_at: str | None, url_sha256: str | None,
        requested_by: str | None = None, approved_by: str | None = None
    ) -> None:
        assert self.record is not None
        self.record.update({"approval_status": status, "approved_version": version,
                            "approved_until": expires_at, "approved_url_sha256": url_sha256,
                            "approved_by": approved_by})
        if requested_by is not None:
            self.record["requested_by"] = requested_by

    def webhook_approval(self, scope: Any, destination: str) -> dict[str, Any] | None:
        return self.record


class _Uow:
    def __init__(self, store: _Store) -> None:
        self.control_plane = self
        self.commercial = store
        self.store = store

    def __enter__(self) -> _Uow:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def get_unit(self, tenant: str, unit: str) -> SimpleNamespace:
        return SimpleNamespace(
            enabled_environments=frozenset({FiscalEnvironment.HOMOLOGATION})
        )

    def append_audit(self, event: Any) -> None:
        self.store.audits.append(event)

    def commit(self) -> None:
        self.store.committed = True


def test_egress_request_requires_integration_permission_and_admin_approval() -> None:
    store = _Store()
    actor = _Actor()
    client = _client(create_staging_webhook_egress_router(
        _Identity(actor), lambda: _Uow(store)
    ))
    client.cookies.update(COOKIES)
    assert client.post("/internal/staging/webhook-destination/request").status_code == 403
    first = client.post("/internal/staging/webhook-destination/request", headers=HEADERS)
    assert first.status_code == 200
    assert first.json()["status"] == "pending"
    assert store.record is not None
    assert store.record["approved_by"] is None
    second = client.post("/internal/staging/webhook-destination/approve", headers=HEADERS)
    assert second.status_code == 200
    assert second.json()["status"] == "approved"
    assert store.record["approved_by"] == "pilot-admin"
    assert len(store.audits) == 2
    assert store.committed
    assert client.post(
        "/internal/staging/webhook-destination/approve", headers=HEADERS
    ).status_code == 409


def test_staging_verifier_refuses_wrong_environment_and_incomplete_identity() -> None:
    assert staging_probe_verifier(None, {}) is None
    import pytest

    with pytest.raises(RuntimeConfigurationError):
        staging_probe_verifier(None, {"NFCORE_API_GSM_MODE": "scoped-staging-sa-v1",
                                      "NFCORE_ENVIRONMENT": "production"})
    with pytest.raises(RuntimeConfigurationError):
        staging_probe_verifier(None, {"NFCORE_API_GSM_MODE": "scoped-staging-sa-v1",
                                      "NFCORE_ENVIRONMENT": "staging"})
