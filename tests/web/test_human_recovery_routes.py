from datetime import UTC, datetime

from fastapi.testclient import TestClient

from kordena_fiscal.security.human_identity import (
    HumanAccount,
    InMemoryHumanAccountRepository,
    InMemoryWebSessionRepository,
    PortalRole,
    ScryptPasswordHasher,
)
from kordena_fiscal.security.human_recovery import (
    InMemoryPasswordResetRepository,
    IssuedPasswordReset,
    PasswordRecoveryService,
)
from kordena_fiscal.web import create_app

NOW = datetime(2026, 9, 28, 5, 30, tzinfo=UTC)


class CaptureDelivery:
    def __init__(self) -> None:
        self.reset: IssuedPasswordReset | None = None

    def deliver(self, *, email: str, reset: IssuedPasswordReset) -> None:
        assert email == "owner@example.com"
        self.reset = reset


def test_password_reset_completion_notifies_commercial_activation_without_exposing_token() -> None:
    hasher = ScryptPasswordHasher()
    accounts = InMemoryHumanAccountRepository(
        (
            HumanAccount(
                account_id="commercial-owner",
                email="owner@example.com",
                password_hash=hasher.hash("temporary-commercial-password-2026"),
                tenant_id="tenant-commercial",
                role=PortalRole.OWNER,
            ),
        )
    )
    recovery = PasswordRecoveryService(
        accounts=accounts,
        sessions=InMemoryWebSessionRepository(),
        resets=InMemoryPasswordResetRepository(),
        password_hasher=hasher,
    )
    delivery = CaptureDelivery()
    callbacks: list[tuple[str, datetime]] = []
    web = TestClient(
        create_app(
            password_recovery=recovery,
            password_reset_delivery=delivery,
            password_reset_completed=lambda account_id, instant: callbacks.append(
                (account_id, instant)
            ),
        ),
        base_url="https://nfcore.test",
    )

    requested = web.post(
        "/v1/auth/password-reset/request",
        json={"email": "owner@example.com"},
    )
    assert requested.status_code == 202
    assert requested.json() == {"status": "accepted"}
    assert delivery.reset is not None
    assert delivery.reset.reset_token not in requested.text

    completed = web.post(
        "/v1/auth/password-reset/complete",
        json={
            "reset_token": delivery.reset.reset_token,
            "new_password": "activated-commercial-password-2026",
        },
    )
    assert completed.status_code == 204
    assert callbacks
    assert callbacks[0][0] == "commercial-owner"
    assert callbacks[0][1].tzinfo is not None


def test_password_reset_remains_successful_when_commercial_callback_is_temporarily_unavailable() -> None:
    hasher = ScryptPasswordHasher()
    accounts = InMemoryHumanAccountRepository(
        (
            HumanAccount(
                account_id="commercial-owner",
                email="owner@example.com",
                password_hash=hasher.hash("temporary-commercial-password-2026"),
                tenant_id="tenant-commercial",
                role=PortalRole.OWNER,
            ),
        )
    )
    recovery = PasswordRecoveryService(
        accounts=accounts,
        sessions=InMemoryWebSessionRepository(),
        resets=InMemoryPasswordResetRepository(),
        password_hasher=hasher,
    )
    delivery = CaptureDelivery()

    def fail(_account_id: str, _instant: datetime) -> None:
        raise RuntimeError("synthetic commercial-state outage")

    web = TestClient(
        create_app(
            password_recovery=recovery,
            password_reset_delivery=delivery,
            password_reset_completed=fail,
        ),
        base_url="https://nfcore.test",
    )
    assert web.post(
        "/v1/auth/password-reset/request",
        json={"email": "owner@example.com"},
    ).status_code == 202
    assert delivery.reset is not None

    response = web.post(
        "/v1/auth/password-reset/complete",
        json={
            "reset_token": delivery.reset.reset_token,
            "new_password": "activated-commercial-password-2026",
        },
    )
    assert response.status_code == 204
