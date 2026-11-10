"""Read current order data from the Bling v3 API."""

import json
from decimal import Decimal
from http.client import HTTPException, HTTPSConnection
from typing import Any


class BlingApiError(RuntimeError):
    """The provider did not return the requested order."""

    def __init__(self, status: int | None, *, retryable: bool) -> None:
        super().__init__("Bling order fetch failed")
        self.status = status
        self.retryable = retryable


def fetch_sales_order(order_id: int, access_token: str) -> dict[str, Any]:
    """Fetch an order with an installation-scoped OAuth token."""
    if type(order_id) is not int or order_id <= 0:
        raise ValueError("Bling order ID must be a positive integer")
    if not access_token or any(not 33 <= ord(char) <= 126 for char in access_token):
        raise ValueError("Invalid Bling OAuth token")

    connection = HTTPSConnection("api.bling.com.br", timeout=10)
    try:
        connection.request(
            "GET",
            f"/Api/v3/pedidos/vendas/{order_id}",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
                "enable-jwt": "1",
            },
        )
        response = connection.getresponse()
        if response.status != 200:
            raise BlingApiError(
                response.status,
                retryable=response.status == 429 or response.status >= 500,
            )
        body = response.read(2_097_153)
    except (OSError, HTTPException) as exc:
        raise BlingApiError(None, retryable=True) from exc
    finally:
        connection.close()

    if len(body) > 2_097_152:
        raise BlingApiError(200, retryable=False)
    try:
        payload = json.loads(body, parse_float=Decimal)
    except (ValueError, RecursionError):
        raise BlingApiError(200, retryable=False) from None
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, dict) or type(data.get("id")) is not int or data["id"] != order_id:
        raise BlingApiError(200, retryable=False)
    return data


def update_sales_order_status(order_id: int, status_id: int, access_token: str) -> None:
    """Set a configured business status through the official Bling v3 PATCH contract."""
    if any(type(value) is not int or value <= 0 for value in (order_id, status_id)):
        raise ValueError("Bling order and status IDs must be positive integers")
    if not access_token or any(not 33 <= ord(char) <= 126 for char in access_token):
        raise ValueError("Invalid Bling OAuth token")
    connection = HTTPSConnection("api.bling.com.br", timeout=10)
    try:
        connection.request(
            "PATCH",
            f"/Api/v3/pedidos/vendas/{order_id}/situacoes/{status_id}",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
                "enable-jwt": "1",
            },
        )
        response = connection.getresponse()
        if response.status != 204:
            raise BlingApiError(
                response.status,
                retryable=response.status == 429 or response.status >= 500,
            )
    except (OSError, HTTPException) as exc:
        raise BlingApiError(None, retryable=True) from exc
    finally:
        connection.close()


def verify_company(access_token: str, expected_company_id: str) -> None:
    """Bind the OAuth principal to the webhook company before accessing any order."""
    if not access_token or any(not 33 <= ord(char) <= 126 for char in access_token):
        raise ValueError("Invalid Bling OAuth token")
    connection = HTTPSConnection("api.bling.com.br", timeout=10)
    try:
        connection.request(
            "GET",
            "/Api/v3/empresas/me/dados-basicos",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
                "enable-jwt": "1",
            },
        )
        response = connection.getresponse()
        if response.status != 200:
            raise BlingApiError(
                response.status,
                retryable=response.status == 429 or response.status >= 500,
            )
        body = response.read(65_537)
    except (OSError, HTTPException) as exc:
        raise BlingApiError(None, retryable=True) from exc
    finally:
        connection.close()
    if len(body) > 65_536:
        raise BlingApiError(200, retryable=False)
    try:
        data = json.loads(body)["data"]
        company_id = data.get("id") if isinstance(data, dict) else None
        if type(company_id) not in (int, str) or str(company_id) != expected_company_id:
            raise ValueError("company mismatch")
    except (ValueError, TypeError, KeyError, RecursionError):
        raise BlingApiError(200, retryable=False) from None
