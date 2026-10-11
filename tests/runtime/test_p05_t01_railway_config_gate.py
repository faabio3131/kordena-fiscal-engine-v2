"""Contract checks for read-only Railway API configuration, without provider access."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.ci.check_p05_t01_railway_config import check_snapshot

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
def test_any_predeploy_command_blocks_configuration_certification(command, expected):
    status, message = check_snapshot(snapshot(command), expected_environment=ENV_ID)
    assert status == expected
    if expected == 0:
        assert message.startswith("PASS API preDeployCommand absent")
    else:
        assert "BLOCKED_EXTERNAL" in message
        assert "synthetically-unsafe" not in message


@pytest.mark.parametrize("malformed", [None, {}, [], {"service": {"name": "nfcore-api"}}])
def test_unknown_or_partial_snapshot_fails_closed(malformed):
    status, _ = check_snapshot(malformed, expected_environment=ENV_ID)
    assert status == 1


def test_wrong_environment_and_service_cannot_be_certified():
    status, _ = check_snapshot(snapshot(None), expected_environment="another-env")
    assert status == 1
    wrong = snapshot(None)
    wrong["service"]["name"] = "nfcore-worker"
    status, _ = check_snapshot(wrong, expected_environment=ENV_ID)
    assert status == 1


def test_cli_never_echoes_migration_command_or_secrets(tmp_path: Path):
    path = tmp_path / "safe-snapshot.json"
    secret_marker = "synthetic-credential-never-log"
    path.write_text(json.dumps(snapshot([f"echo {secret_marker}"])))
    tool = Path(__file__).parents[2] / "scripts/ci/check_p05_t01_railway_config.py"
    result = subprocess.run(
        [sys.executable, str(tool), str(path), "--environment-id", ENV_ID],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 42
    assert "BLOCKED_EXTERNAL" in result.stdout
    assert secret_marker not in (result.stdout + result.stderr)
