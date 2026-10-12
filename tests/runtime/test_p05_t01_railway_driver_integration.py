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
rollback_file = Path(os.environ.get("FAKE_ROLLBACKS", "/nonexistent-rollback-file"))
rolled_back = rollback_file.read_text().splitlines() if rollback_file.exists() else []
service = (
    args[args.index("--service") + 1]
    if "--service" in args else os.environ["NFCORE_RAILWAY_API_SERVICE"]
)


def snap(name):
    is_new = name in up_services and name not in rolled_back
    return {
        "id": name + ("-rollback" if name in rolled_back else "-new" if is_new else "-old"),
        "status": "SUCCESS",
        "meta": {"commitHash": os.environ["FAKE_NEW_SHA"] if is_new else "b" * 40},
    }


if args[:2] == ["deployment", "list"]:
    print(json.dumps([snap(service)]))
elif args[0] == "status":
    rows = []
    for name in [
        os.environ["NFCORE_RAILWAY_API_SERVICE"],
        os.environ["NFCORE_RAILWAY_WORKER_SERVICE"],
        os.environ["NFCORE_RAILWAY_PORTAL_SERVICE"],
    ]:
        d = snap(name)
        stopped = (
            name == os.environ["NFCORE_RAILWAY_WORKER_SERVICE"]
            and (
                name in rolled_back
                or os.environ.get("FAKE_ALWAYS_STOPPED") == "true"
                or (
                    os.environ.get("FAKE_STOPPED") == "true"
                    and name not in up_services
                )
            )
        )
        instances = [] if stopped else [{"status": "RUNNING"}]
        rows.append({"node": {
            "serviceId": name, "serviceName": name,
            "latestDeployment": {"id": d["id"], "status": "SUCCESS"},
            "activeDeployments": [{
                "id": d["id"], "status": "SUCCESS", "deploymentStopped": stopped,
                "instances": instances,
            }],
        }})
    print(json.dumps({
        "id": os.environ["NFCORE_RAILWAY_PROJECT_ID"], "environments": {"edges": [{"node": {
            "id": os.environ["NFCORE_RAILWAY_ENVIRONMENT_ID"], "serviceInstances": {"edges": rows},
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
        FAKE_ROLLBACKS=str(tmp_path / "rollbacks.log"),
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


def test_driver_rejects_corrupted_rollback_baselines_before_any_rollout(
    tmp_path: Path,
) -> None:
    env = _fake(tmp_path)
    assert _run(env, "prepare-rollback").returncode == 0
    baseline = tmp_path / "baseline.tsv"
    valid = baseline.read_text()
    cases = [
        "",
        valid.splitlines()[0] + "\n",
        valid + valid.splitlines()[0] + "\n",
        valid.replace("b" * 40, "invalid", 1),
    ]
    for corrupted in cases:
        baseline.write_text(corrupted)
        before = (tmp_path / "cmds.log").read_text()
        result = _run(env, "deploy")
        assert result.returncode != 0
        assert "DEPLOY_READY" not in result.stdout
        after = (tmp_path / "cmds.log").read_text()
        assert "up --ci" not in after[len(before):]
    baseline.write_text(valid)


STAGING_PROJECT = "b84b290d-f3b4-46a1-9023-0b761cb96b0d"
STAGING_ENVIRONMENT = "c9878b9b-62b2-4a97-b8ba-743c8a3e99ec"


def _staging_degraded(env: dict[str, str]) -> dict[str, str]:
    env.update(
        NFCORE_RAILWAY_ALLOW_STOPPED_WORKER_BASELINE="true",
        NFCORE_ENVIRONMENT="staging",
        NFCORE_RAILWAY_PROJECT_ID=STAGING_PROJECT,
        NFCORE_RAILWAY_ENVIRONMENT_ID=STAGING_ENVIRONMENT,
        NFCORE_RAILWAY_WORKER_SERVICE="nfcore-worker",
    )
    return env


def test_explicit_staging_exception_captures_stopped_worker_and_requires_new_running_one(
    tmp_path: Path,
) -> None:
    env = _staging_degraded(_fake(tmp_path, stopped_worker=True))
    captured = _run(env, "prepare-rollback")
    assert captured.returncode == 0, captured.stdout + captured.stderr
    baseline = (tmp_path / "baseline.tsv").read_text()
    assert f"nfcore-worker\tnfcore-worker-old\t{'b' * 40}\tstopped" in baseline
    assert f"api\tapi-old\t{'b' * 40}\trunning" in baseline
    assert f"portal\tportal-old\t{'b' * 40}\trunning" in baseline
    assert _run(env, "backup").returncode == 0
    deployed = _run(env, "deploy")
    assert deployed.returncode == 0, deployed.stdout + deployed.stderr
    assert _run(env, "verify-worker").returncode == 0
    assert (tmp_path / "cmds.log").read_text().count("up --ci") == 3


def test_explicit_staging_exception_never_accepts_a_new_stopped_worker(
    tmp_path: Path,
) -> None:
    env = _staging_degraded(_fake(tmp_path, stopped_worker=True))
    env["FAKE_ALWAYS_STOPPED"] = "true"
    assert _run(env, "prepare-rollback").returncode == 0
    assert _run(env, "backup").returncode == 0
    result = _run(env, "deploy")
    assert result.returncode != 0
    assert "DEPLOY_READY" not in result.stdout
    assert (tmp_path / "cmds.log").read_text().count("up --ci") == 2


def test_degraded_staging_baseline_is_invalid_without_exact_scope_and_opt_in(
    tmp_path: Path,
) -> None:
    env = _staging_degraded(_fake(tmp_path, stopped_worker=True))
    for key, value in [
        ("NFCORE_RAILWAY_ALLOW_STOPPED_WORKER_BASELINE", "false"),
        ("NFCORE_ENVIRONMENT", "production"),
        ("NFCORE_ENVIRONMENT", "development"),
        ("NFCORE_RAILWAY_PROJECT_ID", "another-project"),
        ("NFCORE_RAILWAY_ENVIRONMENT_ID", "another-environment"),
        ("NFCORE_RAILWAY_WORKER_SERVICE", "other-worker"),
    ]:
        invalid = {**env, key: value}
        result = _run(invalid, "prepare-rollback")
        assert result.returncode != 0, (key, result.stdout, result.stderr)
        assert "ROLLBACK_BASELINE_CAPTURED" not in result.stdout
        assert "postgres pitr backup" not in (tmp_path / "cmds.log").read_text()
    assert not (tmp_path / "baseline.tsv").exists()


def test_revoking_opt_in_blocks_deploy_of_previously_captured_degraded_baseline(
    tmp_path: Path,
) -> None:
    env = _staging_degraded(_fake(tmp_path, stopped_worker=True))
    assert _run(env, "prepare-rollback").returncode == 0
    invalid = {**env, "NFCORE_RAILWAY_ALLOW_STOPPED_WORKER_BASELINE": "false"}
    result = _run(invalid, "deploy")
    assert result.returncode != 0
    assert "DEPLOY_READY" not in result.stdout
    assert "up --ci" not in (tmp_path / "cmds.log").read_text()


def test_tampered_stopped_api_baseline_is_rejected_without_deploy(
    tmp_path: Path,
) -> None:
    env = _staging_degraded(_fake(tmp_path, stopped_worker=True))
    assert _run(env, "prepare-rollback").returncode == 0
    baseline = tmp_path / "baseline.tsv"
    baseline.write_text(baseline.read_text().replace("\trunning", "\tstopped", 1))
    result = _run(env, "deploy")
    assert result.returncode != 0
    assert "up --ci" not in (tmp_path / "cmds.log").read_text()


def test_stopped_worker_rollback_reports_degraded_state_not_healthy(
    tmp_path: Path,
) -> None:
    env = _staging_degraded(_fake(tmp_path, stopped_worker=True))
    assert _run(env, "prepare-rollback").returncode == 0
    assert _run(env, "backup").returncode == 0
    assert _run(env, "deploy").returncode == 0
    helper = tmp_path / "rollback_helper.py"
    helper.write_text(
        "import os,sys\nfrom pathlib import Path\n"
        "name=sys.argv[2].removesuffix('-old')\n"
        "with Path(os.environ['FAKE_ROLLBACKS']).open('a') as f:f.write(name+'\\n')\n"
    )
    env["NFCORE_RAILWAY_GRAPHQL_HELPER"] = str(helper)
    reverted = _run(env, "rollback")
    assert reverted.returncode == 0, reverted.stdout + reverted.stderr
    assert "ROLLBACK_RESTORED_DEGRADED_WORKER" in reverted.stdout
    assert "ROLLBACK_READY" not in reverted.stdout
    assert "WORKER_PRIOR_STOPPED_STATE_RESTORED" in reverted.stdout


def test_attested_logical_backup_uses_verified_local_artifact_not_paid_pitr(
    tmp_path: Path,
) -> None:
    import hashlib

    env = _staging_degraded(_fake(tmp_path, stopped_worker=True))
    env["NFCORE_RAILWAY_POSTGRES_SERVICE"] = (
        "71691da6-8d32-4c95-9475-d63d9da1cb0c"
    )
    env["NFCORE_RAILWAY_BACKUP_MODE"] = "local-logical-attested"
    env["NFCORE_RAILWAY_LOGICAL_BACKUP_OPT_IN"] = "true"
    env["NFCORE_LOGICAL_RESTORE_STATUS"] = "RESTAURACAO_ISOLADA_OK"
    env["NFCORE_LOGICAL_RESTORE_PG_MAJOR"] = "18"
    env["NFCORE_LOGICAL_RESTORE_TABLE_COUNT"] = "34"
    env["NFCORE_LOGICAL_RESTORE_CLEANED"] = "true"
    archive = tmp_path / "backup.dump.age"
    archive.write_bytes(b"age-encryption.org/v1\n" + b"x" * 100)
    identity = tmp_path / "identity"
    identity.write_text("synthetic")
    age = tmp_path / "bin" / "age"
    age.write_text(
        "#!/usr/bin/env python3\nimport sys\n"
        "sys.stdout.buffer.write(b'PGDMP' + b'x' * 100)\n"
    )
    age.chmod(0o755)
    env["NFCORE_LOGICAL_BACKUP_FILE"] = str(archive)
    env["NFCORE_LOGICAL_BACKUP_IDENTITY"] = str(identity)
    env["NFCORE_LOGICAL_BACKUP_SHA256"] = hashlib.sha256(archive.read_bytes()).hexdigest()
    assert _run(env, "prepare-rollback").returncode == 0
    result = _run(env, "backup")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "LOGICAL_BACKUP_OPERATOR_ATTESTED" in result.stdout
    assert "postgres pitr backup" not in (tmp_path / "cmds.log").read_text()
    env["NFCORE_LOGICAL_BACKUP_SHA256"] = "0" * 64
    denied = _run(env, "backup")
    assert denied.returncode != 0
    assert "LOGICAL_BACKUP_OPERATOR_ATTESTED" not in denied.stdout
