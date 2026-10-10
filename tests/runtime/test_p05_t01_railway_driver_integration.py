"""End-to-end scripted Railway driver contracts using synthetic CLI replies."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DRIVER = ROOT / "scripts/deploy/drivers/railway.sh"


def _fake(tmp_path: Path, *, stopped_worker: bool = False) -> dict[str, str]:
    rail = tmp_path / "bin"
    rail.mkdir()
    fake = rail / "railway"
    fake.write_text(r'''#!/usr/bin/env python3
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

args = sys.argv[1:]
with Path(os.environ["FAKE_COMMANDS"]).open("a") as handle:
    handle.write(" ".join(args) + "\n")
up = Path(os.environ["FAKE_UP"])
up_services = up.read_text().splitlines() if up.exists() else []
service = args[args.index("--service") + 1] if "--service" in args else "api"


def snap(name):
    is_new = name in up_services
    return {
        "id": name + "-new" if is_new else name + "-old",
        "status": "SUCCESS",
        "meta": {"commitHash": os.environ["FAKE_NEW_SHA"] if is_new else "b" * 40},
    }


if args[:2] == ["deployment", "list"]:
    print(json.dumps([snap(service)]))
elif args[0] == "status":
    rows = []
    for name in ["api", "worker", "portal"]:
        d = snap(name)
        instances = (
            []
            if name == "worker" and os.environ.get("FAKE_STOPPED") == "true"
            else [{"status": "RUNNING"}]
        )
        rows.append({"node": {
            "serviceId": name, "serviceName": name,
            "latestDeployment": {"id": d["id"], "status": "SUCCESS"},
            "activeDeployments": [{
                "id": d["id"], "status": "SUCCESS", "deploymentStopped": False,
                "instances": instances,
            }],
        }})
    print(json.dumps({
        "id": "project", "environments": {"edges": [{"node": {
            "id": "env", "serviceInstances": {"edges": rows},
        }}]},
    }))
elif args[0] == "up":
    with up.open("a") as handle:
        handle.write(service + "\n")
elif args[:4] == ["postgres", "pitr", "backup", "create"]:
    name = args[args.index("--name") + 1]
    Path(os.environ["FAKE_BACKUP_NAME"]).write_text(name)
    print(json.dumps({"id": "b-id", "name": name}))
elif args[:4] == ["postgres", "pitr", "backup", "list"]:
    name = Path(os.environ["FAKE_BACKUP_NAME"]).read_text()
    now = datetime.now(timezone.utc)
    print(json.dumps([{
        "id": "b-id", "name": name, "status": "COMPLETED",
        "completedAt": (now - timedelta(minutes=1)).isoformat(),
        "expiresAt": (now + timedelta(days=7)).isoformat(),
    }]))
''')
    fake.chmod(0o755)
    sha = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True,
    ).strip()
    env = os.environ.copy()
    env.update(
        PATH=f"{rail}:{env.get('PATH', '')}",
        FAKE_COMMANDS=str(tmp_path / "cmds.log"),
        FAKE_UP=str(tmp_path / "up.log"),
        FAKE_BACKUP_NAME=str(tmp_path / "backup_name"),
        FAKE_NEW_SHA=sha,
        FAKE_STOPPED="true" if stopped_worker else "false",
        NFCORE_RAILWAY_PROJECT_ID="project",
        NFCORE_RAILWAY_ENVIRONMENT_ID="env",
        NFCORE_RAILWAY_API_SERVICE="api",
        NFCORE_RAILWAY_WORKER_SERVICE="worker",
        NFCORE_RAILWAY_PORTAL_SERVICE="portal",
        NFCORE_RAILWAY_POSTGRES_SERVICE="postgres",
        NFCORE_RAILWAY_REAL_EXECUTION_ENABLED="true",
        RAILWAY_API_TOKEN="synthetic-token",
        NFCORE_RAILWAY_ROLLBACK_BASELINE_FILE=str(tmp_path / "baseline.tsv"),
        NFCORE_RAILWAY_WAIT_ATTEMPTS="1",
        NFCORE_RAILWAY_WAIT_SECONDS="0",
        NFCORE_RAILWAY_BACKUP_WAIT_ATTEMPTS="1",
        NFCORE_RAILWAY_BACKUP_WAIT_SECONDS="0",
    )
    return env


def _run(env: dict[str, str], task: str) -> subprocess.CompletedProcess[str]:
    sha = env["FAKE_NEW_SHA"]
    return subprocess.run(
        ["sh", str(DRIVER), task, sha], cwd=ROOT, env=env,
        text=True, capture_output=True, check=False,
    )


def test_driver_accepts_only_valid_baseline_backup_and_live_new_revision(
    tmp_path: Path,
) -> None:
    env = _fake(tmp_path)
    assert _run(env, "prepare-rollback").returncode == 0
    baseline = (tmp_path / "baseline.tsv").read_text()
    for service in ("api", "worker", "portal"):
        assert f"{service}\t{service}-old\t{'b' * 40}" in baseline
    receipt = _run(env, "backup")
    assert receipt.returncode == 0, receipt.stdout + receipt.stderr
    assert "BACKUP_COMPLETED" in receipt.stdout
    deployed = _run(env, "deploy")
    assert deployed.returncode == 0, deployed.stdout + deployed.stderr
    assert _run(env, "verify-worker").returncode == 0
    commands = (tmp_path / "cmds.log").read_text()
    assert "postgres pitr backup list" in commands
    assert "status --project project --environment env --json" in commands
    assert commands.count("up --ci") == 3


def test_driver_rejects_worker_zero_replicas_before_backup(
    tmp_path: Path,
) -> None:
    env = _fake(tmp_path, stopped_worker=True)
    result = _run(env, "prepare-rollback")
    assert result.returncode != 0
    assert "ROLLBACK_BASELINE_CAPTURED" not in result.stdout
    assert not (tmp_path / "baseline.tsv").exists()
    assert "postgres pitr backup" not in (tmp_path / "cmds.log").read_text()
