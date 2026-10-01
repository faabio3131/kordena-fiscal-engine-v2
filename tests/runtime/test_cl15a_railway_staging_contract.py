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


def _fake_railway(
    tmp_path: Path,
    env: dict[str, str],
    *,
    deployment_status: str = "SUCCESS",
) -> Path:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    railway = bin_dir / "railway"
    railway.write_text(
        f"""#!/bin/sh
set -eu
printf '%s\\n' "$*" >> "$RAILWAY_FAKE_LOG"
if [ "$1" = "deployment" ] && [ "$2" = "list" ]; then
  printf '%s\\n' '[{{"id":"deployment-1","status":"{deployment_status}"}}]'
fi
exit 0
""",
        encoding="utf-8",
    )
    railway.chmod(0o755)
    env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"
    env["RAILWAY_FAKE_LOG"] = str(tmp_path / "railway.log")
    return Path(env["RAILWAY_FAKE_LOG"])


def _fake_rollback_helper(tmp_path: Path, env: dict[str, str]) -> Path:
    helper = tmp_path / "railway_graphql_fake.py"
    helper.write_text(
        """from __future__ import annotations

import os
import sys

with open(os.environ["RAILWAY_GRAPHQL_FAKE_LOG"], "a", encoding="utf-8") as handle:
    handle.write(" ".join(sys.argv[1:]) + "\\n")
print("railway graphql: ROLLBACK_REQUESTED deployment=fake status=QUEUED")
""",
        encoding="utf-8",
    )
    env["NFCORE_RAILWAY_GRAPHQL_HELPER"] = str(helper)
    env["RAILWAY_GRAPHQL_FAKE_LOG"] = str(tmp_path / "graphql.log")
    return Path(env["RAILWAY_GRAPHQL_FAKE_LOG"])


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


def test_railway_driver_refuses_real_execution_without_governance_enablement() -> None:
    env = _base_env()

    result = _run("preflight", env=env)

    assert result.returncode == 42
    assert "real execution is disabled by the governance flag" in result.stdout


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
            "NFCORE_RAILWAY_ROLLBACK_BASELINE_FILE": str(tmp_path / "baseline.tsv"),
        }
    )
    log = _fake_railway(tmp_path, env)
    revision = _git_head()

    result = _run("deploy", revision, env=env)

    assert result.returncode == 0
    assert "ROLLBACK_BASELINE_CAPTURED" in result.stdout
    assert f"DEPLOY_READY revision={revision}" in result.stdout
    baseline = Path(env["NFCORE_RAILWAY_ROLLBACK_BASELINE_FILE"]).read_text()
    for service in ("api", "worker", "portal"):
        assert f"{service}\tdeployment-1" in baseline
    command_log = log.read_text()
    for service in ("api", "worker", "portal"):
        assert (
            f"deployment list --service {service} --environment environment-id "
            "--limit 20 --json"
        ) in command_log
        assert (
            f"up --ci --project project-id --environment environment-id "
            f"--service {service}"
        ) in command_log
        assert (
            f"deployment list --service {service} --environment environment-id "
            "--limit 1 --json"
        ) in command_log


def test_railway_driver_refuses_deploy_without_successful_rollback_baseline(
    tmp_path: Path,
) -> None:
    env = _base_env()
    env.update(
        {
            "NFCORE_RAILWAY_REAL_EXECUTION_ENABLED": "true",
            "RAILWAY_API_TOKEN": "synthetic-token",
            "NFCORE_RAILWAY_ROLLBACK_BASELINE_FILE": str(tmp_path / "baseline.tsv"),
        }
    )
    log = _fake_railway(tmp_path, env, deployment_status="CRASHED")

    result = _run("deploy", _git_head(), env=env)

    assert result.returncode == 1
    assert "has no successful rollback baseline" in result.stdout
    assert "up --ci" not in log.read_text()


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


def test_railway_driver_rolls_back_to_captured_deployments(
    tmp_path: Path,
) -> None:
    env = _base_env()
    env.update(
        {
            "NFCORE_RAILWAY_REAL_EXECUTION_ENABLED": "true",
            "RAILWAY_API_TOKEN": "synthetic-token",
            "NFCORE_RAILWAY_WAIT_ATTEMPTS": "1",
            "NFCORE_RAILWAY_WAIT_SECONDS": "0",
            "NFCORE_RAILWAY_ROLLBACK_BASELINE_FILE": str(tmp_path / "baseline.tsv"),
        }
    )
    _fake_railway(tmp_path, env)
    graphql_log = _fake_rollback_helper(tmp_path, env)
    Path(env["NFCORE_RAILWAY_ROLLBACK_BASELINE_FILE"]).write_text(
        "api\tapi-deployment\n"
        "worker\tworker-deployment\n"
        "portal\tportal-deployment\n",
        encoding="utf-8",
    )
    revision = "0" * 40

    result = _run("rollback", revision, env=env)

    assert result.returncode == 0
    assert f"ROLLBACK_READY failed_revision={revision}" in result.stdout
    requests = graphql_log.read_text().splitlines()
    assert requests == [
        "rollback api-deployment",
        "rollback worker-deployment",
        "rollback portal-deployment",
    ]
