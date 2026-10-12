"""P05 single-scope Worker GSM bootstrap: only real-scoped signing, never fallback."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import google_crc32c
import pytest

from kordena_fiscal.runtime import worker_staging_gsm_bootstrap as boot
from kordena_fiscal.runtime.config import RuntimeConfigurationError, RuntimeEnvironment
from kordena_fiscal.security.secret_binding import SecretBinding
from kordena_fiscal.security.secrets import SecretResolutionError
from kordena_fiscal.vault.google_secret_manager import GsmPayload, encode_gsm_envelope

RESOURCE = "projects/fm-nfcore-staging/secrets/nfcore-webhook-pilot"
REF = "sec_stagingWorkerSigningABC123"
NOW = datetime.now(UTC)


def _metadata(tmp_path: Path) -> dict[str, str]:
    file = tmp_path / "worker-key.json"
    file.write_bytes(b"x" * 256)
    file.chmod(0o600)
    return {
        "NFCORE_WORKER_GSM_MODE": "scoped-staging-sa-v1",
        "NFCORE_ENVIRONMENT": "staging",
        "NFCORE_WORKER_GSM_CREDENTIAL_FILE": str(file),
        "NFCORE_WORKER_GSM_KEY_CREATED_AT": (NOW - timedelta(days=1)).isoformat(),
        "NFCORE_WORKER_GSM_KEY_NOT_AFTER": (NOW + timedelta(days=10)).isoformat(),
        "NFCORE_WORKER_GSM_TENANT_ID": "pilot-tenant",
        "NFCORE_WORKER_GSM_UNIT_ID": "pilot-unit",
        "NFCORE_WORKER_GSM_SIGNING_REFERENCE": REF,
        "NFCORE_WORKER_GSM_SIGNING_VERSION": "1",
        "NFCORE_WORKER_GSM_PROVIDER_ID": "webhook",
        "NFCORE_WORKER_GSM_DESTINATION_ID": "events",
        "NFCORE_WORKER_GSM_RESOURCE": RESOURCE,
    }


def _binding(**overrides: object) -> SecretBinding:
    defaults = {
        "reference_id": REF,
        "tenant_id": "pilot-tenant",
        "unit_id": "pilot-unit",
        "purpose": "webhook-signing",
        "runtime_environment": "staging",
        "fiscal_environment": None,
        "provider_id": "webhook",
        "workload_id": "nfcore-worker",
        "kind": "signature",
        "canonical_version": 1,
        "resource": RESOURCE,
        "cloud_version": "2",
        "revision": 1,
    }
    defaults.update(overrides)
    return SecretBinding(**defaults)  # type: ignore[arg-type]


class _FakeDb:
    def __init__(self, binding: SecretBinding | None) -> None:
        self.binding = binding
        self.reads = 0

    @contextmanager
    def __call__(self):
        self.reads += 1
        yield SimpleNamespace(secret_bindings=SimpleNamespace(get=lambda _ref: self.binding))


def test_no_opt_in_never_constructs_handlers() -> None:
    assert boot.staging_gsm_handler_factory({}) is None


@pytest.mark.parametrize(
    ("key", "bad"),
    [
        ("NFCORE_WORKER_GSM_MODE", "anything-else"),
        ("NFCORE_ENVIRONMENT", "production"),
        ("NFCORE_WORKER_GSM_UNIT_ID", "*"),
        ("NFCORE_WORKER_GSM_RESOURCE", "projects/other-project/secrets/s"),
        ("NFCORE_WORKER_GSM_SIGNING_REFERENCE", "tenant-controlled"),
        ("NFCORE_WORKER_GSM_SIGNING_VERSION", "0"),
    ],
)
def test_invalid_metadata_blocks_before_db(tmp_path: Path, key: str, bad: str) -> None:
    metadata = _metadata(tmp_path)
    metadata[key] = bad
    with pytest.raises((RuntimeConfigurationError, SecretResolutionError)):
        boot.staging_gsm_handler_factory(metadata)


def test_world_readable_identity_rejected(tmp_path: Path) -> None:
    metadata = _metadata(tmp_path)
    Path(metadata["NFCORE_WORKER_GSM_CREDENTIAL_FILE"]).chmod(0o644)
    with pytest.raises(RuntimeConfigurationError, match="not private"):
        boot.staging_gsm_handler_factory(metadata)


def test_missing_binding_blocks_before_identity_access(monkeypatch, tmp_path: Path) -> None:
    factory = boot.staging_gsm_handler_factory(_metadata(tmp_path))
    assert factory is not None
    db = _FakeDb(None)
    monkeypatch.setattr(
        boot.ServiceAccountCredentials, "from_service_account_file",
        lambda path: pytest.fail("identity must not be loaded"),
    )
    with pytest.raises(RuntimeConfigurationError, match="durable signing binding unavailable"):
        factory(db, SimpleNamespace(environment=RuntimeEnvironment.STAGING))
    assert db.reads == 1


@pytest.mark.parametrize(
    "override",
    [
        {"state": "revoked"},
        {"tenant_id": "other-tenant"},
        {"unit_id": "other-unit"},
        {"workload_id": "nfcore-api"},
        {"canonical_version": 2},
        {"resource": "projects/fm-nfcore-staging/secrets/other"},
    ],
)
def test_wrong_durable_binding_blocks_before_key_access(
    monkeypatch, tmp_path: Path, override: dict[str, object],
) -> None:
    factory = boot.staging_gsm_handler_factory(_metadata(tmp_path))
    assert factory is not None
    monkeypatch.setattr(
        boot.ServiceAccountCredentials, "from_service_account_file",
        lambda path: pytest.fail("invalid binding must not load identity"),
    )
    with pytest.raises(RuntimeConfigurationError, match="binding unavailable"):
        factory(
            _FakeDb(_binding(**override)), SimpleNamespace(environment=RuntimeEnvironment.STAGING)
        )


def test_actual_secret_resolution_is_required_before_handlers(
    monkeypatch, tmp_path: Path,
) -> None:
    factory = boot.staging_gsm_handler_factory(_metadata(tmp_path))
    assert factory is not None
    fake_credentials = object()
    monkeypatch.setattr(
        boot.ServiceAccountCredentials,
        "from_service_account_file",
        lambda _: fake_credentials,
    )
    monkeypatch.setattr(
        boot, "build_staging_workload_gsm_access",
        lambda **kwargs: access,
    )
    binding = _binding()
    payload = encode_gsm_envelope(binding, b"synthetic-test-key-not-cloud")
    access = SimpleNamespace(
        access=Mock(return_value=GsmPayload(
            name=binding.version_name,
            data=payload,
            crc32c=google_crc32c.value(payload),
        ))
    )
    db = _FakeDb(binding)
    handlers = factory(db, SimpleNamespace(environment=RuntimeEnvironment.STAGING))
    assert set(handlers) == {"deliver_webhook"}
    assert access.access.call_count == 1
    assert db.reads >= 2
    # Only authorized configuration can use a real handler. No fake delivery occurs.


def test_invalid_cloud_payload_prevents_worker_readiness(monkeypatch, tmp_path: Path) -> None:
    factory = boot.staging_gsm_handler_factory(_metadata(tmp_path))
    assert factory is not None
    monkeypatch.setattr(
        boot.ServiceAccountCredentials,
        "from_service_account_file",
        lambda _: object(),
    )
    monkeypatch.setattr(
        boot, "build_staging_workload_gsm_access",
        lambda **kwargs: SimpleNamespace(
            access=lambda name: GsmPayload(name, b"corrupt", 0)
        ),
    )
    with pytest.raises(SecretResolutionError):
        factory(_FakeDb(_binding()), SimpleNamespace(environment=RuntimeEnvironment.STAGING))
