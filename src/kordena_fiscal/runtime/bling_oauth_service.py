"""Durable OAuth state, AES-GCM token envelopes and refresh CAS for Bling.

Uses the ONE existing fiscal PostgreSQL/SQLite database; OAuth credentials
are encrypted before persistence with an externally supplied 32-byte key.
Tenant/unit scope comes exclusively from the canonical fiscal binding.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import json
import secrets
from datetime import UTC, datetime, timedelta
from typing import Protocol

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from kordena_fiscal.domain import ExecutionScope, FiscalValidationError
from kordena_fiscal.integrations.bling_contracts import BlingInstallationState
from kordena_fiscal.persistence.bling_installations import (
    BlingInstallationRepository,
    Database,
)
from kordena_fiscal.persistence.ports import PersistenceConflictError

from kordena_fiscal.connectors.bling_oauth import (
    BlingOAuthClient,
    BlingOAuthError,
    BlingTokenSet,
)


class BlingOAuthUnavailable(RuntimeError):
    """Safe error. Never attach or stringify response bodies/tokens."""

    def __init__(self, reason: str, *, retryable: bool = False) -> None:
        super().__init__(reason)
        self.retryable = retryable


class BlingCompanyVerifier(Protocol):
    def __call__(self, access_token: str, expected_company_id: str) -> None: ...


class BlingTokenCipher:
    """Encryption key is provisioned out of band, never a runtime fallback."""

    def __init__(self, key: bytes) -> None:
        if len(key) != 32:
            raise BlingOAuthUnavailable("Bling encryption key invalid")
        self._aes = AESGCM(key)

    @classmethod
    def from_base64(cls, value: str) -> BlingTokenCipher:
        try:
            key = base64.b64decode(value, validate=True)
        except (ValueError, binascii.Error):
            raise BlingOAuthUnavailable("Bling encryption key invalid") from None
        return cls(key)

    @staticmethod
    def _aad(installation_id: str, purpose: str) -> bytes:
        if len(installation_id) != 32 or purpose not in {
            "access", "refresh", "webhook",
        }:
            raise BlingOAuthUnavailable("Bling credential scope invalid")
        return f"nfcore:bling:v1:{installation_id}:{purpose}".encode()

    def seal(self, installation_id: str, purpose: str, value: str) -> str:
        if not value or len(value) > 8192:
            raise BlingOAuthUnavailable("Bling credential invalid")
        nonce = secrets.token_bytes(12)
        result = b"BLC1" + nonce + self._aes.encrypt(
            nonce, value.encode(), self._aad(installation_id, purpose),
        )
        return base64.b64encode(result).decode()

    def open(self, installation_id: str, purpose: str, value: str) -> str:
        try:
            raw = base64.b64decode(value, validate=True)
            if len(raw) < 33 or raw[:4] != b"BLC1":
                raise ValueError
            plaintext = self._aes.decrypt(
                raw[4:16], raw[16:], self._aad(installation_id, purpose),
            )
            return plaintext.decode("utf-8")
        except (ValueError, binascii.Error, InvalidTag, UnicodeDecodeError):
            raise BlingOAuthUnavailable("Bling credential integrity invalid") from None


class BlingOAuthService:
    def __init__(
        self,
        database: Database,
        installations: BlingInstallationRepository,
        cipher: BlingTokenCipher,
        client: BlingOAuthClient,
        verifier: BlingCompanyVerifier,
        *,
        required_scopes: frozenset[str],
        webhook_secret: str,
    ) -> None:
        if not webhook_secret or len(webhook_secret) < 16:
            raise BlingOAuthUnavailable("Bling webhook secret not configured")
        if not required_scopes:
            raise BlingOAuthUnavailable("Bling approved scopes missing")
        self.database = database
        self.installations = installations
        self.cipher = cipher
        self.client = client
        self.verifier = verifier
        self.required_scopes = required_scopes
        self._webhook_secret = webhook_secret

    def _scope(self, scope: ExecutionScope, installation_id: str):
        view = self.installations.get_for_scope(scope, installation_id)
        if view is None:
            raise BlingOAuthUnavailable("Bling installation unavailable")
        return view

    def begin(
        self, scope: ExecutionScope, installation_id: str, *,
        actor_id: str, session_id: str,
    ) -> str:
        self._scope(scope, installation_id)
        if not actor_id or not session_id:
            raise BlingOAuthUnavailable("Bling session required")
        state = secrets.token_hex(32)
        digest = hashlib.sha256(state.encode()).hexdigest()
        now = datetime.now(UTC)
        with self.database.connection() as connection:
            connection.execute(
                "INSERT INTO fm_bling_oauth_flows "
                "(state_sha256, installation_id, actor_id, session_id, expires_at, consumed) "
                "VALUES (?, ?, ?, ?, ?, 0)",
                (digest, installation_id, actor_id, session_id,
                 (now + timedelta(minutes=5)).isoformat()),
            )
            connection.commit()
        return self.client.authorization_url(state)

    def _consume_state(
        self, state: str, *,
        actor_id: str, session_id: str,
    ) -> str:
        if not state or len(state) != 64 or any(c not in "0123456789abcdef" for c in state):
            raise BlingOAuthUnavailable("Bling OAuth callback state invalid")
        digest = hashlib.sha256(state.encode()).hexdigest()
        with self.database.connection() as connection:
            result = connection.execute(
                "UPDATE fm_bling_oauth_flows SET consumed = 1 "
                "WHERE state_sha256 = ? AND actor_id = ? AND session_id = ? "
                "AND consumed = 0 AND expires_at > ? RETURNING installation_id",
                (digest, actor_id, session_id, datetime.now(UTC).isoformat()),
            ).fetchone()
            if result is None:
                connection.rollback()
                raise BlingOAuthUnavailable("Bling OAuth callback invalid or replayed")
            connection.commit()
        return str(result[0])

    def complete(
        self, scope: ExecutionScope, *,
        state: str, code: str, actor_id: str, session_id: str,
    ) -> None:
        installation_id = self._consume_state(
            state, actor_id=actor_id, session_id=session_id,
        )
        current = self._scope(scope, installation_id)
        try:
            tokens = self.client.exchange(code)
            self._validate_tokens(tokens)
            self.verifier(tokens.access_token, current.company_id)
        except Exception:
            raise BlingOAuthUnavailable("Bling OAuth connection unavailable") from None
        # Token and installation state are one canonical transaction, preventing
        # a failed CAS from assigning a new credential to a competing install.
        self._replace_credentials(
            installation_id, tokens, expected_revision=0,
            scope=scope, expected_installation_revision=current.revision,
        )

    def _validate_tokens(self, tokens: BlingTokenSet) -> None:
        if not self.required_scopes <= tokens.scopes:
            raise BlingOAuthUnavailable("Bling OAuth scopes are insufficient")

    def _replace_credentials(
        self, installation_id: str, tokens: BlingTokenSet, *,
        expected_revision: int,
        lease_owner: str | None = None,
        scope: ExecutionScope | None = None,
        expected_installation_revision: int | None = None,
    ) -> None:
        access = self.cipher.seal(installation_id, "access", tokens.access_token)
        refresh = self.cipher.seal(installation_id, "refresh", tokens.refresh_token)
        now = datetime.now(UTC).isoformat()
        with self.database.connection() as connection:
            if expected_revision == 0:
                if scope is None or expected_installation_revision is None:
                    raise PersistenceConflictError("Bling OAuth installation authority missing")
                changed = connection.execute(
                    "UPDATE fm_bling_installations SET state = ?, "
                    "revision = revision + 1, updated_at = ? "
                    "WHERE installation_id = ? AND tenant_id = ? AND unit_id = ? "
                    "AND environment = ? AND revision = ?",
                    (
                        BlingInstallationState.CONNECTED.value, now, installation_id,
                        scope.tenant_id, scope.unit_id, scope.environment.value,
                        expected_installation_revision,
                    ),
                )
                if changed.rowcount != 1:
                    connection.rollback()
                    raise PersistenceConflictError("Bling installation authorization changed")
                webhook = self.cipher.seal(
                    installation_id, "webhook", self._webhook_secret,
                )
                changed = connection.execute(
                    "INSERT INTO fm_bling_credentials "
                    "(installation_id, access_ciphertext, refresh_ciphertext, "
                    "webhook_secret_ciphertext, access_expires_at, refresh_expires_at, "
                    "scopes_json, token_revision, refresh_lease_owner, "
                    "refresh_lease_until, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, 1, NULL, NULL, ?) "
                    "ON CONFLICT (installation_id) DO UPDATE SET "
                    "access_ciphertext = EXCLUDED.access_ciphertext, "
                    "refresh_ciphertext = EXCLUDED.refresh_ciphertext, "
                    "webhook_secret_ciphertext = EXCLUDED.webhook_secret_ciphertext, "
                    "access_expires_at = EXCLUDED.access_expires_at, "
                    "refresh_expires_at = EXCLUDED.refresh_expires_at, "
                    "scopes_json = EXCLUDED.scopes_json, "
                    "token_revision = fm_bling_credentials.token_revision + 1, "
                    "refresh_lease_owner = NULL, refresh_lease_until = NULL, "
                    "updated_at = EXCLUDED.updated_at",
                    (
                        installation_id, access, refresh, webhook,
                        tokens.access_expires_at.isoformat(),
                        tokens.refresh_expires_at.isoformat(),
                        json.dumps(sorted(tokens.scopes)), now,
                    ),
                )
            else:
                changed = connection.execute(
                    "UPDATE fm_bling_credentials SET access_ciphertext = ?, "
                    "refresh_ciphertext = ?, access_expires_at = ?, refresh_expires_at = ?, "
                    "scopes_json = ?, token_revision = token_revision + 1, "
                    "refresh_lease_owner = NULL, refresh_lease_until = NULL, updated_at = ? "
                    "WHERE installation_id = ? AND token_revision = ? "
                    "AND refresh_lease_owner = ?",
                    (
                        access, refresh, tokens.access_expires_at.isoformat(),
                        tokens.refresh_expires_at.isoformat(),
                        json.dumps(sorted(tokens.scopes)), now,
                        installation_id, expected_revision, lease_owner,
                    ),
                )
            if changed.rowcount != 1:
                connection.rollback()
                raise PersistenceConflictError("Bling OAuth credential version conflict")
            connection.commit()

    def _mark_reauth(self, scope: ExecutionScope, installation_id: str) -> None:
        current = self._scope(scope, installation_id)
        try:
            self.installations.transition(
                scope, installation_id, expected_revision=current.revision,
                state=BlingInstallationState.NEEDS_REAUTH,
            )
        except PersistenceConflictError:
            pass

    def access_token(self, scope: ExecutionScope, installation_id: str) -> str:
        current = self._scope(scope, installation_id)
        if current.state is not BlingInstallationState.CONNECTED:
            raise BlingOAuthUnavailable("Bling installation requires authorization")
        with self.database.connection() as connection:
            row = connection.execute(
                "SELECT access_ciphertext, refresh_ciphertext, access_expires_at, "
                "refresh_expires_at, token_revision, refresh_lease_owner, "
                "refresh_lease_until FROM fm_bling_credentials "
                "WHERE installation_id = ?",
                (installation_id,),
            ).fetchone()
        if row is None:
            raise BlingOAuthUnavailable("Bling authorization missing")
        now = datetime.now(UTC)
        expiry = datetime.fromisoformat(str(row[2]))
        if expiry > now + timedelta(seconds=120):
            return self.cipher.open(installation_id, "access", str(row[0]))
        refresh_expiry = datetime.fromisoformat(str(row[3]))
        if refresh_expiry <= now:
            self._mark_reauth(scope, installation_id)
            raise BlingOAuthUnavailable("Bling authorization expired")
        # The short lease is claimed transactionally BEFORE making the provider
        # call. Concurrent workers cannot use a rotating refresh token twice.
        owner = secrets.token_hex(16)
        lease_until = (now + timedelta(seconds=30)).isoformat()
        with self.database.connection() as connection:
            updated = connection.execute(
                "UPDATE fm_bling_credentials SET refresh_lease_owner = ?, "
                "refresh_lease_until = ? WHERE installation_id = ? "
                "AND token_revision = ? AND "
                "(refresh_lease_until IS NULL OR refresh_lease_until < ?)",
                (owner, lease_until, installation_id, int(row[4]), now.isoformat()),
            )
            if updated.rowcount != 1:
                connection.rollback()
                raise BlingOAuthUnavailable("Bling token refresh already in progress", retryable=True)
            connection.commit()
        try:
            token = self.cipher.open(installation_id, "refresh", str(row[1]))
            fresh = self.client.refresh(token)
            self._validate_tokens(fresh)
            self.verifier(fresh.access_token, current.company_id)
            self._replace_credentials(
                installation_id, fresh, expected_revision=int(row[4]), lease_owner=owner,
            )
            return fresh.access_token
        except BlingOAuthError as exc:
            if exc.needs_reauth:
                self._mark_reauth(scope, installation_id)
            raise BlingOAuthUnavailable(
                "Bling refresh unavailable", retryable=exc.retryable,
            ) from None
        finally:
            with self.database.connection() as connection:
                connection.execute(
                    "UPDATE fm_bling_credentials SET refresh_lease_owner = NULL, "
                    "refresh_lease_until = NULL WHERE installation_id = ? "
                    "AND refresh_lease_owner = ?",
                    (installation_id, owner),
                )
                connection.commit()

    def revoke_local(self, scope: ExecutionScope, installation_id: str) -> None:
        """Immediately pause locally, then best-effort provider revocation.

        An upstream error retains the encrypted credentials for retry, but the
        local installation is already PAUSED and cannot dispatch any new jobs.
        """
        current = self._scope(scope, installation_id)
        if current.state is not BlingInstallationState.PAUSED:
            self.installations.transition(
                scope, installation_id, expected_revision=current.revision,
                state=BlingInstallationState.PAUSED,
            )
        with self.database.connection() as connection:
            row = connection.execute(
                "SELECT refresh_ciphertext FROM fm_bling_credentials "
                "WHERE installation_id = ?", (installation_id,),
            ).fetchone()
        if row is not None:
            try:
                token = self.cipher.open(installation_id, "refresh", str(row[0]))
                self.client.revoke(token)
            except BlingOAuthError as exc:
                raise BlingOAuthUnavailable(
                    "Bling upstream revocation pending", retryable=exc.retryable,
                ) from None
            with self.database.connection() as connection:
                connection.execute(
                    "DELETE FROM fm_bling_credentials WHERE installation_id = ?",
                    (installation_id,),
                )
                connection.commit()

    def webhook_secret(self, installation_id: str) -> bytes:
        view = self.installations.get_by_id(installation_id)
        if view is None or view.state is not BlingInstallationState.CONNECTED:
            raise BlingOAuthUnavailable("Bling webhook installation unavailable")
        with self.database.connection() as connection:
            row = connection.execute(
                "SELECT webhook_secret_ciphertext FROM fm_bling_credentials "
                "WHERE installation_id = ?",
                (installation_id,),
            ).fetchone()
        if row is None or row[0] is None:
            raise BlingOAuthUnavailable("Bling webhook secret not provisioned")
        return self.cipher.open(installation_id, "webhook", str(row[0])).encode()
