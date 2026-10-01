from __future__ import annotations

import json
from typing import Any
from urllib.error import URLError

import pytest
from fastapi.testclient import TestClient

from kordena_fiscal.application.activation_delivery import ActivationEmailMessage
from kordena_fiscal.runtime.activation_email import (
    ActivationEmailProviderError,
    BrevoActivationMessageTransport,
    build_activation_delivery_from_mapping,
)
from kordena_fiscal.runtime.api import create_runtime_app
from kordena_fiscal.runtime.config import RuntimeConfigurationError, RuntimeSettings


class _Response:
    status = 201

    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self, _limit: int = -1) -> bytes:
        return json.dumps(self._payload).encode("utf-8")


def _mapping() -> dict[str, str]:
    return {
        "NFCORE_ACTIVATION_EMAIL_PROVIDER": "brevo",
        "NFCORE_ACTIVATION_EMAIL_API_KEY": "xkeysib-synthetic-secret",
        "NFCORE_ACTIVATION_EMAIL_SENDER": "acesso@nfcore.example",
        "NFCORE_ACTIVATION_BASE_URL": "https://portal.nfcore.example/",
        "NFCORE_ACTIVATION_EMAIL_TIMEOUT_SECONDS": "7",
    }


def test_brevo_transport_posts_transactional_email_without_logging_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def fake_urlopen(request: Any, timeout: float) -> _Response:
        captured["url"] = request.full_url
        captured["headers"] = {
            key.lower(): value for key, value in request.header_items()
        }
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        captured["timeout"] = timeout
        return _Response({"messageId": "<synthetic@brevo>"})

    monkeypatch.setattr(
        "kordena_fiscal.runtime.activation_email.urlopen",
        fake_urlopen,
    )
    transport = BrevoActivationMessageTransport(
        api_key="xkeysib-synthetic-secret",
        timeout_seconds=7,
    )
    message = ActivationEmailMessage(
        to_email="owner@example.com",
        from_email="acesso@nfcore.example",
        subject="Ative seu acesso ao FM NFCORE",
        text_body="https://portal.nfcore.example/#token=synthetic",
    )

    transport.send(message)

    assert captured["url"] == "https://api.brevo.com/v3/smtp/email"
    assert captured["timeout"] == 7
    headers = captured["headers"]
    assert headers["api-key"] == "xkeysib-synthetic-secret"
    payload = captured["payload"]
    assert payload["sender"] == {"email": "acesso@nfcore.example"}
    assert payload["to"] == [
        {
            "email": "owner@example.com",
            "contactPixelTrackingConsent": False,
        }
    ]
    assert payload["subject"] == "Ative seu acesso ao FM NFCORE"
    assert "#token=synthetic" in payload["textContent"]


def test_brevo_transport_redacts_provider_network_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "xkeysib-secret-never-escape"

    def fail_urlopen(_request: Any, timeout: float) -> _Response:
        assert timeout == 10
        raise URLError(f"provider rejected api-key={secret}")

    monkeypatch.setattr(
        "kordena_fiscal.runtime.activation_email.urlopen",
        fail_urlopen,
    )
    transport = BrevoActivationMessageTransport(api_key=secret)

    with pytest.raises(ActivationEmailProviderError) as caught:
        transport.send(
            ActivationEmailMessage(
                to_email="owner@example.com",
                from_email="acesso@nfcore.example",
                subject="Ative seu acesso",
                text_body="activation body",
            )
        )

    assert str(caught.value) == "activation provider request failed"
    assert secret not in str(caught.value)
    assert caught.value.__cause__ is None


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("NFCORE_ACTIVATION_EMAIL_PROVIDER", "unknown", "unsupported activation"),
        ("NFCORE_ACTIVATION_EMAIL_API_KEY", "", "API_KEY is required"),
        ("NFCORE_ACTIVATION_EMAIL_TIMEOUT_SECONDS", "not-a-number", "must be numeric"),
    ],
)
def test_activation_delivery_configuration_fails_closed(
    field: str,
    value: str,
    match: str,
) -> None:
    values = _mapping()
    values[field] = value

    with pytest.raises(RuntimeConfigurationError, match=match):
        build_activation_delivery_from_mapping(values)


def test_activation_delivery_is_absent_until_provider_is_explicitly_selected() -> None:
    assert build_activation_delivery_from_mapping({}) is None


def test_runtime_profile_reports_injected_activation_delivery() -> None:
    delivery = build_activation_delivery_from_mapping(_mapping())
    assert delivery is not None
    settings = RuntimeSettings.from_mapping({})

    client = TestClient(
        create_runtime_app(
            settings,
            password_reset_delivery=delivery,
        )
    )

    profile = client.get("/runtime/profile").json()
    assert profile["password_reset_delivery_configured"] is True
    assert profile["commercial_activation_delivery_configured"] is False
