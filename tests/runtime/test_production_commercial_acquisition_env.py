"""Production commercial-acquisition security env-based resolver: fail-closed tests."""

from __future__ import annotations

import base64
from datetime import UTC, datetime

import pytest

from kordena_fiscal.runtime import production_commercial_acquisition_env as candidate
from kordena_fiscal.runtime.config import RuntimeConfigurationError
from kordena_fiscal.security.s2s import WebhookSecurity, WebhookSignatureError

ENV_VAR = "NFCORE_PRODUCTION_COMMERCIAL_ACQUISITION_SECRET_BASE64"


def test_absent_configuration_returns_none() -> None:
    assert candidate.production_commercial_acquisition_security_from_env({}) is None


def test_valid_secret_produces_working_webhook_security() -> None:
    raw = b"x" * 32
    encoded = base64.b64encode(raw).decode("ascii")
    result = candidate.production_commercial_acquisition_security_from_env({ENV_VAR: encoded})
    assert isinstance(result, WebhookSecurity)
    now = datetime.now(UTC)
    signature = result.sign(b"synthetic-body", now=now)
    result.verify(b"synthetic-body", signature, now=now)
    with pytest.raises(WebhookSignatureError):
        result.verify(b"tampered-body", signature, now=now)


def test_invalid_base64_raises() -> None:
    with pytest.raises(RuntimeConfigurationError):
        candidate.production_commercial_acquisition_security_from_env(
            {ENV_VAR: "not-valid-base64!!"}
        )


def test_too_short_secret_raises() -> None:
    raw = b"x" * 16
    encoded = base64.b64encode(raw).decode("ascii")
    with pytest.raises(RuntimeConfigurationError):
        candidate.production_commercial_acquisition_security_from_env({ENV_VAR: encoded})


def test_defaults_to_os_environ(monkeypatch: pytest.MonkeyPatch) -> None:
    raw = b"y" * 40
    encoded = base64.b64encode(raw).decode("ascii")
    monkeypatch.setenv(ENV_VAR, encoded)
    result = candidate.production_commercial_acquisition_security_from_env()
    assert isinstance(result, WebhookSecurity)
