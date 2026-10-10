"""Provider-evidence regression matrix; no Railway operations or credentials."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from types import ModuleType
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "deploy" / "railway_evidence.py"
SHA = "a" * 40
OTHER_SHA = "b" * 40


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("nfcore_railway_evidence", SCRIPT)
    assert spec is not None and spec.loader is not None
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


def _cli(check: str, *args: str, payload: Any) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), check, *args],
        input=json.dumps(payload), text=True, capture_output=True, check=False,
    )


def _status(
    *, instances: list[str] | None = None, latest: str = "new",
    active: str = "new", service: str = "worker", environment: str = "env",
    stopped: bool = False,
) -> dict[str, Any]:
    return {
        "id": "project",
        "environments": {
            "edges": [{"node": {
                "id": environment,
                "serviceInstances": {"edges": [{"node": {
                    "serviceId": service,
                    "serviceName": service,
                    "latestDeployment": {"id": latest, "status": "SUCCESS"},
                    "activeDeployments": [{
                        "id": active, "status": "SUCCESS",
                        "deploymentStopped": stopped,
                        "instances": [{"status": x} for x in (instances if instances is not None else ["RUNNING"])],
                    }],
                }}]},
            }}],
        },
    }


def test_provider_deployment_revision_and_identity_are_both_required() -> None:
    payload = [{"id": "new", "status": "SUCCESS", "meta": {"commitHash": SHA}}]
    assert _cli("deployment", SHA, "old", payload=payload).stdout.strip() == "new"
    for tampered in [
        [{"id": "old", "status": "SUCCESS", "meta": {"commitHash": SHA}}],
        [{"id": "new", "status": "SUCCESS", "meta": {"commitHash": OTHER_SHA}}],
        [{"id": "new", "status": "SUCCESS", "meta": {}}],
        [{"id": "new", "status": "CRASHED", "meta": {"commitHash": SHA}}],
        [{"id": "new", "status": "SUCCESS"}],
        [],
        {"id": "new", "status": "SUCCESS", "meta": {"commitHash": SHA}},
    ]:
        result = _cli("deployment", SHA, "old", payload=tampered)
        assert result.returncode != 0
        assert "BLOCKED" in result.stdout


@pytest.mark.parametrize(
    ("scenario", "changes"),
    [
        ("worker 0/1", {"instances": []}),
        ("crashed", {"instances": ["CRASHED"]}),
        ("mixed", {"instances": ["RUNNING", "EXITED"]}),
        ("old latest", {"latest": "old"}),
        ("old active", {"active": "old"}),
        ("stopped", {"stopped": True}),
        ("cross-service", {"service": "other"}),
        ("cross-environment", {"environment": "other"}),
    ],
)
def test_runtime_proof_fails_closed(scenario: str, changes: dict[str, Any]) -> None:
    evidence = _status(**changes)
    assert scenario
    result = _cli("runtime", "project", "env", "worker", "new", payload=evidence)
    assert result.returncode == 1
    assert "BLOCKED" in result.stdout


def test_real_cli_status_shape_proves_serving_running_instances_only() -> None:
    result = _cli("runtime", "project", "env", "worker", "new", payload=_status())
    assert result.returncode == 0
    assert result.stdout.strip() == "new"
    assert _cli("runtime", "wrong", "env", "worker", "new", payload=_status()).returncode == 1
    assert _cli("runtime", "project", "env", "worker", "new", payload={}).returncode == 1


def test_backup_request_requires_provider_id_and_exact_name() -> None:
    good = {"id": "backup-123", "name": "nfcore-pre-abcd"}
    assert _cli("backup-request", "nfcore-pre-abcd", payload=good).stdout.strip() == "backup-123"
    for row in [{}, {"name": good["name"]}, {"id": "backup-123", "name": "wrong"}]:
        assert _cli("backup-request", good["name"], payload=row).returncode != 0


def test_backup_must_be_completed_fresh_and_retained() -> None:
    now = datetime.now(timezone.utc)
    good = {
        "id": "backup-123", "name": "nfcore-pre-abcd", "status": "COMPLETED",
        "completedAt": (now - timedelta(minutes=1)).isoformat(),
        "expiresAt": (now + timedelta(days=7)).isoformat(),
    }
    check = lambda data: _cli("backup-receipt", "backup-123", "nfcore-pre-abcd", payload=data)
    assert check([good]).returncode == 0
    for row in [
        {**good, "status": "QUEUED"},
        {**good, "status": "FAILED"},
        {**good, "completedAt": None},
        {**good, "completedAt": (now + timedelta(days=1)).isoformat()},
        {**good, "expiresAt": None},
        {**good, "expiresAt": (now - timedelta(days=1)).isoformat()},
        {**good, "name": "some-other-backup"},
        {**good, "id": "older-backup"},
    ]:
        assert check([row]).returncode == 1
    assert check([good, good]).returncode == 1
    assert check({"unexpected": [good]}).returncode == 1


def test_malformed_provider_data_is_redacted() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "runtime", "project", "env", "worker", "new"],
        input="{malformed-secret-token}", text=True, capture_output=True, check=False,
    )
    assert result.returncode == 1
    assert "malformed-secret-token" not in result.stdout + result.stderr
    assert "BLOCKED" in result.stdout


def test_baseline_identity_contains_sha_and_refuses_missing_commit() -> None:
    good = [{"id": "deployment-id", "status": "SUCCESS", "meta": {"commitHash": SHA}}]
    assert _cli("baseline", payload=good).stdout.strip() == f"deployment-id\\t{SHA}"
    assert _cli("latest-id", payload=good).stdout.strip() == "deployment-id"
    assert _cli("baseline", payload=[{"id": "deployment-id", "status": "SUCCESS"}]).returncode == 1
