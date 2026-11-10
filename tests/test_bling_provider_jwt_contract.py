"""Synthetic Bling wire contract: JWT headers, company ID and HMAC app key."""

from __future__ import annotations

import base64
from pathlib import Path
from unittest.mock import patch

import pytest

from kordena_fiscal.connectors.bling_api import (
    BlingApiError,
    fetch_sales_order,
    update_sales_order_status,
    verify_company,
)
from kordena_fiscal.persistence.sqlite import SqliteFiscalDatabase
from kordena_fiscal.runtime.bling_oauth_factory import build_bling_oauth_service


def test_numeric_company_id_matches_installation_string() -> None:
    with patch("kordena_fiscal.connectors.bling_api.HTTPSConnection") as factory:
        response = factory.return_value.getresponse.return_value
        response.status = 200
        response.read.return_value = b'{"data":{"id":123}}'
        verify_company("synthetic-jwt", "123")
        factory.return_value.request.assert_called_once_with(
            "GET", "/Api/v3/empresas/me/dados-basicos",
            headers={
                "Authorization": "Bearer synthetic-jwt",
                "Accept": "application/json",
                "enable-jwt": "1",
            },
        )
        with pytest.raises(BlingApiError):
            verify_company("synthetic-jwt", "124")


def test_order_fetch_and_status_patch_include_jwt_header() -> None:
    with patch("kordena_fiscal.connectors.bling_api.HTTPSConnection") as factory:
        response = factory.return_value.getresponse.return_value
        response.status = 200
        response.read.return_value = b'{"data":{"id":5}}'
        assert fetch_sales_order(5, "synthetic-jwt")["id"] == 5
        assert factory.return_value.request.call_args.kwargs["headers"]["enable-jwt"] == "1"
    with patch("kordena_fiscal.connectors.bling_api.HTTPSConnection") as factory:
        factory.return_value.getresponse.return_value.status = 204
        update_sales_order_status(5, 42, "synthetic-jwt")
        assert factory.return_value.request.call_args.kwargs["headers"]["enable-jwt"] == "1"


def test_bling_factory_uses_oauth_app_secret_for_webhook_hmac(tmp_path: Path) -> None:
    secrets_dir = tmp_path / "keys"
    secrets_dir.mkdir(mode=0o700)
    key_data = {
        "client-secret": "synthetic-client-secret-for-bling-hmac",
        "master-key": base64.b64encode(b"K" * 32).decode(),
    }
    paths = {}
    for name, value in key_data.items():
        p = secrets_dir / name
        p.write_text(value, encoding="ascii")
        p.chmod(0o600)
        paths[name] = str(p)
    database = SqliteFiscalDatabase(tmp_path / "bling.sqlite")
    database.initialize(enable_bling=True)
    _, service = build_bling_oauth_service(database, {
        "NFCORE_BLING_INSTALLATIONS_ENABLED": "true",
        "NFCORE_SECRET_BACKEND": "external",
        "NFCORE_BLING_CLIENT_ID": "synthetic-app",
        "NFCORE_BLING_APPROVED_SCOPES": "pedidos_vendas empresas",
        "NFCORE_BLING_CLIENT_SECRET_FILE": paths["client-secret"],
        "NFCORE_BLING_TOKEN_MASTER_KEY_FILE": paths["master-key"],
    })
    assert service._webhook_secret == key_data["client-secret"]
