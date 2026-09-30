from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DRIVER = ROOT / "scripts" / "deploy" / "drivers" / "railway.sh"


def _run(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["sh", str(DRIVER), *args],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_railway_driver_advertises_canonical_contract_and_provider() -> None:
    contract = _run("contract")
    provider = _run("provider")

    assert contract.returncode == 0
    assert contract.stdout.strip() == "nfcore-staging-driver-v1"
    assert provider.returncode == 0
    assert provider.stdout.strip() == "railway"


def test_railway_driver_fails_closed_without_external_identifiers() -> None:
    result = _run("preflight", env=os.environ.copy())

    assert result.returncode == 42
    assert "BLOCKED_EXTERNAL missing=NFCORE_RAILWAY_PROJECT_ID" in result.stdout


def test_railway_driver_refuses_real_execution_while_public_repo_guard_is_off() -> None:
    env = os.environ.copy()
    env.update(
        {
            "NFCORE_RAILWAY_PROJECT_ID": "project-id",
            "NFCORE_RAILWAY_ENVIRONMENT_ID": "environment-id",
            "NFCORE_RAILWAY_API_SERVICE": "api",
            "NFCORE_RAILWAY_WORKER_SERVICE": "worker",
            "NFCORE_RAILWAY_PORTAL_SERVICE": "portal",
        }
    )

    result = _run("preflight", env=env)

    assert result.returncode == 42
    assert "real execution is disabled while the repository remains public" in result.stdout


def test_railway_driver_real_operations_are_blocked_in_cl15a() -> None:
    for command in ("backup", "deploy", "verify-worker", "rollback"):
        result = _run(command, "0" * 40)
        assert result.returncode == 42
        assert "CL-15A certifies provider readiness only" in result.stdout
