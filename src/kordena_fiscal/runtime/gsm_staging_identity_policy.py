"""Staging-only metadata guard for an explicitly supplied GSM workload identity.

This component never parses credential files, reads private keys or discovers
ambient credentials. It only validates the preexisting SDK identity before
delegating to the canonical GSM adapter.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Literal

from google.oauth2.service_account import Credentials as ServiceAccountCredentials

from kordena_fiscal.security.secrets import SecretResolutionError
from kordena_fiscal.vault.google_secret_manager import (
    GoogleSdkSecretAccess,
    build_google_sdk_access,
)

PROJECT_ID = "fm-nfcore-staging"
# Number Google echoes for this project in AccessSecretVersion names (observed via
# `gcloud secrets versions describe`). Pinned: no other project number is equivalent.
PROJECT_NUMBER = "672015004427"
PROJECT_NUMBERS = {PROJECT_ID: PROJECT_NUMBER}
WORKLOAD_IDENTITIES = {
    "nfcore-api": "nfcore-stg-api@fm-nfcore-staging.iam.gserviceaccount.com",
    "nfcore-worker": "nfcore-stg-worker@fm-nfcore-staging.iam.gserviceaccount.com",
}


def build_staging_workload_gsm_access(
    *,
    credentials: ServiceAccountCredentials,
    workload_id: Literal["nfcore-api", "nfcore-worker"],
    environment: str,
    key_created_at: datetime,
    key_not_after: datetime,
    now: datetime | None = None,
) -> GoogleSdkSecretAccess:
    """Validate identity + operator-supplied rotation metadata, without handling keys.

    The creation time and key identifier must also be reconciled with Google IAM
    by the approved external operator. This check alone does not prove key age.
    """
    current = now or datetime.now(UTC)
    expected_email = WORKLOAD_IDENTITIES.get(workload_id)
    if (
        environment != "staging"
        or expected_email is None
        or not isinstance(credentials, ServiceAccountCredentials)
        or credentials.service_account_email != expected_email
        or credentials.project_id != PROJECT_ID
    ):
        raise SecretResolutionError("GSM staging workload identity unavailable")
    if any(
        not isinstance(value, datetime) or value.utcoffset() is None
        for value in (key_created_at, key_not_after, current)
    ):
        raise SecretResolutionError("GSM staging rotation metadata invalid")
    if not (
        key_created_at <= current < key_not_after
        and key_not_after <= key_created_at + timedelta(days=30)
    ):
        raise SecretResolutionError("GSM staging rotation window invalid")
    return build_google_sdk_access(
        credentials=credentials,
        environment="staging",
        bootstrap_not_after=key_not_after,
        now=current,
    )
