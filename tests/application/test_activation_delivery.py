from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

import pytest

from kordena_fiscal.application.activation_delivery import (
    ActivationDeliveryError,
    ActivationEmailMessage,
    SecureActivationEmailDelivery,
)
from kordena_fiscal.security.human_recovery import IssuedPasswordReset

NOW = datetime(2026, 9, 29, 23, 30, tzinfo=UTC)
TOKEN = "synthetic-reset-token-never-log"


@dataclass(slots=True)
class RecordingTransport:
    messages: list[ActivationEmailMessage] = field(default_factory=list)

    def send(self, message: ActivationEmailMessage) -> None:
        self.messages.append(message)


class FailingTransport:
    def send(self, message: ActivationEmailMessage) -> None:
        del message
        raise RuntimeError("provider endpoint api-key=secret-should-not-escape")


def _reset() -> IssuedPasswordReset:
    return IssuedPasswordReset(
        reset_token=TOKEN,
        account_id="commercial-owner-1",
        expires_at=NOW,
    )


def test_activation_delivery_builds_https_fragment_link_and_redacts_repr() -> None:
    transport = RecordingTransport()
    delivery = SecureActivationEmailDelivery(
        transport=transport,
        activation_base_url="https://nfcore.example.com/ativar",
        sender_email="ACESSO@FMTECNOLOGIA.EXAMPLE",
    )

    delivery.deliver(email="Owner@Example.com", reset=_reset())

    assert len(transport.messages) == 1
    message = transport.messages[0]
    assert message.to_email == "owner@example.com"
    assert message.from_email == "acesso@fmtecnologia.example"
    assert TOKEN not in message.text_body
    assert "Redefinir minha senha" in message.text_body
    assert "10 minutos" in message.text_body
    assert message.html_body is not None
    assert "Redefinir minha senha" in message.html_body
    assert "https://nfcore.example.com/ativar#token=" in message.html_body
    assert TOKEN in message.html_body
    assert ">https://nfcore.example.com/ativar#token=" not in message.html_body
    assert TOKEN not in repr(message)
    assert "owner@example.com" not in repr(message)


@pytest.mark.parametrize(
    "url",
    [
        "http://nfcore.example.com/ativar",
        "https://user:password@nfcore.example.com/ativar",
        "https://nfcore.example.com/ativar?token=x",
        "https://nfcore.example.com/ativar#token=x",
        "not-a-url",
    ],
)
def test_activation_delivery_rejects_unsafe_activation_base_urls(url: str) -> None:
    with pytest.raises(ValueError, match="absolute HTTPS"):
        SecureActivationEmailDelivery(
            transport=RecordingTransport(),
            activation_base_url=url,
            sender_email="acesso@fmtecnologia.example",
        )


def test_activation_delivery_rejects_header_injection_email() -> None:
    delivery = SecureActivationEmailDelivery(
        transport=RecordingTransport(),
        activation_base_url="https://nfcore.example.com/ativar",
        sender_email="acesso@fmtecnologia.example",
    )

    with pytest.raises(ValueError, match="email is invalid"):
        delivery.deliver(
            email="owner@example.com\nBcc: attacker@example.com",
            reset=_reset(),
        )


def test_activation_delivery_redacts_transport_failure_and_token() -> None:
    delivery = SecureActivationEmailDelivery(
        transport=FailingTransport(),
        activation_base_url="https://nfcore.example.com/ativar",
        sender_email="acesso@fmtecnologia.example",
    )

    with pytest.raises(ActivationDeliveryError) as caught:
        delivery.deliver(email="owner@example.com", reset=_reset())

    assert str(caught.value) == "activation delivery failed"
    assert TOKEN not in str(caught.value)
    assert "api-key" not in str(caught.value)
    assert caught.value.__cause__ is None


@pytest.mark.parametrize("minutes", [4, 31])
def test_activation_delivery_rejects_unsafe_reset_ttl(minutes: int) -> None:
    with pytest.raises(ValueError, match="between 5 and 30"):
        SecureActivationEmailDelivery(
            transport=RecordingTransport(),
            activation_base_url="https://nfcore.example.com/ativar",
            sender_email="acesso@fmtecnologia.example",
            reset_ttl_minutes=minutes,
        )
