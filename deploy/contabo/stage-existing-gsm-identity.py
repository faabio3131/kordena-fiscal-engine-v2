#!/usr/bin/env python3
"""Stage an EXISTING NFCore GSM service-account identity on the Contabo host.

This one-time operator tool does not create keys, access other SaaS, connect to
GCP, start containers, execute DDL or output private credential material.
IAM access and PostgreSQL recovery/lease gates remain separate requirements.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

HOST = "vmi3692211"
PROD_DIR = Path("/opt/fm/nfcore")
SOURCE_DIR = PROD_DIR / "src"
INBOX_DIR = Path("/etc/nfcore/incoming")
WORKER_DIR = Path("/etc/nfcore/worker")
TARGET_IDENTITY = WORKER_DIR / "worker-identity.json"
WORKER_ENV = PROD_DIR / ".env.worker"
COMPOSE_ENV = PROD_DIR / ".worker-compose.env"
PROJECT = "fm-nfcore-prod"
PROJECT_NUMBER = "646230745113"
WORKER_EMAIL = "nfcore-worker@fm-nfcore-prod.iam.gserviceaccount.com"
API_EMAIL = "nfcore-api@fm-nfcore-prod.iam.gserviceaccount.com"
SHA_RE = re.compile(r"[0-9a-f]{40}\Z")


class Denied(Exception):
    """Fail-closed rejection using fixed, non-secret error codes."""


def require(condition: bool, code: str) -> None:
    if not condition:
        raise Denied(code)


def ensure_trusted_directory(
    path: Path, *, required: bool = True, allowed_owners: tuple[int, ...] = (0,)
) -> None:
    if not path.exists() and not path.is_symlink():
        if required:
            raise Denied("NO_GO_MISSING_TRUSTED_DIRECTORY")
        return
    require(not path.is_symlink(), "NO_GO_SYMLINK_DIR")
    st = path.lstat()
    require(stat.S_ISDIR(st.st_mode) and st.st_uid in allowed_owners,
            "NO_GO_UNTRUSTED_DIRECTORY")
    require(stat.S_IMODE(st.st_mode) & 0o022 == 0, "NO_GO_WRITABLE_DIRECTORY")


def parse_existing_identity(raw: bytes) -> str:
    """Validate exact SA JSON metadata without exposing private key material."""
    try:
        def unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
            result: dict[str, object] = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError("duplicate")
                result[key] = value
            return result

        key = json.loads(raw.decode("utf-8"), object_pairs_hook=unique)
        require(isinstance(key, dict), "NO_GO_IDENTITY_FORMAT")
        require(all(isinstance(v, str) for v in key.values()), "NO_GO_IDENTITY_FORMAT")
        mandatory = {"type", "project_id", "private_key_id", "private_key",
                     "client_email", "token_uri"}
        allowed = mandatory | {"client_id", "auth_uri", "auth_provider_x509_cert_url",
                               "client_x509_cert_url", "universe_domain"}
        require(mandatory <= key.keys() and key.keys() <= allowed, "NO_GO_IDENTITY_FIELDS")
        require(key["type"] == "service_account" and key["project_id"] == PROJECT,
                "NO_GO_WRONG_PROJECT")
        require(key["client_email"] == WORKER_EMAIL, "NO_GO_WRONG_WORKLOAD_IDENTITY")
        require(key["token_uri"] == "https://oauth2.googleapis.com/token"
                and key.get("universe_domain", "googleapis.com") == "googleapis.com",
                "NO_GO_INVALID_IDENTITY_ENDPOINT")
        require(bool(SHA_RE.fullmatch(key["private_key_id"])), "NO_GO_INVALID_KEY_ID")
        private = key["private_key"]
        pem_type = "PRIVATE " + "KEY"
        require(private.startswith(f"-----BEGIN {pem_type}-----\n")
                and private.rstrip().endswith(f"-----END {pem_type}-----"),
                "NO_GO_PRIVATE_KEY_FORMAT")
        return key["private_key_id"]
    except (ValueError, UnicodeDecodeError, TypeError, KeyError):
        raise Denied("NO_GO_INVALID_EXISTING_IDENTITY") from None


def validate_created_at(value: str, *, now: datetime | None = None) -> tuple[str, str]:
    """Use creation timestamp independently verified in Google IAM, not file time."""
    try:
        created = datetime.fromisoformat(value.replace("Z", "+00:00"))
        require(created.tzinfo is not None, "NO_GO_KEY_TIMEZONE")
        created = created.astimezone(UTC)
        current = now or datetime.now(UTC)
        expires = created + timedelta(days=90)
        require(created <= current < expires, "NO_GO_KEY_EXPIRED_OR_FUTURE")
        return created.isoformat(timespec="seconds"), expires.isoformat(timespec="seconds")
    except ValueError:
        raise Denied("NO_GO_KEY_CREATED_TIME") from None


def render_env(*, key_id: str, created: str, expiry: str) -> bytes:
    values = {
        "NFCORE_WORKER_GSM_MODE": "multi-tenant-production-sa-v1",
        "NFCORE_GSM_PROJECT_ID": PROJECT,
        "NFCORE_GSM_ALLOWED_PROJECTS": PROJECT,
        "NFCORE_GSM_PROJECT_NUMBER": PROJECT_NUMBER,
        "NFCORE_GSM_API_SERVICE_ACCOUNT": API_EMAIL,
        "NFCORE_GSM_WORKER_SERVICE_ACCOUNT": WORKER_EMAIL,
        "NFCORE_WORKER_GSM_HOST_NAMESPACE": "nfcore",
        "NFCORE_PUBLIC_HOSTNAME": "api.nfcore.com.br",
        "NFCORE_ALLOWED_ORIGINS": "https://app.nfcore.com.br",
        "NFCORE_REQUIRE_HTTPS": "true",
        "NFCORE_WORKER_GSM_KEY_ID": key_id,
        "NFCORE_WORKER_GSM_KEY_CREATED_AT": created,
        "NFCORE_WORKER_GSM_KEY_NOT_AFTER": expiry,
    }
    return ("\n".join(f"{key}={value}" for key, value in values.items()) + "\n").encode()


def check_host(expected_sha: str) -> None:
    require(os.geteuid() == 0, "NO_GO_ROOT_REQUIRED")
    require(os.uname().nodename == HOST, "NO_GO_UNEXPECTED_HOST")
    require(bool(SHA_RE.fullmatch(expected_sha)), "NO_GO_RELEASE_SHA_FORMAT")
    try:
        state = (PROD_DIR / ".deployed").read_text(encoding="ascii").splitlines()
    except (OSError, UnicodeDecodeError):
        raise Denied("NO_GO_DEPLOY_MARKER_MISSING") from None
    env = os.environ.copy()
    env.update({
        "GIT_CONFIG_COUNT": "1",
        "GIT_CONFIG_KEY_0": "safe.directory",
        "GIT_CONFIG_VALUE_0": str(SOURCE_DIR),
    })
    try:
        cp = subprocess.run(
            ["/usr/bin/git", "-C", str(SOURCE_DIR), "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True, timeout=10, env=env,
        )
        source_sha = cp.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        raise Denied("NO_GO_RELEASE_UNAVAILABLE") from None
    require(state == ["SHA=" + expected_sha] and source_sha == expected_sha,
            "NO_GO_PRODUCTION_RELEASE_MISMATCH")


def read_existing_identity(source: Path) -> tuple[bytes, str]:
    require(source.parent == INBOX_DIR and source != TARGET_IDENTITY,
            "NO_GO_SOURCE_NOT_IN_NFCORE_INBOX")
    for parent in (Path("/"), Path("/etc"), Path("/etc/nfcore"), INBOX_DIR):
        ensure_trusted_directory(parent)
    require(not source.is_symlink(), "NO_GO_SYMLINK")
    try:
        previous = source.lstat()
    except OSError:
        raise Denied("NO_GO_EXISTING_KEY_NOT_STAGED") from None
    require(stat.S_ISREG(previous.st_mode) and previous.st_uid == 0
            and stat.S_IMODE(previous.st_mode) == 0o600
            and previous.st_nlink == 1
            and 128 <= previous.st_size <= 65536,
            "NO_GO_CREDENTIAL_SOURCE_PERMISSIONS")
    try:
        fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
        try:
            current = os.fstat(fd)
            require((current.st_dev, current.st_ino) == (previous.st_dev, previous.st_ino),
                    "NO_GO_SOURCE_CHANGED")
            blob = os.read(fd, 65537)
            require(len(blob) == previous.st_size, "NO_GO_SOURCE_CHANGED")
        finally:
            os.close(fd)
    except OSError:
        raise Denied("NO_GO_UNREADABLE_EXISTING_KEY") from None
    return blob, parse_existing_identity(blob)


def atomic_write_new(path: Path, data: bytes, *, uid: int, gid: int) -> None:
    require(not path.exists() and not path.is_symlink(), "NO_GO_TARGET_EXISTS")
    fd, name = tempfile.mkstemp(prefix=".nfcore-stage-", dir=str(path.parent))
    try:
        os.fchmod(fd, 0o600)
        os.fchown(fd, uid, gid)
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        # Refuse to overwrite an existing key, configuration or symlink.
        os.link(name, path, follow_symlinks=False)
        os.unlink(name)
        directory_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("check", "stage"), required=True)
    parser.add_argument("--expected-production-sha", required=True)
    parser.add_argument("--existing-identity-file", type=Path, required=True)
    parser.add_argument("--iam-key-created-at", required=True,
                        help="Verified IAM creation timestamp, ISO8601 with timezone")
    args = parser.parse_args()
    try:
        check_host(args.expected_production_sha)
        raw, key_id = read_existing_identity(args.existing_identity_file)
        created, expiry = validate_created_at(args.iam_key_created_at)
        # fmadmin (1001) owns the host application directory on some installations.
        # The private key itself is staged ONLY under root-owned /etc/nfcore/worker.
        ensure_trusted_directory(PROD_DIR, allowed_owners=(0, 1001))
        ensure_trusted_directory(WORKER_DIR, required=False)
        for target in (TARGET_IDENTITY, WORKER_ENV, COMPOSE_ENV):
            require(not target.exists() and not target.is_symlink(),
                    "NO_GO_TARGET_ALREADY_CONFIGURED")
        env_data = render_env(key_id=key_id, created=created, expiry=expiry)
        compose_data = f"NFCORE_WORKER_IDENTITY_HOST_PATH={TARGET_IDENTITY}\n".encode()
        if args.mode == "check":
            print("EXISTING_GSM_IDENTITY_STAGE_PREFLIGHT_PASS")
            print("IAM_ACCESS_AND_WORKER_START_NOT_VERIFIED")
            return 0

        created_worker_dir = False
        created_files: list[Path] = []
        try:
            if not WORKER_DIR.exists():
                WORKER_DIR.mkdir(mode=0o700)
                created_worker_dir = True
            ensure_trusted_directory(WORKER_DIR)
            for target, payload, owner, group in (
                (TARGET_IDENTITY, raw, 10001, 10001),
                (WORKER_ENV, env_data, 1001, 1001),
                (COMPOSE_ENV, compose_data, 1001, 1001),
            ):
                atomic_write_new(target, payload, uid=owner, gid=group)
                created_files.append(target)
        except BaseException:
            for target in reversed(created_files):
                try:
                    target.unlink()
                except OSError:
                    pass
            if created_worker_dir:
                try:
                    WORKER_DIR.rmdir()
                except OSError:
                    pass
            raise
        print("GSM_EXISTING_IDENTITY_STAGED_NO_CONTAINER_STARTED")
        print("GSM_IAM_OUTBOX_RECOVERY_GATES_STILL_REQUIRED")
        return 0
    except Denied as exc:
        print(str(exc), file=sys.stderr)
        return 42


if __name__ == "__main__":
    raise SystemExit(main())
