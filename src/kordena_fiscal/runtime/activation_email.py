"""External activation-email composition for FM NFCORE.

Provider-specific transport lives at the runtime boundary. The Core remains provider-neutral
and receives only the existing PasswordResetDelivery contract.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from kordena_fiscal.application.activation_delivery import (
    ActivationEmailMessage,
    SecureActivationEmailDelivery,
)

from .config import RuntimeConfigurationError

_BREVO_ENDPOINT = "https://api.brevo.com/v3/smtp/email"
_MAX_PROVIDER_RESPONSE_BYTES = 64 * 1024


class ActivationEmailProviderError(RuntimeError):
    """External activation-email transport failed without leaking provider material."""


class BrevoActivationMessageTransport:
    """Send NFCore activation mail through Brevo's transactional HTTPS API."""

    def __init__(self, *, api_key: str, timeout_seconds: float = 10.0) -> None:
        normalized_key = api_key.strip()
        if (
            not normalized_key
            or len(normalized_key) > 4096
            or "\r" in normalized_key
            or "\n" in normalized_key
        ):
            raise RuntimeConfigurationError("activation email API key is invalid")
        if not isinstance(timeout_seconds, (int, float)) or isinstance(timeout_seconds, bool):
            raise RuntimeConfigurationError("activation email timeout must be numeric")
        timeout = float(timeout_seconds)
        if timeout <= 0 or timeout > 60:
            raise RuntimeConfigurationError(
                "activation email timeout must be > 0 and <= 60 seconds"
            )
        self._api_key = normalized_key
        self._timeout_seconds = timeout

    def send(self, message: ActivationEmailMessage) -> None:
        if not isinstance(message, ActivationEmailMessage):
            raise ActivationEmailProviderError("activation provider message is invalid")

        payload = json.dumps(
            {
                "sender": {"email": message.from_email},
                "to": [
                    {
                        "email": message.to_email,
                        # Keep open tracking anonymous for this security-sensitive email.
                        "contactPixelTrackingConsent": False,
                    }
                ],
                "subject": message.subject,
                "textContent": message.text_body,
            },
            separators=(",", ":"),
        ).encode("utf-8")
        request = Request(
            _BREVO_ENDPOINT,
            data=payload,
            method="POST",
            headers={
                "accept": "application/json",
                "api-key": self._api_key,
                "content-type": "application/json",
                "user-agent": "FM-NFCORE/1.0",
            },
        )

        try:
            with urlopen(request, timeout=self._timeout_seconds) as response:
                status = int(getattr(response, "status", 200))
                raw = response.read(_MAX_PROVIDER_RESPONSE_BYTES + 1)
        except (HTTPError, URLError, TimeoutError, OSError):
            raise ActivationEmailProviderError("activation provider request failed") from None

        if status < 200 or status >= 300 or len(raw) > _MAX_PROVIDER_RESPONSE_BYTES:
            raise ActivationEmailProviderError("activation provider request failed")

        try:
            decoded = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ActivationEmailProviderError("activation provider response is invalid") from None
        if not isinstance(decoded, dict):
            raise ActivationEmailProviderError("activation provider response is invalid")
        message_id = decoded.get("messageId")
        if not isinstance(message_id, str) or not message_id.strip():
            raise ActivationEmailProviderError("activation provider response is invalid")


def _required(values: Mapping[str, str], name: str) -> str:
    value = values.get(name, "").strip()
    if not value:
        raise RuntimeConfigurationError(f"{name} is required")
    return value


def build_activation_delivery_from_mapping(
    values: Mapping[str, str],
) -> SecureActivationEmailDelivery | None:
    """Build the external activation delivery only when a provider is explicitly selected."""

    provider = values.get("NFCORE_ACTIVATION_EMAIL_PROVIDER", "").strip().lower()
    if not provider:
        return None
    if provider != "brevo":
        raise RuntimeConfigurationError("unsupported activation email provider")

    api_key = _required(values, "NFCORE_ACTIVATION_EMAIL_API_KEY")
    sender = _required(values, "NFCORE_ACTIVATION_EMAIL_SENDER")
    activation_base_url = _required(values, "NFCORE_ACTIVATION_BASE_URL")
    timeout_raw = values.get("NFCORE_ACTIVATION_EMAIL_TIMEOUT_SECONDS", "10").strip()
    try:
        timeout = float(timeout_raw)
    except ValueError:
        raise RuntimeConfigurationError(
            "NFCORE_ACTIVATION_EMAIL_TIMEOUT_SECONDS must be numeric"
        ) from None

    transport = BrevoActivationMessageTransport(
        api_key=api_key,
        timeout_seconds=timeout,
    )
    return SecureActivationEmailDelivery(
        transport=transport,
        activation_base_url=activation_base_url,
        sender_email=sender,
    )


def build_activation_delivery_from_environ() -> SecureActivationEmailDelivery | None:
    return build_activation_delivery_from_mapping(os.environ)


__all__ = [
    "ActivationEmailProviderError",
    "BrevoActivationMessageTransport",
    "build_activation_delivery_from_environ",
    "build_activation_delivery_from_mapping",
]
