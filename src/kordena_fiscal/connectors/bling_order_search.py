"""Bounded Bling v3 order discovery, not a second fiscal intake authority.

Official Bling pagination: pagina/limite. Payload is untrusted until the
canonical installation-specific OAuth principal and full order are verified.
"""
from __future__ import annotations

import json
from http.client import HTTPException, HTTPSConnection
from typing import Any
from urllib.parse import urlencode

from .bling_api import BlingApiError

_PAGE_LIMIT = 100
_MAX_BYTES = 2_097_152


def list_sales_orders(
    page: int, limit: int, access_token: str,
) -> tuple[dict[str, Any], ...]:
    """Return bounded ID-bearing provider summaries; no tax inference."""
    if (
        type(page) is not int or page < 1 or page > 100_000
        or type(limit) is not int or not 1 <= limit <= _PAGE_LIMIT
        or not access_token or len(access_token) > 8192
        or any(not 33 <= ord(char) <= 126 for char in access_token)
    ):
        raise ValueError("invalid Bling discovery request")
    path = "/Api/v3/pedidos/vendas?" + urlencode({"pagina": page, "limite": limit})
    conn = HTTPSConnection("api.bling.com.br", timeout=10)
    try:
        conn.request(
            "GET", path,
            headers={"Authorization": "Bearer " + access_token, "Accept": "application/json"},
        )
        response = conn.getresponse()
        if response.status != 200:
            raise BlingApiError(
                response.status,
                retryable=response.status == 429 or response.status >= 500,
            )
        raw = response.read(_MAX_BYTES + 1)
    except (OSError, HTTPException) as exc:
        raise BlingApiError(None, retryable=True) from exc
    finally:
        conn.close()
    if len(raw) > _MAX_BYTES:
        raise BlingApiError(200, retryable=False)
    try:
        payload = json.loads(raw)
    except (ValueError, TypeError, RecursionError):
        raise BlingApiError(200, retryable=False) from None
    data = payload.get("data") if isinstance(payload, dict) else None
    if (
        not isinstance(data, list)
        or len(data) > limit
        or any(
            not isinstance(item, dict)
            or type(item.get("id")) is not int
            or item["id"] <= 0
            for item in data
        )
    ):
        raise BlingApiError(200, retryable=False)
    if len({item["id"] for item in data}) != len(data):
        raise BlingApiError(200, retryable=False)
    return tuple(data)
