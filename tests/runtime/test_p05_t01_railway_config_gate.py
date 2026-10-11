"""Contract checks for read-only Railway API configuration, without provider access."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "scripts/ci/check_p05_t01_railway_config.py"
ENV_ID = "synthetic-staging-env"


def snapshot(predeploy):
    return {
        "service": {"id": "synthetic-api", "name": "nfcore-api"},
        "environment": {"id": ENV_ID, "name": "production"},
        "config": {
            "source": {"repo": "faabio3131/kordena-fiscal-engine-v2", "branch": "main"},
            "deploy": {"preDeployCommand": predeploy},
        },
    }


def evaluate(tmp_path: Path, value: object, *, environment_id: str = ENV_ID):
    path = tmp_path / "safe-snapshot.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(TOOL), str(path), "--environment-id", environment_id],
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        (None, 0),
        ([], 0),
        (["python scripts/ci/migration_guard.py --apply"], 42),
        (["echo synthetically-unsafe"], 42),
        ("python scripts/ci/migration_guard.py --apply", 42),
    ],
)
def test_any_predeploy_command_blocks_configuration_certification(
    tmp_path: Path, command, expected: int
) -> None:
    result = evaluate(tmp_path, snapshot(command))
    assert result.returncode == expected, result.stderr
    if expected == 0:
        assert result.stdout.startswith("PASS API preDeployCommand absent")
    else:
        assert "BLOCKED_EXTERNAL" in result.stdout
        assert "synthetically-unsafe" not in result.stdout


@pytest.mark.parametrize("malformed", [None, {}, [], {"service": {"name": "nfcore-api"}}])
def test_unknown_or_partial_snapshot_fails_closed(tmp_path: Path, malformed) -> None:
    result = evaluate(tmp_path, malformed)
    assert result.returncode == 1


def test_wrong_environment_and_service_cannot_be_certified(tmp_path: Path) -> None:
    result = evaluate(tmp_path, snapshot(None), environment_id="another-env")
    assert result.returncode == 1
    wrong = snapshot(None)
    wrong["service"]["name"] = "nfcore-worker"
    result = evaluate(tmp_path, wrong)
    assert result.returncode == 1


def test_cli_never_echoes_migration_command_or_secrets(tmp_path: Path) -> None:
    secret_marker = "synthetic-credential-never-log"
    result = evaluate(tmp_path, snapshot([f"echo {secret_marker}"]))
    assert result.returncode == 42
    assert "BLOCKED_EXTERNAL" in result.stdout
    assert secret_marker not in (result.stdout + result.stderr)
