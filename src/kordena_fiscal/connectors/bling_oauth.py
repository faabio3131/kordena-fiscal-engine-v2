"""Official Bling OAuth2 Authorization Code / JWT transport, fixed TLS origin.

Source: https://developer.bling.com.br/aplicativos and /migracao-jwt.
Secrets are server-side; no OAuth token or authorization code enters logs.
"""
from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from http.client import HTTPException, HTTPSConnection
from urllib.parse import urlencode

AUTHORIZE_URL = "https://www.bling.com.br/Api/v3/oauth/authorize"
_TOKEN_HOST = "api.bling.com.br"
_TOKEN_PATH = "/Api/v3/oauth/token"
_REVOKE_PATH = "/Api/v3/oauth/revoke"
_MAX_RESPONSE_BYTES = 65_536
_MAX_TOKEN_CHARS = 8_192


class BlingOAuthError(RuntimeError):
    """Generic error without provider response, credentials or URL query."""

    def __init__(self, *, retryable: bool, needs_reauth: bool = False) -> None:
        super().__init__("Bling OAuth operation unavailable")
        self.retryable = retryable
        self.needs_reauth = needs_reauth


@dataclass(frozen=True, slots=True, repr=False)
class BlingTokenSet:
    access_token: str
    refresh_token: str
    access_expires_at: datetime
    scopes: frozenset[str]
    refresh_expires_at: datetime

    def __repr__(self) -> str:
        return "BlingTokenSet(<redacted>)"


class BlingOAuthClient:
    def __init__(self, *, client_id: str, client_secret: str) -> None:
        if not client_id or not client_secret or any(
            ord(c) < 33 or ord(c) > 126 for c in client_id + client_secret
        ):
            raise ValueError("invalid Bling OAuth client configuration")
        if ":" in client_id or len(client_id) > 256 or len(client_secret) > 256:
            raise ValueError("invalid Bling OAuth client configuration")
        self._client_id = client_id
        self._client_secret = client_secret

    def authorization_url(self, state: str) -> str:
        if not state or len(state) > 256 or not state.isascii() or not state.isalnum():
            raise ValueError("invalid OAuth state")
        return AUTHORIZE_URL + "?" + urlencode({
            "response_type": "code",
            "client_id": self._client_id,
            "state": state,
        })

    @staticmethod
    def _scopes(value: object) -> frozenset[str]:
        if isinstance(value, str):
            pieces = value.replace(",", " ").split()
        elif isinstance(value, list) and all(isinstance(v, str) for v in value):
            pieces = value
        else:
            return frozenset()
        if any(not item or len(item) > 128 for item in pieces):
            raise BlingOAuthError(retryable=False, needs_reauth=True)
        return frozenset(pieces)

    def _post(self, path: str, fields: dict[str, str]) -> dict[str, object]:
        basic = base64.b64encode(
            (self._client_id + ":" + self._client_secret).encode()
        ).decode()
        connection = HTTPSConnection(_TOKEN_HOST, timeout=10)
        try:
            connection.request(
                "POST", path, body=urlencode(fields), headers={
                    "Authorization": "Basic " + basic,
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Accept": "application/json",
                    "enable-jwt": "1",
                },
            )
            response = connection.getresponse()
            data = response.read(_MAX_RESPONSE_BYTES + 1)
            if response.status != 200 or len(data) > _MAX_RESPONSE_BYTES:
                raise BlingOAuthError(
                    retryable=response.status == 429 or response.status >= 500,
                    needs_reauth=response.status in {400, 401, 403},
                )
            value = json.loads(data)
        except BlingOAuthError:
            raise
        except (OSError, HTTPException, ValueError, TypeError):
            raise BlingOAuthError(retryable=True) from None
        finally:
            connection.close()
        if not isinstance(value, dict):
            raise BlingOAuthError(retryable=False)
        return value

    @staticmethod
    def _parse(data: dict[str, object], now: datetime) -> BlingTokenSet:
        access, refresh = data.get("access_token"), data.get("refresh_token")
        kind, ttl = data.get("token_type"), data.get("expires_in")
        if (
            not isinstance(access, str)
            or not isinstance(refresh, str)
            or not access
            or not refresh
            or len(access) > _MAX_TOKEN_CHARS
            or len(refresh) > _MAX_TOKEN_CHARS
            or any(ord(c) < 33 or ord(c) > 126 for c in access + refresh)
            or kind != "Bearer"
            or type(ttl) is not int
            or not 30 <= ttl <= 86_400
        ):
            raise BlingOAuthError(retryable=False, needs_reauth=True)
        scopes = BlingOAuthClient._scopes(data.get("scope"))
        # The Bling reference documents a 30-day refresh lifespan. Treat as a
        # maximum and request reauthorization on provider invalid_grant.
        return BlingTokenSet(
            access_token=access,
            refresh_token=refresh,
            access_expires_at=now + timedelta(seconds=ttl),
            refresh_expires_at=now + timedelta(days=30),
            scopes=scopes,
        )

    def exchange(self, code: str, *, now: datetime | None = None) -> BlingTokenSet:
        if not code or len(code) > 2048 or not code.isascii():
            raise BlingOAuthError(retryable=False, needs_reauth=True)
        data = self._post(_TOKEN_PATH, {"grant_type": "authorization_code", "code": code})
        return self._parse(data, datetime.now(UTC) if now is None else now)

    def refresh(self, refresh_token: str, *, now: datetime | None = None) -> BlingTokenSet:
        if not refresh_token or len(refresh_token) > _MAX_TOKEN_CHARS:
            raise BlingOAuthError(retryable=False, needs_reauth=True)
        data = self._post(
            _TOKEN_PATH, {"grant_type": "refresh_token", "refresh_token": refresh_token},
        )
        return self._parse(data, datetime.now(UTC) if now is None else now)

    def revoke(self, token: str) -> None:
        if not token or len(token) > _MAX_TOKEN_CHARS:
            raise BlingOAuthError(retryable=False)
        # Revocation can return 200 or 204; no token contents in response/log.
        basic = base64.b64encode(
            (self._client_id + ":" + self._client_secret).encode()
        ).decode()
        connection = HTTPSConnection(_TOKEN_HOST, timeout=10)
        try:
            connection.request(
                "POST", _REVOKE_PATH, body=urlencode({"token": token}), headers={
                    "Authorization": "Basic " + basic,
                    "Content-Type": "application/x-www-form-urlencoded",
                    "enable-jwt": "1",
                },
            )
            response = connection.getresponse()
            response.read(_MAX_RESPONSE_BYTES + 1)
            if response.status not in (200, 204):
                raise BlingOAuthError(retryable=response.status == 429 or response.status >= 500)
        except BlingOAuthError:
            raise
        except (OSError, HTTPException):
            raise BlingOAuthError(retryable=True) from None
        finally:
            connection.close()
