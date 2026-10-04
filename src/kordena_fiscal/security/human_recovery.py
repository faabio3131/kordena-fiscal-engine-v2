"""One-time password recovery primitives for FM NFCORE human accounts."""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from threading import Lock
from typing import Protocol, runtime_checkable

from kordena_fiscal.security.human_identity import (
    HumanAccountRepository,
    HumanAuthenticationError,
    ScryptPasswordHasher,
    WebSessionRepository,
)


def _aware(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value


def _digest(token: str) -> str:
    normalized = token.strip()
    if not normalized or len(normalized) > 4096:
        raise HumanAuthenticationError("password reset token is not usable")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class PasswordResetRecord:
    reset_id: str
    account_id: str
    token_sha256: str
    created_at: datetime
    expires_at: datetime
    used: bool = False

    def __post_init__(self) -> None:
        if not self.reset_id.strip() or not self.account_id.strip():
            raise ValueError("reset_id and account_id are required")
        if len(self.token_sha256) != 64:
            raise ValueError("token_sha256 must be SHA-256 hex")
        try:
            int(self.token_sha256, 16)
        except ValueError as exc:
            raise ValueError("token_sha256 must be hexadecimal") from exc
        _aware(self.created_at, "created_at")
        _aware(self.expires_at, "expires_at")
        if self.expires_at <= self.created_at:
            raise ValueError("expires_at must be after created_at")


@runtime_checkable
class PasswordResetRepository(Protocol):
    def by_token_digest(self, token_sha256: str) -> PasswordResetRecord | None: ...

    def save(self, record: PasswordResetRecord) -> None: ...

    def mark_used(self, reset_id: str) -> None: ...

    def invalidate_account(self, account_id: str) -> None: ...


class InMemoryPasswordResetRepository:
    """Thread-safe reference store; durable implementation belongs to WP-WEB-03."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._by_id: dict[str, PasswordResetRecord] = {}
        self._token_to_id: dict[str, str] = {}

    def by_token_digest(self, token_sha256: str) -> PasswordResetRecord | None:
        with self._lock:
            reset_id = self._token_to_id.get(token_sha256)
            return self._by_id.get(reset_id) if reset_id is not None else None

    def save(self, record: PasswordResetRecord) -> None:
        if not isinstance(record, PasswordResetRecord):
            raise ValueError("record must be PasswordResetRecord")
        with self._lock:
            self._by_id[record.reset_id] = record
            self._token_to_id[record.token_sha256] = record.reset_id

    def mark_used(self, reset_id: str) -> None:
        with self._lock:
            record = self._by_id.get(reset_id)
            if record is not None and not record.used:
                self._by_id[reset_id] = replace(record, used=True)

    def invalidate_account(self, account_id: str) -> None:
        normalized = account_id.strip()
        with self._lock:
            for reset_id, record in tuple(self._by_id.items()):
                if record.account_id == normalized and not record.used:
                    self._by_id[reset_id] = replace(record, used=True)


@dataclass(frozen=True, slots=True)
class IssuedPasswordReset:
    reset_token: str
    account_id: str
    expires_at: datetime

    def __repr__(self) -> str:
        return (
            "IssuedPasswordReset(reset_token=<redacted>, "
            f"account_id={self.account_id!r}, expires_at={self.expires_at!r})"
        )


class PasswordRecoveryService:
    """Issue hashed one-time reset grants and revoke sessions after password change."""

    def __init__(
        self,
        *,
        accounts: HumanAccountRepository,
        sessions: WebSessionRepository,
        resets: PasswordResetRepository,
        password_hasher: ScryptPasswordHasher,
        reset_ttl: timedelta = timedelta(minutes=10),
    ) -> None:
        if not isinstance(accounts, HumanAccountRepository):
            raise ValueError("accounts must implement HumanAccountRepository")
        if not isinstance(sessions, WebSessionRepository):
            raise ValueError("sessions must implement WebSessionRepository")
        if not isinstance(resets, PasswordResetRepository):
            raise ValueError("resets must implement PasswordResetRepository")
        if reset_ttl < timedelta(minutes=5) or reset_ttl > timedelta(minutes=30):
            raise ValueError("reset_ttl must be between 5 and 30 minutes")
        self._accounts = accounts
        self._sessions = sessions
        self._resets = resets
        self._password_hasher = password_hasher
        self._reset_ttl = reset_ttl

    def request_reset(self, *, email: str, now: datetime) -> IssuedPasswordReset | None:
        """Return a delivery grant only for an eligible account.

        HTTP/email adapters must still answer generically so account existence is
        never disclosed to an unauthenticated caller.
        """

        _aware(now, "now")
        account = self._accounts.by_email(email.strip().casefold())
        if account is None or not account.enabled:
            return None
        self._resets.invalidate_account(account.account_id)
        token = secrets.token_urlsafe(48)
        expires_at = now + self._reset_ttl
        record = PasswordResetRecord(
            reset_id=secrets.token_urlsafe(24),
            account_id=account.account_id,
            token_sha256=_digest(token),
            created_at=now,
            expires_at=expires_at,
        )
        self._resets.save(record)
        return IssuedPasswordReset(
            reset_token=token,
            account_id=account.account_id,
            expires_at=expires_at,
        )

    def complete_reset(
        self,
        *,
        reset_token: str,
        new_password: str,
        now: datetime,
    ) -> str:
        _aware(now, "now")
        record = self._resets.by_token_digest(_digest(reset_token))
        if record is None or record.used or now >= record.expires_at:
            raise HumanAuthenticationError("password reset token is not usable")
        account = self._accounts.by_id(record.account_id)
        if account is None or not account.enabled:
            raise HumanAuthenticationError("password reset token is not usable")

        new_hash = self._password_hasher.hash(new_password)
        updated = replace(
            account,
            password_hash=new_hash,
            session_epoch=account.session_epoch + 1,
        )
        self._accounts.save(updated)
        self._sessions.revoke_account(account.account_id)
        self._resets.mark_used(record.reset_id)
        return account.account_id
