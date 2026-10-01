from __future__ import annotations

import importlib.util
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest


def _load_approval_guard() -> Callable[[], None]:
    script_path = (
        Path(__file__).resolve().parents[2]
        / "scripts"
        / "admin"
        / "provision_staging_test_account.py"
    )
    spec = importlib.util.spec_from_file_location(
        "nfcore_staging_test_account_command",
        script_path,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load staging test account command")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return cast(Callable[[], None], getattr(module, "_require_staging_approval"))


def test_staging_test_account_command_rejects_non_staging(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("NFCORE_ENVIRONMENT", "production")
    monkeypatch.setenv("NFCORE_STAGING_TEST_ACCOUNT_APPROVED", "true")

    with pytest.raises(RuntimeError, match="restricted to staging"):
        _load_approval_guard()()


def test_staging_test_account_command_requires_explicit_approval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("NFCORE_ENVIRONMENT", "staging")
    monkeypatch.delenv("NFCORE_STAGING_TEST_ACCOUNT_APPROVED", raising=False)

    with pytest.raises(RuntimeError, match="NFCORE_STAGING_TEST_ACCOUNT_APPROVED=true"):
        _load_approval_guard()()


def test_staging_test_account_command_accepts_staging_with_approval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("NFCORE_ENVIRONMENT", "staging")
    monkeypatch.setenv("NFCORE_STAGING_TEST_ACCOUNT_APPROVED", "true")

    _load_approval_guard()()
