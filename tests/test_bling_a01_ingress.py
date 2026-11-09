"""A-01: webhook auth is per installation and never trusts company/tenant from JSON."""
from __future__ import annotations

import hashlib
import hmac
import json
from datetime import UTC, datetime
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from kordena_fiscal.application.service import FiscalApplicationService
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
from kordena_fiscal.persistence.sqlite import SqliteFiscalDatabase
from kordena_fiscal.runtime.bling_multitenant_ingress import build_multitenant_bling_ingress


class FakeSecrets:
    def __init__(self, items: dict[str, bytes]) -> None:
        self.items = items

    def webhook_secret(self, installation_id: str) -> bytes:
        return self.items[installation_id]


def _body(company: str, order_id: int, event_id: str) -> bytes:
    return json.dumps(
        {
            "eventId": event_id,
            "companyId": company,
            "data": {"id": order_id},
            "event": "order.created",
            "date": datetime.now(UTC).isoformat(),
            "version": "v1",
        },
        separators=(",", ":"),
    ).encode()


def _signature(body: bytes, secret: bytes) -> str:
    return "sha256=" + hmac.new(secret, body, hashlib.sha256).hexdigest()


def test_multitenant_webhook_is_hmac_verified_and_scope_bound(tmp_path: Path) -> None:
    db = SqliteFiscalDatabase(tmp_path / "webhooks.sqlite")
    db.initialize()
    with db() as uow:
        for tenant in ("a", "b"):
            for unit in ("1", "2"):
                uow.bindings.add(FiscalAccountBinding(
                    binding_id=f"binding-{tenant}-{unit}",
                    host_scope=HostScope(HostNamespace("bling"), tenant, unit),
                    fiscal_account_id=FiscalAccountId(f"fiscal-{tenant}"),
                    fiscal_unit_id=FiscalUnitId(f"unit-{unit}"),
                ))
        uow.commit()
    store = BlingInstallationRepository(db)
    credentials: dict[str, bytes] = {}
    installations = []
    for tenant in ("a", "b"):
        for unit in ("1", "2"):
            host = HostScope(HostNamespace("bling"), tenant, unit)
            installation = store.create(
                host_scope=host, company_id=f"company-{tenant}-{unit}",
                environment=FiscalEnvironment.HOMOLOGATION,
            )
            scope = FiscalApplicationService(db).resolve_scope(
                host, environment=FiscalEnvironment.HOMOLOGATION, correlation_id="tests",
            )
            store.transition(
                scope, installation.installation_id, expected_revision=1,
                state=BlingInstallationState.CONNECTED,
            )
            secret = f"test-secret-{tenant}-{unit}-123456".encode()
            credentials[installation.installation_id] = secret
            installations.append(installation)

    app = FastAPI()
    app.include_router(build_multitenant_bling_ingress(
        FiscalApplicationService(db), store, FakeSecrets(credentials),
    ))
    with TestClient(app) as client:
        for index, installation in enumerate(installations):
            body = _body(installation.company_id, 9000 + index, f"event-{index}")
            secret = credentials[installation.installation_id]
            url = f"/webhooks/bling/installations/{installation.installation_id}"
            assert client.post(
                url, content=body, headers={"X-Bling-Signature-256": _signature(body, secret)}
            ).status_code == 202
            assert client.post(
                url, content=body, headers={"X-Bling-Signature-256": _signature(body, secret)}
            ).status_code == 202
            # Valid signature from another installation cannot impersonate this company.
            other_secret = credentials[installations[(index + 1) % 4].installation_id]
            assert client.post(
                url, content=body,
                headers={"X-Bling-Signature-256": _signature(body, other_secret)},
            ).status_code == 400
            forged = _body("forged", 9000 + index, f"event-forged-{index}")
            assert client.post(
                url, content=forged,
                headers={"X-Bling-Signature-256": _signature(forged, secret)},
            ).status_code == 400
        assert client.post(
            "/webhooks/bling/installations/unknown", content=b"x",
        ).status_code == 404
    with db() as uow:
        assert sum(uow.outbox.counts_by_status().values()) == 4


def test_unconfigured_installation_rejects_signed_event(tmp_path: Path) -> None:
    db = SqliteFiscalDatabase(tmp_path / "inactive.sqlite")
    db.initialize()
    with db() as uow:
        uow.bindings.add(FiscalAccountBinding(
            binding_id="binding",
            host_scope=HostScope(HostNamespace("bling"), "t", "u"),
            fiscal_account_id=FiscalAccountId("fiscal-t"),
            fiscal_unit_id=FiscalUnitId("fiscal-u"),
        ))
        uow.commit()
    store = BlingInstallationRepository(db)
    row = store.create(
        host_scope=HostScope(HostNamespace("bling"), "t", "u"),
        company_id="company", environment=FiscalEnvironment.HOMOLOGATION,
    )
    app = FastAPI()
    app.include_router(build_multitenant_bling_ingress(
        FiscalApplicationService(db), store,
        FakeSecrets({row.installation_id: b"long-secret-123456"}),
    ))
    with TestClient(app) as client:
        assert client.post(
            f"/webhooks/bling/installations/{row.installation_id}",
            content=_body("company", 1, "event-1"),
        ).status_code == 409
