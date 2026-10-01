from __future__ import annotations

import pytest

from scripts.admin.provision_staging_test_account import _require_staging_approval


def test_staging_test_account_command_rejects_non_staging(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("NFCORE_ENVIRONMENT", "production")
    monkeypatch.setenv("NFCORE_STAGING_TEST_ACCOUNT_APPROVED", "true")

    with pytest.raises(RuntimeError, match="restricted to staging"):
        _require_staging_approval()


def test_staging_test_account_command_requires_explicit_approval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("NFCORE_ENVIRONMENT", "staging")
    monkeypatch.delenv("NFCORE_STAGING_TEST_ACCOUNT_APPROVED", raising=False)

    with pytest.raises(RuntimeError, match="NFCORE_STAGING_TEST_ACCOUNT_APPROVED=true"):
        _require_staging_approval()


def test_staging_test_account_command_accepts_staging_with_approval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("NFCORE_ENVIRONMENT", "staging")
    monkeypatch.setenv("NFCORE_STAGING_TEST_ACCOUNT_APPROVED", "true")

    _require_staging_approval()
