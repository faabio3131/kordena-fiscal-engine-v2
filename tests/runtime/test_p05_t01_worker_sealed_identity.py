"""Synthetic SDK credentials; these tests never contact Google or Railway."""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import google_crc32c
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from kordena_fiscal.runtime import worker_staging_gsm_bootstrap as boot
from kordena_fiscal.runtime.config import RuntimeConfigurationError, RuntimeEnvironment
from kordena_fiscal.vault.google_secret_manager import GsmPayload, encode_gsm_envelope
from tests.runtime.test_p05_t01_worker_staging_gsm_bootstrap import _binding, _FakeDb, _metadata

KEY_ID = "a" * 40


@pytest.fixture(scope="module")
def identity():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return {
        "type": "service_account", "project_id": "fm-nfcore-staging",
        "private_key_id": KEY_ID,
        "private_key": key.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ).decode(),
        "client_email": "nfcore-stg-worker@fm-nfcore-staging.iam.gserviceaccount.com",
        "token_uri": "https://oauth2.googleapis.com/token",
        "universe_domain": "googleapis.com",
    }


def _sealed(tmp_path, raw):
    metadata = _metadata(tmp_path)
    metadata.pop(boot._FILE_ENV)
    metadata[boot._JSON_ENV] = raw
    metadata[boot._KEY_ID_ENV] = KEY_ID
    return metadata


def test_memory_loader_uses_real_sdk(identity, monkeypatch):
    monkeypatch.setattr(boot.ServiceAccountCredentials, "from_service_account_file",
                        lambda *_: pytest.fail("sealed identity must not touch a file"))
    credentials = boot._memory_credentials(json.dumps(identity), key_id=KEY_ID)
    assert credentials.service_account_email == identity["client_email"]
    assert credentials.project_id == identity["project_id"]
    assert credentials.signer.key_id == KEY_ID


@pytest.mark.parametrize(("field", "value"), [
    ("type", "authorized_user"), ("type", "external_account"),
    ("project_id", "other-project"), ("client_email", "nfcore-stg-api@example.test"),
    ("token_uri", "https://attacker.invalid/token"),
    ("universe_domain", "attacker.invalid"), ("private_key_id", "b" * 40),
    ("private_key", "sensitive-invalid-key"), ("client_id", 123),
    ("credential_source", {"file": "arbitrary"}),
])
def test_rejects_unapproved_formats_without_sdk_network(identity, field, value):
    altered = dict(identity, **{field: value})
    with pytest.raises((ValueError, TypeError)):
        boot._memory_credentials(json.dumps(altered), key_id=KEY_ID)


@pytest.mark.parametrize("raw", ["{}", "[]", "null", "x" * 65537,
                                    '{"type":"service_account","type":"service_account"}'])
def test_rejects_invalid_json(raw):
    with pytest.raises((ValueError, TypeError)):
        boot._memory_credentials(raw, key_id=KEY_ID)


def test_identity_sources_are_exclusive(tmp_path, identity):
    metadata = _metadata(tmp_path)
    metadata[boot._JSON_ENV] = json.dumps(identity)
    with pytest.raises(RuntimeConfigurationError, match="exactly one"):
        boot.staging_gsm_handler_factory(metadata)
    metadata.pop(boot._JSON_ENV)
    metadata.pop(boot._FILE_ENV)
    with pytest.raises(RuntimeConfigurationError, match="exactly one"):
        boot.staging_gsm_handler_factory(metadata)


def test_sealed_requires_iam_key_id(tmp_path, identity):
    metadata = _sealed(tmp_path, json.dumps(identity))
    metadata.pop(boot._KEY_ID_ENV)
    with pytest.raises(RuntimeConfigurationError, match="identifier required"):
        boot.staging_gsm_handler_factory(metadata)


def test_binding_checked_before_json_parse(tmp_path, monkeypatch):
    factory = boot.staging_gsm_handler_factory(_sealed(tmp_path, "sensitive-invalid-json"))
    monkeypatch.setattr(boot, "_memory_credentials", lambda *_args, **_kw:
                        pytest.fail("binding must be checked first"))
    with pytest.raises(RuntimeConfigurationError, match="binding unavailable"):
        factory(_FakeDb(None), SimpleNamespace(environment=RuntimeEnvironment.STAGING))


def test_identity_error_is_sanitized(tmp_path):
    factory = boot.staging_gsm_handler_factory(_sealed(tmp_path, "sensitive-invalid-json"))
    with pytest.raises(RuntimeConfigurationError) as caught:
        factory(_FakeDb(_binding()), SimpleNamespace(environment=RuntimeEnvironment.STAGING))
    assert str(caught.value) == "worker GSM approved identity unavailable"
    assert caught.value.__suppress_context__


def test_sealed_process_env_consumed_and_real_gsm_read_required(
    tmp_path, identity, monkeypatch,
):
    metadata = _sealed(tmp_path, json.dumps(identity))
    for name, value in metadata.items():
        monkeypatch.setenv(name, value)
    monkeypatch.delenv(boot._FILE_ENV, raising=False)
    binding = _binding()
    envelope = encode_gsm_envelope(binding, b"synthetic-signing-key")
    access = SimpleNamespace(access=Mock(return_value=GsmPayload(
        binding.version_name, envelope, google_crc32c.value(envelope),
    )))
    seen = []

    def approve(**kwargs):
        seen.append(kwargs["credentials"])
        return access

    monkeypatch.setattr(boot, "build_staging_workload_gsm_access", approve)
    factory = boot.staging_gsm_handler_factory()
    handlers = factory(_FakeDb(binding), SimpleNamespace(environment=RuntimeEnvironment.STAGING))
    assert boot._JSON_ENV not in boot.os.environ
    assert seen[0].signer.key_id == KEY_ID
    assert access.access.call_count == 1
    assert set(handlers.handlers) == {"deliver_webhook"}
    assert handlers.claim_selection.scope.tenant_id == "pilot-tenant"


@pytest.mark.parametrize("deadline", [-1, 31])
def test_sealed_preserves_existing_rotation_authority(tmp_path, identity, deadline):
    metadata = _sealed(tmp_path, json.dumps(identity))
    now = datetime.now(UTC)
    metadata["NFCORE_WORKER_GSM_KEY_CREATED_AT"] = (now-timedelta(hours=1)).isoformat()
    metadata["NFCORE_WORKER_GSM_KEY_NOT_AFTER"] = (now+timedelta(days=deadline)).isoformat()
    factory = boot.staging_gsm_handler_factory(metadata)
    with pytest.raises(RuntimeConfigurationError, match="approved identity unavailable"):
        factory(_FakeDb(_binding()), SimpleNamespace(environment=RuntimeEnvironment.STAGING))
