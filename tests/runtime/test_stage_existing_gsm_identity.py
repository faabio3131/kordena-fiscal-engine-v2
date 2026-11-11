"""Offline security contract tests for the NFCore existing-GSM-key stager.

No real GCP key, VPS connection, IAM write, container startup or DDL.
"""
from __future__ import annotations

import importlib.util
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

SCRIPT = Path(__file__).parents[2] / "deploy/contabo/stage-existing-gsm-identity.py"
SPEC = importlib.util.spec_from_file_location("stage_existing_gsm_identity", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
stager = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stager)


def _synthetic_key(**updates: str) -> bytes:
    key_type = "PRIVATE " + "KEY"
    example = {
        "type": "service_account",
        "project_id": "fm-nfcore-prod",
        "private_key_id": "a" * 40,
        "private_key": (
            f"-----BEGIN {key_type}-----\n"
            "synthetic-nonfunctional\n"
            f"-----END {key_type}-----\n"
        ),
        "client_email": "nfcore-worker@fm-nfcore-prod.iam.gserviceaccount.com",
        "token_uri": "https://oauth2.googleapis.com/token",
    }
    example.update(updates)
    return json.dumps(example).encode()


def test_only_existing_exact_worker_identity_is_recognized() -> None:
    assert stager.parse_existing_identity(_synthetic_key()) == "a" * 40


@pytest.mark.parametrize(
    "change",
    [
        {"project_id": "wrong-project"},
        {"client_email": "nfcore-api@fm-nfcore-prod.iam.gserviceaccount.com"},
        {"token_uri": "https://invalid.example/token"},
        {"private_key_id": "broken"},
        {"private_key": "not-a-key"},
        {"type": "authorized_user"},
    ],
)
def test_wrong_identity_fails_closed(change: dict[str, str]) -> None:
    with pytest.raises(stager.Denied):
        stager.parse_existing_identity(_synthetic_key(**change))


def test_duplicate_json_key_is_rejected() -> None:
    source = _synthetic_key().decode()[:-1] + ', "private_key_id": "' + "b" * 40 + '"}'
    with pytest.raises(stager.Denied):
        stager.parse_existing_identity(source.encode())


def test_source_must_be_in_nfcore_inbox_not_other_saas(tmp_path: Path) -> None:
    with pytest.raises(stager.Denied, match="NO_GO_SOURCE_NOT_IN_NFCORE_INBOX"):
        stager.read_existing_identity(tmp_path / "any.json")


def test_key_lifecycle_is_bounded_to_90_days() -> None:
    now = datetime(2026, 11, 11, 12, tzinfo=UTC)
    created = now - timedelta(days=25)
    start, end = stager.validate_created_at(created.isoformat(), now=now)
    assert datetime.fromisoformat(end) - datetime.fromisoformat(start) == timedelta(days=90)
    for invalid in (now + timedelta(seconds=1), now - timedelta(days=91)):
        with pytest.raises(stager.Denied):
            stager.validate_created_at(invalid.isoformat(), now=now)
    with pytest.raises(stager.Denied):
        stager.validate_created_at("2026-11-10T12:00:00", now=now)


def test_multi_tenant_env_contains_no_private_material_or_fake_scopes() -> None:
    env = stager.render_env(
        key_id="c" * 40,
        created="2026-11-10T12:00:00+00:00",
        expiry="2027-02-08T12:00:00+00:00",
    ).decode()
    assert "NFCORE_WORKER_GSM_MODE=multi-tenant-production-sa-v1" in env
    assert "NFCORE_GSM_PROJECT_NUMBER=646230745113" in env
    assert "NFCORE_WORKER_GSM_HOST_NAMESPACE=nfcore" in env
    assert "NFCORE_PUBLIC_HOSTNAME=api.nfcore.com.br" in env
    assert "NFCORE_ALLOWED_ORIGINS=https://app.nfcore.com.br" in env
    assert "NFCORE_REQUIRE_HTTPS=true" in env
    assert "NFCORE_WORKER_GSM_TENANT_ID" not in env
    assert "NFCORE_WORKER_GSM_UNIT_ID" not in env
    assert "GOOGLE_APPLICATION_CREDENTIALS" not in env
    assert "CREDENTIAL_JSON" not in env
    assert "private_key" not in env


