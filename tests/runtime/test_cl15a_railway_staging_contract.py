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


def _base_env() -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "NFCORE_RAILWAY_PROJECT_ID": "project-id",
            "NFCORE_RAILWAY_ENVIRONMENT_ID": "environment-id",
            "NFCORE_RAILWAY_API_SERVICE": "api",
            "NFCORE_RAILWAY_WORKER_SERVICE": "worker",
            "NFCORE_RAILWAY_PORTAL_SERVICE": "portal",
            "NFCORE_RAILWAY_POSTGRES_SERVICE": "postgres",
        }
    )
    return env


def _git_head() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()


def _fake_railway(tmp_path: Path, env: dict[str, str]) -> Path:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    railway = bin_dir / "railway"
    railway.write_text(
        """#!/bin/sh
set -eu
printf '%s\\n' "$*" >> "$RAILWAY_FAKE_LOG"
if [ "$1" = "deployment" ] && [ "$2" = "list" ]; then
  printf '%s\\n' '[{"id":"deployment-1","status":"SUCCESS"}]'
fi
exit 0
""",
        encoding="utf-8",
    )
    railway.chmod(0o755)
    env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"
    env["RAILWAY_FAKE_LOG"] = str(tmp_path / "railway.log")
    return Path(env["RAILWAY_FAKE_LOG"])


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
    env = _base_env()

    result = _run("preflight", env=env)

    assert result.returncode == 42
    assert "real execution is disabled while the repository remains public" in result.stdout


def test_railway_driver_preflight_can_be_prepared_without_exposing_secrets(
    tmp_path: Path,
) -> None:
    env = _base_env()
    env.update(
        {
            "NFCORE_RAILWAY_REAL_EXECUTION_ENABLED": "true",
            "RAILWAY_API_TOKEN": "synthetic-token",
        }
    )
    log = _fake_railway(tmp_path, env)

    result = _run("preflight", env=env)

    assert result.returncode == 0
    assert result.stdout.strip() == "railway staging driver: PREFLIGHT_READY"
    assert "link --project project-id --environment environment-id --json" in log.read_text()


def test_railway_driver_prepares_native_postgres_backup(
    tmp_path: Path,
) -> None:
    env = _base_env()
    env.update(
        {
            "NFCORE_RAILWAY_REAL_EXECUTION_ENABLED": "true",
            "RAILWAY_API_TOKEN": "synthetic-token",
        }
    )
    log = _fake_railway(tmp_path, env)
    revision = "a" * 40

    result = _run("backup", revision, env=env)

    assert result.returncode == 0
    assert f"BACKUP_REQUESTED revision={revision}" in result.stdout
    command_log = log.read_text()
    assert (
        "postgres pitr backup create --project project-id "
        "--environment environment-id --service postgres "
        "--name nfcore-pre-aaaaaaaaaaaa --json"
    ) in command_log


def test_railway_driver_prepares_immutable_three_service_deploy(
    tmp_path: Path,
) -> None:
    env = _base_env()
    env.update(
        {
            "NFCORE_RAILWAY_REAL_EXECUTION_ENABLED": "true",
            "RAILWAY_API_TOKEN": "synthetic-token",
            "NFCORE_RAILWAY_WAIT_ATTEMPTS": "1",
            "NFCORE_RAILWAY_WAIT_SECONDS": "0",
        }
    )
    log = _fake_railway(tmp_path, env)
    revision = _git_head()

    result = _run("deploy", revision, env=env)

    assert result.returncode == 0
    assert f"DEPLOY_READY revision={revision}" in result.stdout
    command_log = log.read_text()
    for service in ("api", "worker", "portal"):
        assert (
            f"up --ci --project project-id --environment environment-id "
            f"--service {service}"
        ) in command_log
        assert (
            f"deployment list --service {service} --environment environment-id "
            "--limit 1 --json"
        ) in command_log


def test_railway_driver_verify_worker_uses_terminal_success(
    tmp_path: Path,
) -> None:
    env = _base_env()
    env.update(
        {
            "NFCORE_RAILWAY_REAL_EXECUTION_ENABLED": "true",
            "RAILWAY_API_TOKEN": "synthetic-token",
            "NFCORE_RAILWAY_WAIT_ATTEMPTS": "1",
            "NFCORE_RAILWAY_WAIT_SECONDS": "0",
        }
    )
    _fake_railway(tmp_path, env)
    revision = _git_head()

    result = _run("verify-worker", revision, env=env)

    assert result.returncode == 0
    assert f"WORKER_READY revision={revision}" in result.stdout


def test_railway_driver_rollback_remains_fail_closed_until_externally_certified() -> None:
    result = _run("rollback", "0" * 40)

    assert result.returncode == 42
    assert "rollback remains pending external baseline certification" in result.stdout
