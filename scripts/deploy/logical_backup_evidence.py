#!/usr/bin/env python3
"""Fail-closed operator-local proof for an already restored staging logical backup.

A matching file and decryptable PostgreSQL custom archive are checked directly.
The restore result is a HUMAN ATTESTATION, not an independent restore test;
this helper never claims that inspecting metadata is a restore certification.
No plaintext file, secrets or raw DSN are emitted.
"""
from __future__ import annotations

import hashlib
import os
import re
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

PROJECT = "b84b290d-f3b4-46a1-9023-0b761cb96b0d"
ENVIRONMENT = "c9878b9b-62b2-4a97-b8ba-743c8a3e99ec"
POSTGRES = "71691da6-8d32-4c95-9475-d63d9da1cb0c"
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
MAX_AGE = timedelta(hours=72)
MAX_SIZE = 1024 * 1024 * 1024


class EvidenceBlocked(ValueError):
    """Missing or untrustworthy local backup evidence."""


def validate(environ: dict[str, str], *, now: datetime | None = None) -> str:
    """Validate exact staging scope and evidence without reading credentials."""
    if (
        environ.get("NFCORE_ENVIRONMENT") != "staging"
        or environ.get("NFCORE_RAILWAY_PROJECT_ID") != PROJECT
        or environ.get("NFCORE_RAILWAY_ENVIRONMENT_ID") != ENVIRONMENT
        or environ.get("NFCORE_RAILWAY_POSTGRES_SERVICE") != POSTGRES
        or environ.get("NFCORE_RAILWAY_LOGICAL_BACKUP_OPT_IN") != "true"
        or environ.get("NFCORE_RAILWAY_BACKUP_MODE") != "local-logical-attested"
        or environ.get("NFCORE_LOGICAL_RESTORE_STATUS") != "RESTAURACAO_ISOLADA_OK"
        or environ.get("NFCORE_LOGICAL_RESTORE_PG_MAJOR") != "18"
        or environ.get("NFCORE_LOGICAL_RESTORE_CLEANED") != "true"
    ):
        raise EvidenceBlocked("staging backup approval or restore attestation absent")
    try:
        tables = int(environ.get("NFCORE_LOGICAL_RESTORE_TABLE_COUNT", ""))
    except ValueError as exc:
        raise EvidenceBlocked("restore table count invalid") from exc
    if not 1 <= tables <= 100_000:
        raise EvidenceBlocked("restore table count invalid")
    expected = environ.get("NFCORE_LOGICAL_BACKUP_SHA256", "")
    if not SHA256.fullmatch(expected):
        raise EvidenceBlocked("backup SHA256 missing")
    archive = Path(environ.get("NFCORE_LOGICAL_BACKUP_FILE", ""))
    identity = Path(environ.get("NFCORE_LOGICAL_BACKUP_IDENTITY", ""))
    if (
        not archive.is_absolute() or archive.suffix != ".age"
        or not archive.name.endswith(".dump.age") or archive.is_symlink()
        or not archive.is_file() or identity.is_symlink() or not identity.is_file()
    ):
        raise EvidenceBlocked("backup or identity file not available")
    size = archive.stat().st_size
    if not 80 <= size <= MAX_SIZE:
        raise EvidenceBlocked("backup size invalid")
    timestamp = datetime.fromtimestamp(archive.stat().st_mtime, tz=UTC)
    current = now or datetime.now(UTC)
    if not timestamp <= current or current - timestamp > MAX_AGE:
        raise EvidenceBlocked("backup is older than the allowed staging window")
    digest = hashlib.sha256()
    with archive.open("rb") as file:
        if not file.read(len(b"age-encryption.org/v1\n")).startswith(
            b"age-encryption.org/v1\n"
        ):
            raise EvidenceBlocked("encrypted archive header invalid")
        file.seek(0)
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    if digest.hexdigest() != expected:
        raise EvidenceBlocked("encrypted archive checksum mismatch")
    # Actual decryption is checked, without writing plaintext to disk or logs.
    try:
        process = subprocess.Popen(
            ["age", "--decrypt", "--identity", str(identity), str(archive)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
    except OSError as exc:
        raise EvidenceBlocked("age executable unavailable") from exc
    try:
        assert process.stdout is not None
        with process.stdout as pipe:
            if pipe.read(5) != b"PGDMP":
                raise EvidenceBlocked("decrypted PostgreSQL archive invalid")
            while pipe.read(1024 * 1024):
                pass
        try:
            result = process.wait(timeout=30)
        except subprocess.TimeoutExpired as exc:
            raise EvidenceBlocked("backup decrypt timeout") from exc
        if result != 0:
            raise EvidenceBlocked("backup decrypt unsuccessful")
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
    return expected


def main() -> int:
    try:
        digest = validate(dict(os.environ))
    except (EvidenceBlocked, OSError):
        print("logical staging backup: BLOCKED evidence not verified")
        return 42
    print(f"logical staging backup: SHA256_VERIFIED={digest}")
    print("logical staging backup: ARCHIVE_DECRYPTED_PGDMP")
    print("logical staging backup: RESTORE_OPERATOR_ATTESTED_NOT_REEXECUTED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
