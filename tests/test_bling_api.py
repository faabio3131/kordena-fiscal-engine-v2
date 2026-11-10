from decimal import Decimal
from unittest.mock import patch

import pytest

from kordena_fiscal.connectors.bling_api import BlingApiError, fetch_sales_order


def test_bling_fetch_uses_fixed_origin_and_checks_order_identity() -> None:
    with patch("kordena_fiscal.connectors.bling_api.HTTPSConnection") as connect:
        connection = connect.return_value
        response = connection.getresponse.return_value
        response.status = 200
        response.read.return_value = b'{"data":{"id":9001,"total":12.30}}'
        assert fetch_sales_order(9001, "synthetic") == {"id": 9001, "total": Decimal("12.30")}
        connect.assert_called_once_with("api.bling.com.br", timeout=10)
        connection.request.assert_called_once_with(
            "GET",
            "/Api/v3/pedidos/vendas/9001",
            headers={
                "Authorization": "Bearer synthetic",
                "Accept": "application/json",
                "enable-jwt": "1",
            },
        )
        response.read.return_value = b'{"data":{"id":9002}}'
        with pytest.raises(BlingApiError) as error:
            fetch_sales_order(9001, "synthetic")
        assert not error.value.retryable


@pytest.mark.parametrize(
    ("status", "retryable"),
    [(302, False), (401, False), (429, True), (503, True)],
)
def test_bling_fetch_classifies_provider_errors(status: int, retryable: bool) -> None:
    with patch("kordena_fiscal.connectors.bling_api.HTTPSConnection") as connect:
        connection = connect.return_value
        connection.getresponse.return_value.status = status
        with pytest.raises(BlingApiError) as error:
            fetch_sales_order(9001, "synthetic")
        assert error.value.status == status
        assert error.value.retryable is retryable
        connection.close.assert_called_once()


def test_bling_status_patch_uses_official_contract_and_only_accepts_204() -> None:
    from kordena_fiscal.connectors.bling_api import update_sales_order_status

    with patch("kordena_fiscal.connectors.bling_api.HTTPSConnection") as connect:
        connection = connect.return_value
        connection.getresponse.return_value.status = 204
        update_sales_order_status(9001, 10, "synthetic")
        connection.request.assert_called_once_with(
            "PATCH",
            "/Api/v3/pedidos/vendas/9001/situacoes/10",
            headers={
                "Authorization": "Bearer synthetic",
                "Accept": "application/json",
                "enable-jwt": "1",
            },
        )
        connection.close.assert_called_once()
        connection.getresponse.return_value.status = 200
        with pytest.raises(BlingApiError):
            update_sales_order_status(9001, 10, "synthetic")


@pytest.mark.parametrize("value", [True, 0, -1, "2"])
def test_bling_status_patch_refuses_invalid_identifiers_before_network(value) -> None:
    from kordena_fiscal.connectors.bling_api import update_sales_order_status

    with patch("kordena_fiscal.connectors.bling_api.HTTPSConnection") as connect:
        with pytest.raises(ValueError):
            update_sales_order_status(9001, value, "synthetic")
        connect.assert_not_called()


@pytest.mark.parametrize("company", ["synthetic-company", "other-company"])
def test_oauth_company_identity_is_checked_before_accessing_orders(company):
    import json

    from kordena_fiscal.connectors.bling_api import verify_company

    with patch("kordena_fiscal.connectors.bling_api.HTTPSConnection") as connect:
        connection = connect.return_value
        response = connection.getresponse.return_value
        response.status = 200
        response.read.return_value = json.dumps({"data": {"id": company}}).encode()
        if company == "synthetic-company":
            verify_company("synthetic", "synthetic-company")
        else:
            with pytest.raises(BlingApiError) as error:
                verify_company("synthetic", "synthetic-company")
            assert not error.value.retryable
        connection.request.assert_called_once_with(
            "GET",
            "/Api/v3/empresas/me/dados-basicos",
            headers={
                "Authorization": "Bearer synthetic",
                "Accept": "application/json",
                "enable-jwt": "1",
            },
        )
        connection.close.assert_called_once()
