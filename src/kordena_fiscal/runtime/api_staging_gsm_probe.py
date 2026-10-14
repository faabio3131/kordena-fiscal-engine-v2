"""Optional dedicated GSM verifier for the signed staging HTTP probe.

The API and Worker use distinct service accounts and distinct durable bindings
for the same pinned signing secret. Missing or invalid opt-in fails closed.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import cast

from google.oauth2.service_account import Credentials as ServiceAccountCredentials

from kordena_fiscal.persistence.postgres import PostgresFiscalDatabase
from kordena_fiscal.security.s2s import WebhookSecurity
from kordena_fiscal.security.secrets import SecretReference, SecretResolver, SecretScope
from kordena_fiscal.vault.google_secret_manager import (
    DurableGsmReader,
    GoogleSignatureSecretBackend,
)

from .config import RuntimeConfigurationError
from .gsm_staging_identity_policy import (
    PROJECT_ID,
    PROJECT_NUMBERS,
    WORKLOAD_IDENTITIES,
    build_staging_workload_gsm_access,
)

_SIGNING_REFERENCE = "sec_nfcore_staging_pilot_gsm_signing_01"
_VERIFY_REFERENCE = "sec_nfcore_staging_pilot_gsm_verify_01"
_RESOURCE = "projects/fm-nfcore-staging/secrets/nfcore-stg-pilot-webhook-signing"
_PROVIDER = "google-secret-manager"
_TENANT = "nfcore-staging-e2e"
_UNIT = "pilot-gsm-staging"
_JSON_FIELD = "NFCORE_API_GSM_CREDENTIAL_JSON"
_MODE = "scoped-staging-sa-v1"


class _VerifierKeyResolver:
    def __init__(self, resolver: SecretResolver) -> None:
        self._resolver = resolver
        self._reference = SecretReference(_VERIFY_REFERENCE, 1)
        self._scope = SecretScope(_TENANT, _UNIT, "webhook-signing")

    def resolve(self, key_id: str) -> bytes | None:
        if key_id != _SIGNING_REFERENCE:
            return None
        with self._resolver.resolve(self._reference, scope=self._scope) as material:
            return material.reveal()


def _timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.utcoffset() is None:
        raise ValueError("timezone required")
    return parsed


def _credentials(raw: str, key_id: str) -> ServiceAccountCredentials:
    if not 128 <= len(raw.encode("utf-8")) <= 65536:
        raise ValueError("invalid credential size")

    def unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate credential field")
            result[key] = value
        return result

    info = json.loads(raw, object_pairs_hook=unique)
    if not isinstance(info, dict) or any(not isinstance(v, str) for v in info.values()):
        raise ValueError("invalid credential format")
    required = {
        "type", "project_id", "private_key_id", "private_key",
        "client_email", "token_uri",
    }
    allowed = required | {
        "client_id", "auth_uri", "auth_provider_x509_cert_url",
        "client_x509_cert_url", "universe_domain",
    }
    if (
        not required.issubset(info)
        or not set(info).issubset(allowed)
        or info["type"] != "service_account"
        or info["project_id"] != PROJECT_ID
        or info["client_email"] != WORKLOAD_IDENTITIES["nfcore-api"]
        or info["token_uri"] != "https://oauth2.googleapis.com/token"
        or info.get("universe_domain", "googleapis.com") != "googleapis.com"
        or not re.fullmatch(r"[a-f0-9]{40}", key_id)
        or info["private_key_id"] != key_id
    ):
        raise ValueError("credential identity denied")
    loader = cast(
        Callable[[dict[str, str]], ServiceAccountCredentials],
        ServiceAccountCredentials.from_service_account_info,
    )
    return loader(info)


def staging_probe_verifier(
    database: PostgresFiscalDatabase,
    environ: Mapping[str, str] | None = None,
) -> WebhookSecurity | None:
    source = os.environ if environ is None else environ
    mode = source.get("NFCORE_API_GSM_MODE", "").strip()
    if not mode:
        return None
    if mode != _MODE or source.get("NFCORE_ENVIRONMENT") != "staging":
        raise RuntimeConfigurationError("staging verifier mode denied")
    required = (
        "NFCORE_API_GSM_KEY_ID",
        "NFCORE_API_GSM_KEY_CREATED_AT",
        "NFCORE_API_GSM_KEY_NOT_AFTER",
        _JSON_FIELD,
    )
    if any(not source.get(name) for name in required):
        raise RuntimeConfigurationError("staging verifier identity incomplete")
    phase = "DATABASE_READ"
    try:
        with database() as uow:
            binding = uow.secret_bindings.get(_VERIFY_REFERENCE)
        phase = "BINDING_CONTRACT"
        if (
            binding is None
            or binding.tenant_id != _TENANT
            or binding.unit_id != _UNIT
            or binding.purpose != "webhook-signing"
            or binding.runtime_environment != "staging"
            or binding.fiscal_environment is not None
            or binding.workload_id != "nfcore-api"
            or binding.kind != "signature"
            or binding.provider_id != _PROVIDER
            or binding.canonical_version != 1
            or binding.cloud_version != "2"
            or binding.resource != _RESOURCE
            or binding.state != "active"
            or (binding.not_after is not None and binding.not_after <= datetime.now(UTC))
        ):
            raise ValueError("verifier binding unavailable")
        phase = "SERVICE_ACCOUNT_CREDENTIALS"
        credentials = _credentials(
            source[_JSON_FIELD], source["NFCORE_API_GSM_KEY_ID"]
        )
        phase = "ROTATION_POLICY_OR_CLIENT"
        access = build_staging_workload_gsm_access(
            credentials=credentials,
            workload_id="nfcore-api",
            environment="staging",
            key_created_at=_timestamp(source["NFCORE_API_GSM_KEY_CREATED_AT"]),
            key_not_after=_timestamp(source["NFCORE_API_GSM_KEY_NOT_AFTER"]),
        )
        phase = "RESOLVER_COMPOSITION"
        reader = DurableGsmReader(
            uow_factory=database,
            access=access,
            environment="staging",
            workload_id="nfcore-api",
            allowed_resources=frozenset({_RESOURCE}),
            project_numbers=PROJECT_NUMBERS,
        )
        resolver = SecretResolver(
            GoogleSignatureSecretBackend(reader, provider_id=_PROVIDER),
            environment="staging",
        )
        phase = "GSM_SECRET_READ_OR_ENVELOPE"
        # Require actual GSM permission and correct binding before declaring ready.
        with resolver.resolve(
            SecretReference(_VERIFY_REFERENCE, 1),
            scope=SecretScope(_TENANT, _UNIT, "webhook-signing"),
        ):
            pass
    except Exception:
        # Only this finite phase label is exposed. Never log credentials, tokens,
        # exception messages, cloud payloads, tenant identifiers, or key material.
        raise RuntimeConfigurationError(
            f"staging GSM verifier unavailable [{phase}]"
        ) from None
    return WebhookSecurity(
        key_resolver=_VerifierKeyResolver(resolver),
        signing_key_id=_SIGNING_REFERENCE,
    )
