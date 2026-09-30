"""Provider-neutral secure activation delivery for FM NFCORE.

This module adapts the canonical PasswordRecoveryService reset grant to an outbound
message transport. It does not issue/reset credentials, persist raw tokens or select a
concrete email provider.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from urllib.parse import quote, urlparse

from kordena_fiscal.security.human_recovery import IssuedPasswordReset


class ActivationDeliveryError(RuntimeError):
    """Activation delivery failed without exposing provider or token details."""


@dataclass(frozen=True, slots=True, repr=False)
class ActivationEmailMessage:
    """Ephemeral outbound activation message.

    The body necessarily contains the one-time reset grant, therefore repr is always
    metadata-only and the object has no persistence/serialization boundary.
    """

    to_email: str
    from_email: str
    subject: str
    text_body: str

    def __repr__(self) -> str:
        return (
            "ActivationEmailMessage("
            f"to_email=<redacted>, from_email={self.from_email!r}, "
            f"subject={self.subject!r}, text_body=<redacted>)"
        )


class ActivationMessageTransport(Protocol):
    """Provider-specific outbound transport implemented outside the Core."""

    def send(self, message: ActivationEmailMessage) -> None: ...


class SecureActivationEmailDelivery:
    """Deliver canonical activation grants without becoming credential authority."""

    def __init__(
        self,
        *,
        transport: ActivationMessageTransport,
        activation_base_url: str,
        sender_email: str,
        product_name: str = "FM NFCORE",
    ) -> None:
        self._transport = transport
        self._activation_base_url = self._validate_base_url(activation_base_url)
        self._sender_email = self._validate_email(sender_email, "sender_email")
        normalized_product = product_name.strip()
        if not normalized_product or len(normalized_product) > 80:
            raise ValueError("product_name must be non-blank and <= 80 chars")
        self._product_name = normalized_product

    def deliver(self, *, email: str, reset: IssuedPasswordReset) -> None:
        recipient = self._validate_email(email, "email")
        if not isinstance(reset, IssuedPasswordReset):
            raise ActivationDeliveryError("activation grant is invalid")

        # The fragment is deliberately used instead of a query parameter so the raw
        # token is not sent to the web server in the initial GET request/access log.
        activation_url = (
            f"{self._activation_base_url}#token={quote(reset.reset_token, safe='')}"
        )
        message = ActivationEmailMessage(
            to_email=recipient,
            from_email=self._sender_email,
            subject=f"Ative seu acesso ao {self._product_name}",
            text_body=(
                f"Seu acesso ao {self._product_name} está pronto.\n\n"
                f"Use o link abaixo para definir sua senha:\n{activation_url}\n\n"
                f"O link expira em {reset.expires_at.isoformat()}."
            ),
        )
        try:
            self._transport.send(message)
        except Exception:
            # Provider details can contain endpoint/header/credential information.
            raise ActivationDeliveryError("activation delivery failed") from None

    @staticmethod
    def _validate_base_url(value: str) -> str:
        normalized = value.strip().rstrip("/")
        parsed = urlparse(normalized)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError(
                "activation_base_url must be an absolute HTTPS URL without credentials, "
                "query or fragment"
            )
        return normalized

    @staticmethod
    def _validate_email(value: str, field_name: str) -> str:
        normalized = value.strip().casefold()
        if (
            not normalized
            or len(normalized) > 320
            or normalized.count("@") != 1
            or normalized.startswith("@")
            or normalized.endswith("@")
            or "\r" in normalized
            or "\n" in normalized
        ):
            raise ValueError(f"{field_name} is invalid")
        return normalized


__all__ = [
    "ActivationDeliveryError",
    "ActivationEmailMessage",
    "ActivationMessageTransport",
    "SecureActivationEmailDelivery",
]
