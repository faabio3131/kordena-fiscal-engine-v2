"""Focused, local-only regression of P05 logical backup evidence; no Railway I/O."""
from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "scripts" / "deploy" / "logical_backup_evidence.py"
PROJECT = "b84b290d-f3b4-46a1-9023-0b761cb96b0d"
ENVIRONMENT = "c9878b9b-62b2-4a97-b8ba-743c8a3e99ec"
POSTGRES = "71691da6-8d32-4c95-9475-d63d9da1cb0c"


def _setup(tmp_path: Path) -> dict[str, str]:
    archive = tmp_path / "db.dump.age"
    archive.write_bytes(b"age-encryption.org/v1\n" + b"x" * 100)
    identity = tmp_path / "private-key"
    identity.write_text("synthetic-not-a-real-key")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake_age = bin_dir / "age"
    fake_age.write_text(
        "#!/usr/bin/env python3\n"
        "import os,sys\n"
        "sys.stdout.buffer.write(os.environ.get('FAKE_PGDMP', 'PGDMP').encode() + b'x' * 50)\n"
        "sys.exit(int(os.environ.get('FAKE_AGE_EXIT', '0')))\n"
    )
    fake_age.chmod(0o755)
    return {
        **os.environ,
        "PATH": f"{bin_dir}:{os.environ.get('PATH', '')}",
        "NFCORE_ENVIRONMENT": "staging",
        "NFCORE_RAILWAY_PROJECT_ID": PROJECT,
        "NFCORE_RAILWAY_ENVIRONMENT_ID": ENVIRONMENT,
        "NFCORE_RAILWAY_POSTGRES_SERVICE": POSTGRES,
        "NFCORE_RAILWAY_LOGICAL_BACKUP_OPT_IN": "true",
        "NFCORE_RAILWAY_BACKUP_MODE": "local-logical-attested",
        "NFCORE_LOGICAL_RESTORE_STATUS": "RESTAURACAO_ISOLADA_OK",
        "NFCORE_LOGICAL_RESTORE_PG_MAJOR": "18",
        "NFCORE_LOGICAL_RESTORE_TABLE_COUNT": "34",
        "NFCORE_LOGICAL_RESTORE_CLEANED": "true",
        "NFCORE_LOGICAL_BACKUP_FILE": str(archive),
        "NFCORE_LOGICAL_BACKUP_IDENTITY": str(identity),
        "NFCORE_LOGICAL_BACKUP_SHA256": hashlib.sha256(archive.read_bytes()).hexdigest(),
    }


def _run(env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(TOOL)], env=env, cwd=ROOT,
        text=True, capture_output=True, check=False, timeout=10,
    )


def test_real_file_digest_and_pgdmp_required(tmp_path: Path) -> None:
    env = _setup(tmp_path)
    ok = _run(env)
    assert ok.returncode == 0
    assert "ARCHIVE_DECRYPTED_PGDMP" in ok.stdout
    assert "RESTORE_OPERATOR_ATTESTED_NOT_REEXECUTED" in ok.stdout
    bad = {**env, "FAKE_PGDMP": "WRONG"}
    assert _run(bad).returncode == 42
    assert _run({**env, "FAKE_AGE_EXIT": "1"}).returncode == 42


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("NFCORE_ENVIRONMENT", "production"),
        ("NFCORE_RAILWAY_PROJECT_ID", "wrong"),
        ("NFCORE_RAILWAY_ENVIRONMENT_ID", "wrong"),
        ("NFCORE_RAILWAY_POSTGRES_SERVICE", "wrong"),
        ("NFCORE_RAILWAY_LOGICAL_BACKUP_OPT_IN", "false"),
        ("NFCORE_RAILWAY_BACKUP_MODE", "pitr"),
        ("NFCORE_LOGICAL_RESTORE_STATUS", "FAILED"),
        ("NFCORE_LOGICAL_RESTORE_PG_MAJOR", "16"),
        ("NFCORE_LOGICAL_RESTORE_TABLE_COUNT", "0"),
        ("NFCORE_LOGICAL_RESTORE_CLEANED", "false"),
        ("NFCORE_LOGICAL_BACKUP_SHA256", "0" * 64),
    ],
)
def test_wrong_scope_or_forged_restore_claim_rejected(
    tmp_path: Path, name: str, value: str,
) -> None:
    env = _setup(tmp_path)
    env[name] = value
    result = _run(env)
    assert result.returncode == 42
    assert "SHA256_VERIFIED" not in result.stdout


def test_changed_ciphertext_rejected(tmp_path: Path) -> None:
    env = _setup(tmp_path)
    Path(env["NFCORE_LOGICAL_BACKUP_FILE"]).write_bytes(
        b"age-encryption.org/v1\n" + b"y" * 100
    )
    assert _run(env).returncode == 42


def test_stale_ciphertext_rejected(tmp_path: Path) -> None:
    env = _setup(tmp_path)
    archive = Path(env["NFCORE_LOGICAL_BACKUP_FILE"])
    stale = (datetime.now(UTC) - timedelta(days=5)).timestamp()
    os.utime(archive, (stale, stale))
    assert _run(env).returncode == 42


def test_symlink_and_missing_archive_rejected(tmp_path: Path) -> None:
    env = _setup(tmp_path)
    archive = Path(env["NFCORE_LOGICAL_BACKUP_FILE"])
    link = tmp_path / "link.dump.age"
    link.symlink_to(archive)
    assert _run({**env, "NFCORE_LOGICAL_BACKUP_FILE": str(link)}).returncode == 42
    archive.unlink()
    assert _run(env).returncode == 42
