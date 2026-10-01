from datetime import UTC, datetime, timedelta

import pytest

from kordena_fiscal.security.human_identity import (
    HumanAccount,
    HumanAuthenticationError,
    HumanIdentityService,
    HumanRateLimitError,
    InMemoryHumanAccountRepository,
    InMemoryWebSessionRepository,
    LoginAttemptLimiter,
    PortalRole,
    ScryptPasswordHasher,
)
from kordena_fiscal.security.human_recovery import (
    InMemoryPasswordResetRepository,
    PasswordRecoveryService,
)

NOW = datetime(2026, 9, 14, 16, 50, tzinfo=UTC)
OLD_PASSWORD = "old-password-nfcore-2026"
NEW_PASSWORD = "new-password-nfcore-2026"
PASSWORD_MANAGER_PASSWORD = "G7!mQ2#vR9$kT4-xP8@cL6"


def foundation() -> tuple[
    ScryptPasswordHasher,
    InMemoryHumanAccountRepository,
    InMemoryWebSessionRepository,
]:
    hasher = ScryptPasswordHasher()
    account = HumanAccount(
        account_id="account-reset",
        email="reset@example.com",
        password_hash=hasher.hash(OLD_PASSWORD),
        tenant_id="tenant-a",
        role=PortalRole.ADMIN,
    )
    accounts = InMemoryHumanAccountRepository((account,))
    sessions = InMemoryWebSessionRepository()
    return hasher, accounts, sessions


def test_login_rate_limiter_blocks_after_configured_failures() -> None:
    hasher, accounts, sessions = foundation()
    identity = HumanIdentityService(
        accounts=accounts,
        sessions=sessions,
        password_hasher=hasher,
        login_limiter=LoginAttemptLimiter(max_failures=2, window_seconds=300),
    )

    for _ in range(2):
        with pytest.raises(HumanAuthenticationError, match="invalid email or password"):
            identity.login(
                email="reset@example.com",
                password="wrong-password-value",
                now=NOW,
            )

    with pytest.raises(HumanRateLimitError, match="too many login attempts"):
        identity.login(email="reset@example.com", password=OLD_PASSWORD, now=NOW)


def test_password_reset_is_one_time_and_invalidates_existing_sessions() -> None:
    hasher, accounts, sessions = foundation()
    identity = HumanIdentityService(
        accounts=accounts,
        sessions=sessions,
        password_hasher=hasher,
    )
    recovery = PasswordRecoveryService(
        accounts=accounts,
        sessions=sessions,
        resets=InMemoryPasswordResetRepository(),
        password_hasher=hasher,
    )
    existing = identity.login(email="reset@example.com", password=OLD_PASSWORD, now=NOW)
    reset = recovery.request_reset(email="reset@example.com", now=NOW)
    assert reset is not None
    assert reset.reset_token not in repr(reset)

    recovery.complete_reset(
        reset_token=reset.reset_token,
        new_password=NEW_PASSWORD,
        now=NOW + timedelta(minutes=1),
    )

    with pytest.raises(HumanAuthenticationError, match="web session is not usable"):
        identity.authenticate_session(
            session_token=existing.session_token,
            now=NOW + timedelta(minutes=2),
        )
    with pytest.raises(HumanAuthenticationError, match="password reset token is not usable"):
        recovery.complete_reset(
            reset_token=reset.reset_token,
            new_password=NEW_PASSWORD,
            now=NOW + timedelta(minutes=2),
        )
    with pytest.raises(HumanAuthenticationError, match="invalid email or password"):
        identity.login(
            email="reset@example.com",
            password=OLD_PASSWORD,
            now=NOW + timedelta(minutes=2),
        )

    renewed = identity.login(
        email="reset@example.com",
        password=NEW_PASSWORD,
        now=NOW + timedelta(minutes=2),
    )
    assert renewed.account.account_id == "account-reset"


def test_expired_reset_token_is_rejected() -> None:
    hasher, accounts, sessions = foundation()
    recovery = PasswordRecoveryService(
        accounts=accounts,
        sessions=sessions,
        resets=InMemoryPasswordResetRepository(),
        password_hasher=hasher,
        reset_ttl=timedelta(minutes=10),
    )
    reset = recovery.request_reset(email="reset@example.com", now=NOW)
    assert reset is not None

    with pytest.raises(HumanAuthenticationError, match="password reset token is not usable"):
        recovery.complete_reset(
            reset_token=reset.reset_token,
            new_password=NEW_PASSWORD,
            now=NOW + timedelta(minutes=10),
        )


def test_reset_request_for_unknown_account_returns_no_delivery_grant() -> None:
    hasher, accounts, sessions = foundation()
    recovery = PasswordRecoveryService(
        accounts=accounts,
        sessions=sessions,
        resets=InMemoryPasswordResetRepository(),
        password_hasher=hasher,
    )

    assert recovery.request_reset(email="missing@example.com", now=NOW) is None


def test_new_reset_invalidates_all_previous_pending_resets_for_account() -> None:
    hasher, accounts, sessions = foundation()
    recovery = PasswordRecoveryService(
        accounts=accounts,
        sessions=sessions,
        resets=InMemoryPasswordResetRepository(),
        password_hasher=hasher,
    )

    first = recovery.request_reset(email="reset@example.com", now=NOW)
    second = recovery.request_reset(
        email="reset@example.com",
        now=NOW + timedelta(minutes=1),
    )
    assert first is not None
    assert second is not None
    assert first.reset_token != second.reset_token

    with pytest.raises(HumanAuthenticationError, match="password reset token is not usable"):
        recovery.complete_reset(
            reset_token=first.reset_token,
            new_password=NEW_PASSWORD,
            now=NOW + timedelta(minutes=2),
        )

    account_id = recovery.complete_reset(
        reset_token=second.reset_token,
        new_password=NEW_PASSWORD,
        now=NOW + timedelta(minutes=2),
    )
    assert account_id == "account-reset"


def test_password_manager_generated_password_is_accepted() -> None:
    hasher, accounts, sessions = foundation()
    identity = HumanIdentityService(
        accounts=accounts,
        sessions=sessions,
        password_hasher=hasher,
    )
    recovery = PasswordRecoveryService(
        accounts=accounts,
        sessions=sessions,
        resets=InMemoryPasswordResetRepository(),
        password_hasher=hasher,
    )

    reset = recovery.request_reset(email="reset@example.com", now=NOW)
    assert reset is not None

    recovery.complete_reset(
        reset_token=reset.reset_token,
        new_password=PASSWORD_MANAGER_PASSWORD,
        now=NOW + timedelta(minutes=1),
    )

    issued = identity.login(
        email="reset@example.com",
        password=PASSWORD_MANAGER_PASSWORD,
        now=NOW + timedelta(minutes=2),
    )
    assert issued.account.account_id == "account-reset"
