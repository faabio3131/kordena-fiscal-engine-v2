import hmac
import json
from pathlib import Path
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from kordena_fiscal.application.bling_orders import BlingOrders
from kordena_fiscal.application.bling_processing import BlingProcessingHandler
from kordena_fiscal.application.service import FiscalApplicationService
from kordena_fiscal.connectors.bling_webhook import BlingWebhookError, verify_order_notification
from kordena_fiscal.domain import (
    FiscalAccountBinding,
    FiscalAccountId,
    FiscalEnvironment,
    FiscalUnitId,
    HostNamespace,
    HostScope,
)
from kordena_fiscal.persistence.sqlite import SqliteFiscalDatabase
from kordena_fiscal.runtime.bling_ingress import build_bling_ingress
from kordena_fiscal.runtime.fiscal_runtime import CanonicalFiscalOperationPath

SECRET = b"synthetic-test-secret"
BODY = json.dumps(
    {
        "eventId": "synthetic-event",
        "date": "2026-11-09T04:00:00Z",
        "version": "v1",
        "event": "order.updated",
        "companyId": "synthetic-company",
        "data": {"id": 9001},
    }
).encode()
COMPANY = "synthetic-company"
SIGNATURE = "sha256=" + hmac.digest(SECRET, BODY, "sha256").hex()


def test_bling_webhook_authenticates_and_extracts_order() -> None:
    event = verify_order_notification(
        BODY,
        SIGNATURE,
        client_secret=SECRET,
        expected_company_id=COMPANY,
    )
    assert (event.event_id, event.company_id, event.order_id) == ("synthetic-event", COMPANY, 9001)


@pytest.mark.parametrize(("body", "company_id"), [(BODY + b" ", COMPANY), (BODY, "other-company")])
def test_bling_webhook_rejects_tampering_and_cross_company(
    body: bytes,
    company_id: str,
) -> None:
    with pytest.raises(BlingWebhookError):
        verify_order_notification(
            body,
            SIGNATURE,
            client_secret=SECRET,
            expected_company_id=company_id,
        )


def test_bling_ingress_acknowledges_durable_replay_and_rejects_conflict(tmp_path: Path) -> None:
    database = SqliteFiscalDatabase(tmp_path / "bling.sqlite")
    database.initialize()
    with database() as uow:
        uow.bindings.add(
            FiscalAccountBinding(
                binding_id="bling-test",
                host_scope=HostScope(HostNamespace("bling"), "tenant", "unit"),
                fiscal_account_id=FiscalAccountId("fiscal-tenant"),
                fiscal_unit_id=FiscalUnitId("fiscal-unit"),
            )
        )
        uow.commit()

    router = build_bling_ingress(
        FiscalApplicationService(database),
        {
            "NFCORE_BLING_CLIENT_SECRET": SECRET.decode(),
            "NFCORE_BLING_COMPANY_ID": "synthetic-company",
            "NFCORE_BLING_TENANT_ID": "tenant",
            "NFCORE_BLING_UNIT_ID": "unit",
            "NFCORE_BLING_ENVIRONMENT": "homologation",
        },
    )
    assert router is not None
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as client:
        headers = {"X-Bling-Signature-256": SIGNATURE}
        assert client.post("/webhooks/bling", content=BODY, headers=headers).status_code == 202
        assert client.post("/webhooks/bling", content=BODY, headers=headers).status_code == 202
        changed = BODY.replace(b"9001", b"9002")
        headers["X-Bling-Signature-256"] = "sha256=" + hmac.digest(SECRET, changed, "sha256").hex()
        assert client.post("/webhooks/bling", content=changed, headers=headers).status_code == 409

    with database() as uow:
        counts = uow.outbox.counts_by_status()
        assert sum(counts.values()) == 1

    application = FiscalApplicationService(database)
    scope = application.resolve_scope(
        HostScope(HostNamespace("bling"), "tenant", "unit"),
        environment=FiscalEnvironment.HOMOLOGATION,
        correlation_id="test",
    )
    with database() as uow:
        (job,) = uow.outbox.list_for_scope(scope)
    fetch = Mock(
        return_value={
            "id": 9001,
            "contato": {
                "nome": "Cliente sintético",
                "numeroDocumento": "12345678000190",
                "endereco": {"uf": "SP"},
            },
            "itens": [
                {
                    "codigo": "SKU",
                    "descricao": "Produto",
                    "ncm": "85285200",
                    "cfop": "5102",
                    "quantidade": 1,
                    "valor": "10.00",
                }
            ],
        }
    )
    orders = BlingOrders(database, scope, COMPANY)
    handler = BlingProcessingHandler(orders, fetch, CanonicalFiscalOperationPath(application))
    assert handler.dispatch(job).reference == orders.key(9001)
    assert handler.dispatch(job).reference == orders.key(9001)
    fetch.assert_called_once_with(9001)
    row = orders.get(9001)
    assert row is not None
    assert row["state"] == "review_required"
    assert row["normalization_ready"] is True
    assert row["document_id"] is None


@pytest.mark.parametrize(
    "change",
    [
        {"version": "v2"},
        {"date": "2026-11-09T04:00:00"},
        {"data": {"id": True}},
        {"data": {"id": -1}},
        {"data": {"id": "9001"}},
        {"event": "product.updated"},
        {"eventId": ""},
    ],
)
def test_signed_but_invalid_event_is_refused(change):
    body = json.dumps({**json.loads(BODY), **change}).encode()
    signature = "sha256=" + hmac.digest(SECRET, body, "sha256").hex()
    with pytest.raises(BlingWebhookError):
        verify_order_notification(
            body,
            signature,
            client_secret=SECRET,
            expected_company_id=COMPANY,
        )


def test_duplicate_json_members_are_refused_after_signature_verification():
    body = BODY[:-1] + b',"data":{"id":9002}}'
    signature = "sha256=" + hmac.digest(SECRET, body, "sha256").hex()
    with pytest.raises(BlingWebhookError):
        verify_order_notification(
            body, signature, client_secret=SECRET, expected_company_id=COMPANY
        )
