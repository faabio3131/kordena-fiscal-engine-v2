"""Explicit staging-only GSM composition for the existing canonical outbox Worker.

No tenant or signing authority comes from an outbox payload. This is a *single
pre-approved pilot scope*, not a multi-tenant dynamic signing registry. A broader
Worker must not treat this limited composition as full commercial readiness.
No service-account key, raw secret or custom handler is stored in this module.
"""
from __future__ import annotations

import json
import os
import re
import stat
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from google.oauth2.service_account import Credentials as ServiceAccountCredentials

from kordena_fiscal.contingency.outbox import OutboxClaimSelection
from kordena_fiscal.domain import ExecutionScope, FiscalEnvironment
from kordena_fiscal.persistence.postgres import PostgresFiscalDatabase
from kordena_fiscal.security.secrets import SecretReference, SecretResolver, SecretScope
from kordena_fiscal.vault.google_secret_manager import (
    DurableGsmReader,
    GoogleSignatureSecretBackend,
)

from .config import RuntimeConfigurationError, RuntimeEnvironment, RuntimeSettings
from .gsm_staging_identity_policy import (
    PROJECT_ID,
    WORKLOAD_IDENTITIES,
    build_staging_workload_gsm_access,
)
from .observability import StructuredLogger
from .secret_manager import build_gsm_worker_webhook_dependencies
from .worker_composition import (
    DELIVER_WEBHOOK_OPERATION,
    ScopedWorkerHandlerComposition,
    build_canonical_worker_handlers,
)

_RESOURCE = re.compile(r"projects/fm-nfcore-staging/secrets/[A-Za-z0-9_-]{1,255}\Z")
_MODE = "scoped-staging-sa-v1"
_JSON_ENV = "NFCORE_WORKER_GSM_CREDENTIAL_JSON"
_FILE_ENV = "NFCORE_WORKER_GSM_CREDENTIAL_FILE"
_KEY_ID_ENV = "NFCORE_WORKER_GSM_KEY_ID"
_ENV_FIELDS = (
    "NFCORE_WORKER_GSM_KEY_CREATED_AT",
    "NFCORE_WORKER_GSM_KEY_NOT_AFTER",
    "NFCORE_WORKER_GSM_TENANT_ID",
    "NFCORE_WORKER_GSM_UNIT_ID",
    "NFCORE_WORKER_GSM_HOST_NAMESPACE",
    "NFCORE_WORKER_GSM_SIGNING_REFERENCE",
    "NFCORE_WORKER_GSM_SIGNING_VERSION",
    "NFCORE_WORKER_GSM_PROVIDER_ID",
    "NFCORE_WORKER_GSM_DESTINATION_ID",
    "NFCORE_WORKER_GSM_RESOURCE",
)


