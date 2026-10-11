#!/usr/bin/env python3
"""Staging-only candidate: pipe pg_dump straight into age, never to a plaintext file.

This is an INTERNAL candidate for NFV1-P05-T01. It does NOT upload or certify a
recoverable Railway backup. Provisioning, storage, custody and restore require
independent approval and external evidence.
"""

from __future__ import annotations

import hashlib
import os
import re
import stat
import subprocess
import sys
from pathlib import Path

PROJECT_ID = "b84b290d-f3b4-46a1-9023-0b761cb96b0d"
ENVIRONMENT_ID = "c9878b9b-62b2-4a97-b8ba-743c8a3e99ec"
POSTGRES_SERVICE_ID = "71691da6-8d32-4c95-9475-d63d9da1cb0c"
AGE_RECIPIENT = re.compile(r"age1[023456789acdefghjklmnpqrstuvwxyz]{58}\Z")
MAX_SECONDS = 900


class BackupBlocked(Exception):
    """A local or operational prerequisite was not met."""


def _get(env: dict[str, str], key: str) -> str:
    value = env.get(key, "")
    if not value or value != value.strip():
        raise BackupBlocked("backup configuration incomplete")
    return value


def validate_config(env: dict[str, str], destination: Path) -> str:
    """Validate scope before touching the filesystem or starting pg_dump."""
    if (
        env.get("NFCORE_BACKUP_EXECUTION_APPROVED") != "true"
        or env.get("NFCORE_ENVIRONMENT") != "staging"
        or env.get("NFCORE_RAILWAY_PROJECT_ID") != PROJECT_ID
        or env.get("NFCORE_RAILWAY_ENVIRONMENT_ID") != ENVIRONMENT_ID
        or env.get("NFCORE_RAILWAY_POSTGRES_SERVICE_ID") != POSTGRES_SERVICE_ID
        or _get(env, "PGHOST") != "postgres.railway.internal"
        # libpq can override the physical host via PGHOSTADDR or PGSERVICE.
        # Never inherit alternate connection identities or password-file paths.
        or any(
            env.get(name)
            for name in (
                "PGHOSTADDR",
                "PGSERVICE",
                "PGSERVICEFILE",
                "PGPASSFILE",
                "PGOPTIONS",
                "PGREQUIRESSL",
            )
        )
        or not _get(env, "PGPORT").isdigit()
        or not 1 <= int(_get(env, "PGPORT")) <= 65535
        or env.get("PGSSLMODE") not in {"require", "verify-ca", "verify-full"}
    ):
        raise BackupBlocked("staging-only backup authorization or scope missing")
    for name in ("PGUSER", "PGDATABASE", "PGPASSWORD"):
        _get(env, name)

    recipient = _get(env, "NFCORE_BACKUP_AGE_RECIPIENT")
    if not AGE_RECIPIENT.fullmatch(recipient):
        raise BackupBlocked("age recipient configuration invalid")
    if not destination.is_absolute() or destination.suffix != ".age":
        raise BackupBlocked("encrypted output path invalid")
    parent = destination.parent
    if (
        parent.is_symlink()
        or not parent.is_dir()
        or not stat.S_ISDIR(parent.stat().st_mode)
        or (parent.stat().st_mode & 0o077)
        or parent.stat().st_uid != os.getuid()
    ):
        raise BackupBlocked("private backup directory required")
    if destination.exists() or destination.is_symlink():
        raise BackupBlocked("backup output already exists")
    if Path(str(destination) + ".sha256").exists():
        raise BackupBlocked("backup manifest already exists")
    return recipient


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def create_encrypted_backup(destination: Path, *, environ: dict[str, str] | None = None) -> str:
    """Write age ciphertext and its checksum, fail closed on every subprocess error.

    The age *recipient* is public. The age private identity is never present in
    this process; it is controlled by the separate, approved recovery operator.
    """
    env = dict(os.environ if environ is None else environ)
    recipient = validate_config(env, destination)
    partial = Path(str(destination) + ".pending")
    digest_path = Path(str(destination) + ".sha256")
    digest_pending = Path(str(digest_path) + ".pending")
    for path in (partial, digest_pending):
        if path.exists() or path.is_symlink():
            raise BackupBlocked("incomplete artifact exists; operator review required")

    descriptor: int | None = None
    pg_dump: subprocess.Popen[bytes] | None = None
    encrypt: subprocess.Popen[bytes] | None = None
    published = False
    owned_partial = False
    owned_manifest_pending = False
    owned_output = False
    owned_manifest = False
    try:
        descriptor = os.open(partial, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        owned_partial = True
        # PG connection settings are inherited from the approved runtime channel,
        # never placed in argv or printed. No plaintext dump file is ever opened.
        pg_dump = subprocess.Popen(
            ["pg_dump", "--format=custom", "--no-owner", "--no-acl", "--no-password"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env=env,
        )
        try:
            assert pg_dump.stdout is not None
            with os.fdopen(descriptor, "wb") as ciphertext:
                descriptor = None
                encrypt = subprocess.Popen(
                    ["age", "--encrypt", "--recipient", recipient],
                    stdin=pg_dump.stdout,
                    stdout=ciphertext,
                    stderr=subprocess.DEVNULL,
                    env={"PATH": env.get("PATH", ""), "HOME": env.get("HOME", "/nonexistent")},
                )
                pg_dump.stdout.close()
                if encrypt.wait(timeout=MAX_SECONDS) != 0:
                    raise BackupBlocked("encryption subprocess failed")
                if pg_dump.wait(timeout=30) != 0:
                    raise BackupBlocked("database export subprocess failed")
                ciphertext.flush()
                os.fsync(ciphertext.fileno())
        except (OSError, subprocess.SubprocessError):
            raise BackupBlocked("backup pipeline unavailable") from None

        if partial.stat().st_size == 0:
            raise BackupBlocked("encrypted backup empty")
        digest = _sha256(partial)
        # Never replace an existing artifact. Hard link is atomic on POSIX.
        os.link(partial, destination)
        owned_output = True
        descriptor = os.open(digest_pending, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        owned_manifest_pending = True
        with os.fdopen(descriptor, "w", encoding="ascii") as manifest:
            descriptor = None
            manifest.write(digest + "\n")
            manifest.flush()
            os.fsync(manifest.fileno())
        os.link(digest_pending, digest_path)
        owned_manifest = True
        published = True
        return digest
    except BackupBlocked:
        raise
    except (OSError, subprocess.SubprocessError):
        raise BackupBlocked("backup artifact creation failed") from None
    finally:
        for proc in (encrypt, pg_dump):
            if proc is not None and proc.poll() is None:
                proc.kill()
                proc.wait(timeout=5)
        if descriptor is not None:
            os.close(descriptor)
        if owned_partial:
            partial.unlink(missing_ok=True)
        if owned_manifest_pending:
            digest_pending.unlink(missing_ok=True)
        if not published:
            if owned_output:
                destination.unlink(missing_ok=True)
            if owned_manifest:
                digest_path.unlink(missing_ok=True)


def main() -> int:
    if len(sys.argv) != 2:
        print("BLOCKED_EXTERNAL encrypted backup destination required", file=sys.stderr)
        return 42
    try:
        result = create_encrypted_backup(Path(sys.argv[1]))
    except BackupBlocked:
        # Do not echo exception, subprocess stderr, PG settings or recipient.
        print("BLOCKED_EXTERNAL encrypted staging backup not certified", file=sys.stderr)
        return 42
    print(f"ENCRYPTED_LOCAL_ARTIFACT_CREATED sha256={result}")
    print("EXTERNAL_STORAGE_AND_RESTORE_NOT_CERTIFIED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
