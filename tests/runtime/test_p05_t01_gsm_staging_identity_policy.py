"""No-key tests for the staging Google Secret Manager workload identity guard."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import Mock

import pytest
from google.auth.credentials import AnonymousCredentials
from google.cloud import secretmanager_v1
from google.oauth2.service_account import Credentials as ServiceAccountCredentials

from kordena_fiscal.runtime.gsm_staging_identity_policy import (
    PROJECT_ID,
    WORKLOAD_IDENTITIES,
    build_staging_workload_gsm_access,
)
from kordena_fiscal.security.secrets import SecretResolutionError

NOW = datetime(2026, 10, 11, 18, 0, tzinfo=UTC)


def fake_identity(workload: str = "nfcore-api") -> ServiceAccountCredentials:
    identity = Mock(spec=ServiceAccountCredentials)
    identity.service_account_email = WORKLOAD_IDENTITIES[workload]
    identity.project_id = PROJECT_ID
    return identity


@pytest.mark.parametrize("workload", ["nfcore-api", "nfcore-worker"])
def test_approved_staging_identity_uses_canonical_sdk(monkeypatch, workload: str) -> None:
    client_factory = Mock()
    monkeypatch.setattr(secretmanager_v1, "SecretManagerServiceClient", client_factory)
    identity = fake_identity(workload)

    access = build_staging_workload_gsm_access(
        credentials=identity,
        workload_id=workload,  # type: ignore[arg-type]
        environment="staging",
        key_created_at=NOW - timedelta(days=1),
        key_not_after=NOW + timedelta(days=29),
        now=NOW,
    )

    assert access is not None
    client_factory.assert_called_once()
    assert client_factory.call_args.kwargs["credentials"] is identity
    assert client_factory.call_args.kwargs["client_options"]["api_endpoint"] == (
        "secretmanager.googleapis.com"
    )


@pytest.mark.parametrize(
    "change",
    [
        {"environment": "production"},
        {"environment": "development"},
        {"workload_id": "other"},
        {"workload_id": "nfcore-worker"},
        {"key_created_at": NOW + timedelta(seconds=1)},
        {"key_created_at": NOW - timedelta(days=31)},
        {"key_not_after": NOW},
        {"key_not_after": NOW + timedelta(days=31)},
        {"key_created_at": NOW.replace(tzinfo=None)},
        {"key_not_after": NOW.replace(tzinfo=None)},
        {"now": NOW.replace(tzinfo=None)},
    ],
)
def test_staging_identity_rejects_mismatch_before_sdk(monkeypatch, change: dict) -> None:
    client_factory = Mock()
    monkeypatch.setattr(secretmanager_v1, "SecretManagerServiceClient", client_factory)
    args = {
        "credentials": fake_identity(),
        "workload_id": "nfcore-api",
        "environment": "staging",
        "key_created_at": NOW,
        "key_not_after": NOW + timedelta(days=30),
        "now": NOW,
    }
    args.update(change)
    with pytest.raises(SecretResolutionError) as exc:
        build_staging_workload_gsm_access(**args)
    assert "private" not in str(exc.value).lower()
    assert exc.value.__cause__ is None
    client_factory.assert_not_called()


def test_staging_identity_rejects_unapproved_project_and_ambient_credentials(monkeypatch) -> None:
    client_factory = Mock()
    monkeypatch.setattr(secretmanager_v1, "SecretManagerServiceClient", client_factory)
    identity = fake_identity()
    identity.project_id = "different-project"
    for credentials in (identity, AnonymousCredentials()):
        with pytest.raises(SecretResolutionError):
            build_staging_workload_gsm_access(
                credentials=credentials,  # type: ignore[arg-type]
                workload_id="nfcore-api",
                environment="staging",
                key_created_at=NOW,
                key_not_after=NOW + timedelta(days=1),
                now=NOW,
            )
    client_factory.assert_not_called()
