"""Provider-neutral secure activation delivery for FM NFCORE.

This module adapts the canonical PasswordRecoveryService reset grant to an outbound
message transport. It does not issue/reset credentials, persist raw tokens or select a
concrete email provider.
"""

from __future__ import annotations

from dataclasses import dataclass
from html import escape
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
    html_body: str | None = None

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
        reset_ttl_minutes: int = 10,
    ) -> None:
        self._transport = transport
        self._activation_base_url = self._validate_base_url(activation_base_url)
        self._sender_email = self._validate_email(sender_email, "sender_email")
        normalized_product = product_name.strip()
        if not normalized_product or len(normalized_product) > 80:
            raise ValueError("product_name must be non-blank and <= 80 chars")
        if (
            not isinstance(reset_ttl_minutes, int)
            or isinstance(reset_ttl_minutes, bool)
            or reset_ttl_minutes < 5
            or reset_ttl_minutes > 30
        ):
            raise ValueError("reset_ttl_minutes must be between 5 and 30")
        self._product_name = normalized_product
        self._reset_ttl_minutes = reset_ttl_minutes

    def deliver(self, *, email: str, reset: IssuedPasswordReset) -> None:
        recipient = self._validate_email(email, "email")
        if not isinstance(reset, IssuedPasswordReset):
            raise ActivationDeliveryError("activation grant is invalid")

        # The fragment is deliberately used instead of a query parameter so the raw
        # token is not sent to the web server in the initial GET request/access log.
        activation_url = (
            f"{self._activation_base_url}#token={quote(reset.reset_token, safe='')}"
        )
        safe_product = escape(self._product_name)
        safe_activation_url = escape(activation_url, quote=True)
        message = ActivationEmailMessage(
            to_email=recipient,
            from_email=self._sender_email,
            subject=f"Ative seu acesso ao {self._product_name}",
            text_body=(
                f"Seu acesso ao {self._product_name} está pronto.\n\n"
                "Para definir uma nova senha, abra este e-mail em um cliente com suporte "
                "a HTML e use o botão Redefinir minha senha.\n\n"
                f"Por segurança, o acesso é válido por {self._reset_ttl_minutes} minutos "
                "e só pode ser usado uma vez.\n\n"
                "Se você não solicitou esta redefinição, ignore esta mensagem."
            ),
            html_body=(
                '<!doctype html><html lang="pt-BR"><body '
                'style="margin:0;padding:0;background:#07111f;font-family:Arial,sans-serif;'
                'color:#eaf4ff;">'
                '<table role="presentation" width="100%" cellspacing="0" cellpadding="0" '
                'style="background:#07111f;padding:32px 16px;"><tr><td align="center">'
                '<table role="presentation" width="100%" cellspacing="0" cellpadding="0" '
                'style="max-width:560px;background:#0b1b30;border:1px solid #173a63;'
                'border-radius:18px;padding:32px;">'
                f'<tr><td style="font-size:13px;letter-spacing:1.4px;color:#88a8c8;'
                f'font-weight:700;">{safe_product} · ACESSO SEGURO</td></tr>'
                f'<tr><td style="padding-top:14px;font-size:28px;line-height:1.2;'
                f'font-weight:700;color:#ffffff;">Redefina sua senha</td></tr>'
                f'<tr><td style="padding-top:16px;font-size:16px;line-height:1.6;'
                f'color:#c7d8ea;">Seu acesso ao {safe_product} está pronto. '
                'Use o botão abaixo para criar uma nova senha.</td></tr>'
                '<tr><td align="center" style="padding:28px 0;">'
                f'<a href="{safe_activation_url}" '
                'style="display:inline-block;background:#2f6dff;color:#ffffff;'
                'text-decoration:none;font-weight:700;font-size:16px;'
                'padding:15px 26px;border-radius:10px;">Redefinir minha senha</a>'
                '</td></tr>'
                f'<tr><td style="font-size:14px;line-height:1.6;color:#9fb6cc;">'
                f'Por segurança, este acesso é válido por {self._reset_ttl_minutes} minutos '
                'e só pode ser usado uma vez.</td></tr>'
                '<tr><td style="padding-top:12px;font-size:13px;line-height:1.6;'
                'color:#7f9bb7;">Se você não solicitou esta redefinição, ignore esta '
                'mensagem.</td></tr>'
                '</table></td></tr></table></body></html>'
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
