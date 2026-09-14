from datetime import UTC, datetime, timedelta

import pytest

from kordena_fiscal.security.human_identity import (
    CsrfValidationError,
    HumanAccount,
    HumanAuthenticationError,
    HumanAuthorizationError,
    HumanIdentityService,
    InMemoryHumanAccountRepository,
    InMemoryWebSessionRepository,
    PortalPermission,
    PortalRole,
    ScryptPasswordHasher,
)

NOW = datetime(2026, 9, 14, 16, 40, tzinfo=UTC)
PASSWORD = "correct-horse-nfcore-2026"


def build_identity(
    *,
    role: PortalRole = PortalRole.OPERATOR,
    units: frozenset[str] | None = frozenset({"unit-a"}),
) -> tuple[HumanIdentityService, InMemoryHumanAccountRepository, InMemoryWebSessionRepository]:
    hasher = ScryptPasswordHasher()
    account = HumanAccount(
        account_id="account-1",
        email="operator@example.com",
        password_hash=hasher.hash(PASSWORD),
        tenant_id="tenant-a",
        role=role,
        unit_ids=units,
    )
    accounts = InMemoryHumanAccountRepository((account,))
    sessions = InMemoryWebSessionRepository()
    identity = HumanIdentityService(
        accounts=accounts,
        sessions=sessions,
        password_hasher=hasher,
        session_ttl=timedelta(hours=8),
    )
    return identity, accounts, sessions


def test_scrypt_hash_is_salted_and_never_contains_raw_password() -> None:
    hasher = ScryptPasswordHasher()

    first = hasher.hash(PASSWORD)
    second = hasher.hash(PASSWORD)

    assert first != second
    assert PASSWORD not in first
    assert first.startswith("scrypt$")
    assert hasher.verify(PASSWORD, first)
    assert not hasher.verify("wrong-password-value", first)


def test_login_uses_generic_error_for_unknown_account_and_wrong_password() -> None:
    identity, _, _ = build_identity()

    with pytest.raises(HumanAuthenticationError, match="invalid email or password"):
        identity.login(email="missing@example.com", password=PASSWORD, now=NOW)
    with pytest.raises(HumanAuthenticationError, match="invalid email or password"):
        identity.login(email="operator@example.com", password="wrong-password-value", now=NOW)


def test_raw_session_and_csrf_tokens_are_not_stored() -> None:
    identity, _, sessions = build_identity()

    issued = identity.login(email="operator@example.com", password=PASSWORD, now=NOW)
    authenticated = identity.authenticate_session(session_token=issued.session_token, now=NOW)
    stored = sessions.by_token_digest(
        __import__("hashlib").sha256(issued.session_token.encode("utf-8")).hexdigest()
    )

    assert stored is not None
    assert issued.session_token not in repr(stored)
    assert issued.csrf_token not in repr(stored)
    assert issued.session_token not in repr(issued)
    assert issued.csrf_token not in repr(issued)
    assert authenticated.account.account_id == "account-1"


def test_session_expiry_and_logout_are_fail_closed() -> None:
    identity, _, _ = build_identity()
    issued = identity.login(email="operator@example.com", password=PASSWORD, now=NOW)
    authenticated = identity.authenticate_session(session_token=issued.session_token, now=NOW)

    identity.logout(authenticated)
    with pytest.raises(HumanAuthenticationError, match="web session is not usable"):
        identity.authenticate_session(session_token=issued.session_token, now=NOW)

    second = identity.login(email="operator@example.com", password=PASSWORD, now=NOW)
    with pytest.raises(HumanAuthenticationError, match="web session is not usable"):
        identity.authenticate_session(
            session_token=second.session_token,
            now=NOW + timedelta(hours=8),
        )


def test_revoke_all_sessions_invalidates_existing_tokens_by_epoch() -> None:
    identity, _, _ = build_identity()
    first = identity.login(email="operator@example.com", password=PASSWORD, now=NOW)
    second = identity.login(email="operator@example.com", password=PASSWORD, now=NOW)

    identity.revoke_all_sessions("account-1")

    for token in (first.session_token, second.session_token):
        with pytest.raises(HumanAuthenticationError, match="web session is not usable"):
            identity.authenticate_session(session_token=token, now=NOW)


def test_csrf_token_is_bound_to_session() -> None:
    identity, _, _ = build_identity()
    issued = identity.login(email="operator@example.com", password=PASSWORD, now=NOW)
    authenticated = identity.authenticate_session(session_token=issued.session_token, now=NOW)

    identity.assert_csrf(authenticated, issued.csrf_token)
    with pytest.raises(CsrfValidationError, match="invalid CSRF token"):
        identity.assert_csrf(authenticated, "different-csrf-token")


def test_operator_cannot_escalate_to_billing_or_another_unit() -> None:
    identity, _, _ = build_identity(role=PortalRole.OPERATOR)
    issued = identity.login(email="operator@example.com", password=PASSWORD, now=NOW)
    authenticated = identity.authenticate_session(session_token=issued.session_token, now=NOW)

    authenticated.assert_permission(PortalPermission.DOCUMENT_ISSUE, unit_id="unit-a")
    with pytest.raises(HumanAuthorizationError):
        authenticated.assert_permission(PortalPermission.BILLING_MANAGE, unit_id="unit-a")
    with pytest.raises(HumanAuthorizationError):
        authenticated.assert_permission(PortalPermission.DOCUMENT_QUERY, unit_id="unit-b")


def test_owner_has_all_declared_permissions_but_still_respects_unit_scope() -> None:
    identity, _, _ = build_identity(role=PortalRole.OWNER)
    issued = identity.login(email="operator@example.com", password=PASSWORD, now=NOW)
    authenticated = identity.authenticate_session(session_token=issued.session_token, now=NOW)

    assert authenticated.permissions == frozenset(PortalPermission)
    for permission in PortalPermission:
        authenticated.assert_permission(permission, unit_id="unit-a")
    with pytest.raises(HumanAuthorizationError):
        authenticated.assert_permission(PortalPermission.USER_MANAGE, unit_id="unit-b")
