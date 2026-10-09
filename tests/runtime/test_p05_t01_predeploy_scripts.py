from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("corrupt,restore_exit", [(False, 0), (True, 0), (False, 7)])
def test_restore_checks_integrity_and_passes_connection_as_dbname(
    tmp_path: Path, corrupt: bool, restore_exit: int
) -> None:
    dump = tmp_path / "backup with spaces.dump"
    dump.write_bytes(b"synthetic dump")
    checksum = hashlib.sha256(dump.read_bytes()).hexdigest()
    Path(f"{dump}.sha256").write_text(f"{checksum}  {dump}\n")
    if corrupt:
        dump.write_bytes(b"changed")
    binary = tmp_path / "pg_restore"
    binary.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, sys\n"
        "from pathlib import Path\n"
        "Path(os.environ['RESTORE_ARGS']).write_text(json.dumps(sys.argv[1:]))\n"
        "raise SystemExit(int(os.environ['RESTORE_EXIT']))\n"
    )
    binary.chmod(0o755)
    # Alpine's BusyBox accepts -c but rejects GNU's --check spelling.
    checksum_binary = tmp_path / "sha256sum"
    checksum_binary.write_text(
        "#!/bin/sh\n"
        "[ \"$1\" = -c ] || exit 64\n"
        f"exec '{shutil.which('sha256sum')}' \"$@\"\n"
    )
    checksum_binary.chmod(0o755)
    args_path = tmp_path / "args.json"
    dsn = "postgresql://synthetic@localhost/synthetic"
    env = os.environ.copy()
    env.update(
        PATH=f"{tmp_path}:{env['PATH']}", DATABASE_URL=dsn,
        RESTORE_ARGS=str(args_path), RESTORE_EXIT=str(restore_exit),
    )
    result = subprocess.run(
        ["sh", str(ROOT / "scripts/postgres_restore.sh"), str(dump)],
        env=env, capture_output=True, text=True, check=False,
    )
    assert dsn not in result.stdout + result.stderr
    if corrupt:
        assert result.returncode != 0
        assert not args_path.exists()
    else:
        assert json.loads(args_path.read_text()) == [
            f"--dbname={dsn}", "--no-owner", "--no-acl", "--exit-on-error", str(dump),
        ]
        assert result.returncode == restore_exit
    assert ("restore_completed=" in result.stdout) == (not corrupt and restore_exit == 0)


@pytest.mark.parametrize("failed_stage", ["prepare-rollback", "backup", "migration"])
def test_predeploy_stops_before_mutation_when_a_prerequisite_fails(
    tmp_path: Path, failed_stage: str
) -> None:
    ci = tmp_path / "scripts/ci"
    ci.mkdir(parents=True)
    for name in ("staging_preflight.sh", "run_staging_deploy.sh"):
        shutil.copyfile(ROOT / "scripts/ci" / name, ci / name)
    drivers = tmp_path / "scripts/deploy/drivers"
    drivers.mkdir(parents=True)
    driver = drivers / "synthetic.sh"
    driver.write_text(
        "#!/bin/sh\n"
        "if [ \"$1\" = contract ]; then echo nfcore-staging-driver-v1; exit 0; fi\n"
        "echo \"$1\" >> \"$OPERATION_LOG\"\n"
        "[ \"$1\" != \"$FAILED_STAGE\" ]\n"
    )
    binary = tmp_path / "python"
    binary.write_text(
        "#!/bin/sh\n"
        "echo migration >> \"$OPERATION_LOG\"\n"
        "exit 7\n"
    )
    binary.chmod(0o755)
    log = tmp_path / "operations.log"
    env = os.environ.copy()
    env.update(
        PATH=f"{tmp_path}:{env['PATH']}", OPERATION_LOG=str(log), FAILED_STAGE=failed_stage,
        NFCORE_STAGING_BASE_URL="https://api.example.invalid",
        NFCORE_STAGING_PORTAL_URL="https://portal.example.invalid",
        NFCORE_STAGING_DEPLOY_DRIVER="scripts/deploy/drivers/synthetic.sh",
        NFCORE_ENVIRONMENT="staging", NFCORE_PERSISTENCE_BACKEND="postgres",
        NFCORE_SECRET_BACKEND="external", NFCORE_REQUIRE_HTTPS="true",
        NFCORE_DEPLOY_REVISION="a" * 40, DATABASE_URL="postgresql://synthetic@localhost/db",
    )
    result = subprocess.run(
        ["sh", "scripts/ci/run_staging_deploy.sh"], cwd=tmp_path,
        env=env, capture_output=True, text=True, check=False,
    )
    assert result.returncode != 0
    assert log.exists(), result.stdout + result.stderr
    expected = ["prepare-rollback", "backup", "migration"]
    assert log.read_text().splitlines() == expected[:expected.index(failed_stage) + 1]