def _unique_fields(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate identity field")
        result[key] = value
    return result


def _memory_credentials(raw: str, *, key_id: str) -> ServiceAccountCredentials:
    """Parse only the pinned Google SA format, never ADC or arbitrary token URLs.

    Caller sanitizes exceptions. No disk write; Python/SDK signer memory cannot
    promise complete zeroization. IAM key expiry is independently reconciled.
    """
    if not 128 <= len(raw.encode("utf-8")) <= 64 * 1024:
        raise ValueError("identity size invalid")
    info = json.loads(raw, object_pairs_hook=_unique_fields)
    if not isinstance(info, dict) or any(not isinstance(v, str) for v in info.values()):
        raise ValueError("identity format invalid")
    required = {"type", "project_id", "private_key_id", "private_key", "client_email",
                "token_uri"}
    allowed = required | {"client_id", "auth_uri", "auth_provider_x509_cert_url",
                          "client_x509_cert_url", "universe_domain"}
    if (
        not required.issubset(info)
        or not set(info).issubset(allowed)
        or info["type"] != "service_account"
        or info["project_id"] != PROJECT_ID
        or info["client_email"] != WORKLOAD_IDENTITIES["nfcore-worker"]
        or info["token_uri"] != "https://oauth2.googleapis.com/token"
        or info.get("universe_domain", "googleapis.com") != "googleapis.com"
        or not re.fullmatch(r"[a-f0-9]{40}", key_id)
        or info["private_key_id"] != key_id
    ):
        raise ValueError("identity not pinned")
    loader = cast(
        Callable[[dict[str, str]], ServiceAccountCredentials],
        ServiceAccountCredentials.from_service_account_info,
    )
    return loader(info)


def _private_file(path: str) -> Path:
    file = Path(path)
    try:
        info = file.lstat()
        if (
            not file.is_absolute()
            or not stat.S_ISREG(info.st_mode)
            or info.st_mode & 0o077
            or info.st_uid != os.getuid()
            or info.st_size > 64 * 1024
            or info.st_size < 128
        ):
            raise RuntimeConfigurationError("worker GSM identity file is not private")
    except OSError:
        raise RuntimeConfigurationError("worker GSM identity file unavailable") from None
    return file


def _timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        raise RuntimeConfigurationError("worker GSM identity rotation metadata invalid") from None
    if parsed.utcoffset() is None:
        raise RuntimeConfigurationError("worker GSM identity rotation metadata invalid")
    return parsed


def staging_gsm_handler_factory(
    environ: Mapping[str, str] | None = None,
) -> Callable[[PostgresFiscalDatabase, RuntimeSettings], ScopedWorkerHandlerComposition] | None:
    """Fixed canonical composition selected by an explicit, exact staging opt-in."""
    source = os.environ if environ is None else environ
    # Do not copy/retain the raw sealed value in the composition's metadata.
    values = {key: value for key, value in source.items() if key != _JSON_ENV}
    mode = values.get("NFCORE_WORKER_GSM_MODE", "").strip()
    if not mode:
        return None
    if mode != _MODE or values.get("NFCORE_ENVIRONMENT") != "staging":
        raise RuntimeConfigurationError("worker GSM composition not approved for environment")
    if any(not values.get(name) or values[name] != values[name].strip() for name in _ENV_FIELDS):
        raise RuntimeConfigurationError("worker GSM composition metadata incomplete")
    if values["NFCORE_WORKER_GSM_UNIT_ID"] == "*":
        raise RuntimeConfigurationError("worker GSM wildcard scope prohibited")
    resource = values["NFCORE_WORKER_GSM_RESOURCE"]
    if not _RESOURCE.fullmatch(resource):
        raise RuntimeConfigurationError("worker GSM resource not allowlisted")
    has_json = bool(source.get(_JSON_ENV))
    has_file = bool(values.get(_FILE_ENV))
    if has_json == has_file:
        raise RuntimeConfigurationError("worker GSM requires exactly one identity source")
    file = _private_file(values[_FILE_ENV]) if has_file else None
    key_id = values.get(_KEY_ID_ENV, "")
    if has_json and not re.fullmatch(r"[a-f0-9]{40}", key_id):
        raise RuntimeConfigurationError("worker GSM IAM key identifier required")
    created_at = _timestamp(values["NFCORE_WORKER_GSM_KEY_CREATED_AT"])
    not_after = _timestamp(values["NFCORE_WORKER_GSM_KEY_NOT_AFTER"])
    try:
        version = int(values["NFCORE_WORKER_GSM_SIGNING_VERSION"])
        reference = SecretReference(values["NFCORE_WORKER_GSM_SIGNING_REFERENCE"], version)
        scope = SecretScope(
            values["NFCORE_WORKER_GSM_TENANT_ID"],
            values["NFCORE_WORKER_GSM_UNIT_ID"],
            "webhook-signing",
        )
        selection = OutboxClaimSelection(
            scope=ExecutionScope(
                tenant_id=scope.tenant_id,
                unit_id=values["NFCORE_WORKER_GSM_UNIT_ID"],
                host_namespace=values["NFCORE_WORKER_GSM_HOST_NAMESPACE"],
                environment=FiscalEnvironment.HOMOLOGATION,
                correlation_id="worker-staging-claim",
            ),
            operations=frozenset({DELIVER_WEBHOOK_OPERATION}),
        )
    except (ValueError, TypeError):
        raise RuntimeConfigurationError("worker GSM signing metadata invalid") from None
    provider = values["NFCORE_WORKER_GSM_PROVIDER_ID"]
    destination = values["NFCORE_WORKER_GSM_DESTINATION_ID"]

    def build(
        database: PostgresFiscalDatabase, settings: RuntimeSettings
    ) -> ScopedWorkerHandlerComposition:
        if settings.environment is not RuntimeEnvironment.STAGING:
            raise RuntimeConfigurationError("worker GSM requires staging")
        with database() as uow:
            binding = uow.secret_bindings.get(reference.reference_id)
        if (
            binding is None
            or binding.tenant_id != scope.tenant_id
            or binding.unit_id != scope.unit_id
            or binding.purpose != scope.purpose
            or binding.kind != "signature"
            or binding.runtime_environment != "staging"
            or binding.workload_id != "nfcore-worker"
            or binding.canonical_version != reference.version
            or binding.provider_id != provider
            or binding.resource != resource
            or binding.state != "active"
            or (binding.not_after is not None and binding.not_after <= datetime.now(UTC))
        ):
            raise RuntimeConfigurationError("worker GSM durable signing binding unavailable")
        try:
            if has_json:
                raw = source.get(_JSON_ENV, "")
                if environ is None:
                    os.environ.pop(_JSON_ENV, None)
                try:
                    credentials = _memory_credentials(raw, key_id=key_id)
                finally:
                    del raw
            else:
                loader = cast(
                    Callable[[str], ServiceAccountCredentials],
                    ServiceAccountCredentials.from_service_account_file,
                )
                credentials = loader(str(file))
            access = build_staging_workload_gsm_access(
                credentials=credentials,
                workload_id="nfcore-worker",
                environment="staging",
                key_created_at=created_at,
                key_not_after=not_after,
            )
        except Exception:
            raise RuntimeConfigurationError("worker GSM approved identity unavailable") from None
        reader = DurableGsmReader(
            uow_factory=database,
            access=access,
            environment="staging",
            workload_id="nfcore-worker",
            allowed_resources=frozenset({resource}),
        )
        logger = StructuredLogger(service="nfcore-worker", environment="staging")

        def audit(event: object) -> None:
            outcome = getattr(event, "outcome", "denied")
            logger.emit("INFO", "worker_gsm_secret_access", outcome=outcome)

        resolver = SecretResolver(
            GoogleSignatureSecretBackend(reader, provider_id=provider),
            environment="staging",
            audit_sink=audit,
        )
        # Actual GSM read is required before the continuous process reports ready.
        # The canonical resolver zeroizes its transient material on context exit.
        with resolver.resolve(reference, scope=scope):
            pass
        webhook = build_gsm_worker_webhook_dependencies(
            resolver=resolver, reference=reference, scope=scope,
            destination_id=destination,
        )
        return ScopedWorkerHandlerComposition(
            handlers=build_canonical_worker_handlers(uow_factory=database, webhook=webhook),
            claim_selection=selection,
        )

    return build
