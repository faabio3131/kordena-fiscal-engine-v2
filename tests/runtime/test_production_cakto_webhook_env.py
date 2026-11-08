"""Production Cakto webhook env-based secret resolver: fail-closed unit tests."""

from __future__ import annotations

import base64

import pytest

from kordena_fiscal.runtime import production_cakto_webhook_env as candidate
from kordena_fiscal.runtime.config import RuntimeConfigurationError

ENV_VAR = "NFCORE_PRODUCTION_CAKTO_WEBHOOK_SECRET_BASE64"


def test_absent_configuration_returns_none() -> None:
    assert candidate.production_cakto_webhook_secret_from_env({}) is None


def test_valid_secret_is_decoded() -> None:
    raw = b"x" * 32
    encoded = base64.b64encode(raw).decode("ascii")
    result = candidate.production_cakto_webhook_secret_from_env({ENV_VAR: encoded})
    assert result == raw


def test_invalid_base64_raises() -> None:
    with pytest.raises(RuntimeConfigurationError):
        candidate.production_cakto_webhook_secret_from_env({ENV_VAR: "not-valid-base64!!"})


def test_too_short_secret_raises() -> None:
    raw = b"x" * 16
    encoded = base64.b64encode(raw).decode("ascii")
    with pytest.raises(RuntimeConfigurationError):
        candidate.production_cakto_webhook_secret_from_env({ENV_VAR: encoded})


def test_defaults_to_os_environ(monkeypatch: pytest.MonkeyPatch) -> None:
    raw = b"y" * 40
    encoded = base64.b64encode(raw).decode("ascii")
    monkeypatch.setenv(ENV_VAR, encoded)
    assert candidate.production_cakto_webhook_secret_from_env() == raw