def test_root_required_before_any_io() -> None:
    with patch.object(stager.os, "geteuid", return_value=1001):
        with pytest.raises(stager.Denied, match="NO_GO_ROOT_REQUIRED"):
            stager.check_host("a" * 40)


def test_no_fallback_to_railway_credential_env_or_other_saas() -> None:
    body = SCRIPT.read_text(encoding="utf-8")
    assert "NFCORE_WORKER_GSM_CREDENTIAL_JSON" not in body
    assert "CREDENTIAL_FILE" not in body or "json" in body.lower()
    assert "NFCORE_WORKER_GSM_MODE" in body
    assert "/etc/nfcore/incoming" in body
    assert "docker compose up" not in body
    assert "railway" not in body.lower()


def test_staged_multi_tenant_environment_passes_canonical_production_profile() -> None:
    from kordena_fiscal.runtime.config import RuntimeSettings

    env_bytes = stager.render_env(
        key_id="c" * 40,
        created="2026-11-10T12:00:00+00:00",
        expiry="2027-02-08T12:00:00+00:00",
    )
    fields = dict(line.split("=", 1) for line in env_bytes.decode().strip().splitlines())
    fields.update(
        {
            "NFCORE_ENVIRONMENT": "production",
            "NFCORE_PERSISTENCE_BACKEND": "postgres",
            "NFCORE_SECRET_BACKEND": "external",
            "DATABASE_URL": "postgresql://ci-nfcore@localhost/ci_db",
        }
    )
    settings = RuntimeSettings.from_mapping(fields)
    assert settings.require_https is True
    assert settings.public_hostname == "api.nfcore.com.br"
    assert settings.environment.value == "production"



def test_exclusive_stage_file_rolls_back_if_post_link_fsync_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A crash or storage error after creating the target cannot strand a key."""
    target = tmp_path / "worker-identity.json"
    genuine_fsync = os.fsync
    calls = 0

    def failing_fsync(fd: int) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("synthetic directory sync failure")
        genuine_fsync(fd)

    monkeypatch.setattr(stager.os, "fsync", failing_fsync)
    with pytest.raises(OSError, match="synthetic directory sync failure"):
        stager.atomic_write_new(
            target, b"synthetic-not-a-key", uid=os.getuid(), gid=os.getgid(),
        )
    assert calls == 2
    assert not target.exists()
    assert list(tmp_path.iterdir()) == []


def test_exclusive_stage_file_never_overwrites_existing_target(tmp_path: Path) -> None:
    target = tmp_path / "worker-identity.json"
    target.write_bytes(b"existing-private-file-must-be-preserved")
    target.chmod(0o600)
    with pytest.raises(stager.Denied, match="NO_GO_TARGET_EXISTS"):
        stager.atomic_write_new(
            target, b"replacement-denied", uid=os.getuid(), gid=os.getgid(),
        )
    assert target.read_bytes() == b"existing-private-file-must-be-preserved"
    assert list(tmp_path.iterdir()) == [target]



def test_private_gsm_credential_directories_require_mode_0700(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    folder = tmp_path / "inbox"
    folder.mkdir(mode=0o700)
    # Ownership is checked by ensure_trusted_directory in production;
    # isolate the restrictive directory-mode invariant for a test runner UID.
    monkeypatch.setattr(
        stager, "ensure_trusted_directory", lambda _folder: None,
    )
    stager.ensure_private_root_directory(folder)
    folder.chmod(0o755)
    with pytest.raises(stager.Denied, match="NO_GO_PRIVATE_DIRECTORY_PERMISSIONS"):
        stager.ensure_private_root_directory(folder)
    folder.chmod(0o770)
    with pytest.raises(stager.Denied, match="NO_GO_PRIVATE_DIRECTORY_PERMISSIONS"):
        stager.ensure_private_root_directory(folder)
