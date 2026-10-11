"""Synthetic-only tests for private staging pg_dump -> age streaming candidate.

The fake age binary is NOT a cryptographic implementation. A real age
encrypt/decrypt/recoverability rehearsal is an explicit external gate.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.backup.private_staging_backup import BackupBlocked, create_encrypted_backup

PROJECT = "b84b290d-f3b4-46a1-9023-0b761cb96b0d"
ENVIRONMENT = "c9878b9b-62b2-4a97-b8ba-743c8a3e99ec"
SERVICE = "71691da6-8d32-4c95-9475-d63d9da1cb0c"
SYNTHETIC_DUMP = b"synthetic-only-not-customer-data-20261011"
FAKE_RECIPIENT = "age1" + "q" * 58
SCRIPT = Path(__file__).resolve().parents[2] / "scripts/backup/private_staging_backup.py"


def _env(tmp_path: Path) -> dict[str, str]:
    return {
        "NFCORE_BACKUP_EXECUTION_APPROVED": "true",
        "NFCORE_ENVIRONMENT": "staging",
        "NFCORE_RAILWAY_PROJECT_ID": PROJECT,
        "NFCORE_RAILWAY_ENVIRONMENT_ID": ENVIRONMENT,
        "NFCORE_RAILWAY_POSTGRES_SERVICE_ID": SERVICE,
        "NFCORE_BACKUP_AGE_RECIPIENT": FAKE_RECIPIENT,
        "PGHOST": "postgres.railway.internal",
        "PGPORT": "5432",
        "PGUSER": "synthetic_user",
        "PGDATABASE": "synthetic_db",
        "PGSSLMODE": "require",
        "PGPASSWORD": "synthetic-do-not-log-20261011",
        "PATH": str(tmp_path) + os.pathsep + os.environ.get("PATH", ""),
    }


def _fake_executables(tmp_path: Path) -> None:
    pg = tmp_path / "pg_dump"
    pg.write_text(
        "#!/usr/bin/env python3\n"
        "import os,sys\n"
        "assert '--file' not in ' '.join(sys.argv)\n"
        "assert '--no-password' in sys.argv\n"
        f"sys.stdout.buffer.write({SYNTHETIC_DUMP!r})\n"
        "sys.exit(int(os.getenv('SYNTHETIC_PG_EXIT','0')))\n"
    )
    pg.chmod(0o755)
    age = tmp_path / "age"
    age.write_text(
        "#!/usr/bin/env python3\n"
        "import os,sys\n"
        "assert sys.argv[1:3] == ['--encrypt','--recipient']\n"
        "assert sys.argv[3].startswith('age1')\n"
        "assert 'PGPASSWORD' not in os.environ\n"
        "payload=sys.stdin.buffer.read()\n"
        "sys.stdout.buffer.write(b'SYNTHETIC-AGE-DOUBLE-' + payload[::-1])\n"
        "sys.exit(int(os.getenv('SYNTHETIC_AGE_EXIT','0')))\n"
    )
    age.chmod(0o755)


def _stage(tmp_path: Path) -> Path:
    private = tmp_path / "private"
    private.mkdir(mode=0o700)
    return private / "nfcore.age"


def test_encrypted_stream_candidate_has_no_plaintext_artifact(tmp_path: Path) -> None:
    _fake_executables(tmp_path)
    dest = _stage(tmp_path)
    digest = create_encrypted_backup(dest, environ=_env(tmp_path))
    ciphertext = dest.read_bytes()
    assert SYNTHETIC_DUMP not in ciphertext
    assert ciphertext.startswith(b"SYNTHETIC-AGE-DOUBLE-")
    assert hashlib.sha256(ciphertext).hexdigest() == digest
    assert Path(str(dest) + ".sha256").read_text().strip() == digest
    assert set(p.name for p in dest.parent.iterdir()) == {"nfcore.age", "nfcore.age.sha256"}
    assert (dest.stat().st_mode & 0o077) == 0


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("NFCORE_BACKUP_EXECUTION_APPROVED", "false"),
        ("NFCORE_ENVIRONMENT", "production"),
        ("NFCORE_RAILWAY_PROJECT_ID", "another-project"),
        ("NFCORE_RAILWAY_ENVIRONMENT_ID", "other-env"),
        ("NFCORE_RAILWAY_POSTGRES_SERVICE_ID", "other-service"),
        ("NFCORE_BACKUP_AGE_RECIPIENT", "invalid"),
        ("PGHOST", "public-db.example.com"),
        ("PGPORT", "99999"),
        ("PGPORT", "abc"),
        ("PGSSLMODE", "disable"),
        ("PGPASSWORD", ""),
        ("PGUSER", ""),
    ],
)
def test_scope_rejected_before_process(
    tmp_path: Path, field: str, replacement: str
) -> None:
    _fake_executables(tmp_path)
    dest = _stage(tmp_path)
    env = _env(tmp_path)
    env[field] = replacement
    with pytest.raises(BackupBlocked):
        create_encrypted_backup(dest, environ=env)
    assert list(dest.parent.iterdir()) == []


@pytest.mark.parametrize(("failed", "exit_code"), [("SYNTHETIC_PG_EXIT", "9")])
def test_export_error_removes_all_artifacts(tmp_path: Path, failed: str, exit_code: str) -> None:
    _fake_executables(tmp_path)
    dest = _stage(tmp_path)
    env = _env(tmp_path)
    env[failed] = exit_code
    with pytest.raises(BackupBlocked):
        create_encrypted_backup(dest, environ=env)
    assert list(dest.parent.iterdir()) == []


def test_missing_encryption_binary_fails_without_leaking_config(tmp_path: Path) -> None:
    _fake_executables(tmp_path)
    (tmp_path / "age").unlink()
    dest = _stage(tmp_path)
    env = _env(tmp_path)
    with pytest.raises(BackupBlocked) as exc:
        create_encrypted_backup(dest, environ=env)
    assert env["PGPASSWORD"] not in str(exc.value)
    assert list(dest.parent.iterdir()) == []


def test_preexisting_backup_and_symlink_blocked(tmp_path: Path) -> None:
    _fake_executables(tmp_path)
    dest = _stage(tmp_path)
    dest.write_bytes(b"previous encrypted artifact")
    with pytest.raises(BackupBlocked):
        create_encrypted_backup(dest, environ=_env(tmp_path))
    assert dest.read_bytes() == b"previous encrypted artifact"


def test_nonprivate_directory_rejected(tmp_path: Path) -> None:
    _fake_executables(tmp_path)
    dest = _stage(tmp_path)
    dest.parent.chmod(0o755)
    with pytest.raises(BackupBlocked):
        create_encrypted_backup(dest, environ=_env(tmp_path))
    assert not dest.exists()


def test_cli_does_not_print_pg_config_or_recipient(tmp_path: Path) -> None:
    _fake_executables(tmp_path)
    dest = _stage(tmp_path)
    env = {**os.environ, **_env(tmp_path)}
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(dest)],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    output = result.stdout + result.stderr
    assert result.returncode == 0
    assert "ENCRYPTED_LOCAL_ARTIFACT_CREATED" in output
    for sensitive in ("PGPASSWORD", env["PGPASSWORD"], FAKE_RECIPIENT, env["PGUSER"]):
        assert sensitive not in output
    assert "EXTERNAL_STORAGE_AND_RESTORE_NOT_CERTIFIED" in output
