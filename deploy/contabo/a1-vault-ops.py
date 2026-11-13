#!/usr/bin/env python3
"""Back up encrypted A1 records to a separately encrypted, remote restic repository.

Host-only. Never reads/decrypts A1 private keys, PFX passwords or the A1 master
key. A different, offline recovery channel MUST escrow that key. No restore
ever writes to the live Vault. Remote repository readiness is not proof of
off-VPS storage or key escrow without independently inspected host evidence.
"""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

_VAULT_UID = 10001
_REMOTE_PREFIXES = ("sftp:", "s3:", "b2:", "azure:", "gs:", "swift:", "rclone:", "rest:https://")
_RECORD = re.compile(r"[a-f0-9]{64}\.a1\.enc\Z")


class VaultOpsError(Exception):
    """Reject a backup/restore operation without exposing filesystem paths."""


def _vault_records() -> tuple[Path, dict[str, str]]:
    raw = os.environ.get("NFCORE_A1_VAULT_HOST_DIR", "")
    root = Path(raw)
    if not raw or not root.is_absolute() or root == Path("/") or root.is_symlink():
        raise VaultOpsError()
    try:
        metadata = root.stat()
        if not stat.S_ISDIR(metadata.st_mode) or metadata.st_uid != _VAULT_UID:
            raise VaultOpsError()
        if stat.S_IMODE(metadata.st_mode) & 0o077:
            raise VaultOpsError()
        records: dict[str, str] = {}
        for entry in root.iterdir():
            if entry.is_symlink() or not _RECORD.fullmatch(entry.name):
                raise VaultOpsError()
            details = entry.stat()
            if not stat.S_ISREG(details.st_mode) or stat.S_IMODE(details.st_mode) & 0o077:
                raise VaultOpsError()
            records[entry.name] = hashlib.sha256(entry.read_bytes()).hexdigest()
        return root, records
    except OSError:
        raise VaultOpsError() from None


def _remote_config() -> None:
    repository = os.environ.get("RESTIC_REPOSITORY", "")
    password_path = os.environ.get("RESTIC_PASSWORD_FILE", "")
    if not repository.startswith(_REMOTE_PREFIXES) or not password_path:
        raise VaultOpsError()
    password_file = Path(password_path)
    if not password_file.is_absolute() or password_file.is_symlink():
        raise VaultOpsError()
    try:
        st = password_file.stat()
        if not stat.S_ISREG(st.st_mode) or stat.S_IMODE(st.st_mode) & 0o077:
            raise VaultOpsError()
    except OSError:
        raise VaultOpsError() from None


def _restic(*args: str) -> None:
    try:
        result = subprocess.run(
            ["restic", *args], check=False, capture_output=True,
            timeout=3600, text=True,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise VaultOpsError() from None
    if result.returncode != 0:
        # Never echo restic stdout/stderr: remote URLs and paths can be sensitive.
        raise VaultOpsError()


def backup() -> int:
    root, records = _vault_records()
    _remote_config()
    _restic("backup", "--quiet", "--tag", "nfcore-a1-vault", str(root))
    _restic("check", "--quiet")
    print(f"A1_REMOTE_BACKUP=SUCCESS; ENCRYPTED_RECORDS={len(records)}; KEY_ESCROW=NOT_VERIFIED")
    return 0


def restore_rehearsal() -> int:
    root, expected = _vault_records()
    _remote_config()
    stage = Path(tempfile.mkdtemp(prefix="nfcore-a1-restore-"))
    try:
        os.chmod(stage, 0o700)
        _restic(
            "restore", "latest", "--tag", "nfcore-a1-vault",
            "--quiet", "--target", str(stage),
        )
        restored_root = stage / root.relative_to("/")
        if restored_root.is_symlink() or not restored_root.is_dir():
            raise VaultOpsError()
        restored: dict[str, str] = {}
        for entry in restored_root.iterdir():
            if entry.is_symlink() or not _RECORD.fullmatch(entry.name) or not entry.is_file():
                raise VaultOpsError()
            restored[entry.name] = hashlib.sha256(entry.read_bytes()).hexdigest()
        if restored != expected:
            raise VaultOpsError()
        print(f"A1_ISOLATED_RESTORE=SUCCESS; ENCRYPTED_RECORDS={len(expected)}; KEY_ESCROW=NOT_VERIFIED")
        return 0
    finally:
        shutil.rmtree(stage)


def main() -> int:
    try:
        if len(sys.argv) != 2 or sys.argv[1] not in {"backup", "restore-test"}:
            raise VaultOpsError()
        return backup() if sys.argv[1] == "backup" else restore_rehearsal()
    except (VaultOpsError, OSError, ValueError):
        print("A1_VAULT_OPERATION=NOT_CERTIFIED", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
