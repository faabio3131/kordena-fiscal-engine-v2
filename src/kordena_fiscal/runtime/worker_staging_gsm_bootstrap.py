"""Explicit staging-only GSM composition for the existing canonical outbox Worker.

No tenant or signing authority comes from an outbox payload. This is a *single
pre-approved pilot scope*, not a multi-tenant dynamic signing registry. A broader
Worker must not treat this limited composition as full commercial readiness.
No service-account key, raw secret or custom handler is stored in this module.
"""
from __future__ import annotations

import os
import re
import stat
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path

from google.oauth2.service_account import Credentials as ServiceAccountCredentials

from kordena_fiscal.contingency import FiscalOutboxHandler
from kordena_fiscal.persistence.postgres import PostgresFiscalDatabase
from kordena_fiscal.security.secrets import SecretReference, SecretResolver, SecretScope
from kordena_fiscal.vault.google_secret_manager import (
    DurableGsmReader,
    GoogleSignatureSecretBackend,
)

from .config import RuntimeConfigurationError, RuntimeEnvironment, RuntimeSettings
from .gsm_staging_identity_policy import build_staging_workload_gsm_access
from .observability import StructuredLogger
from .secret_manager import build_gsm_worker_webhook_dependencies
from .worker_composition import build_canonical_worker_handlers

_RESOURCE = re.compile(r"projects/fm-nfcore-staging/secrets/[A-Za-z0-9_-]{1,255}\Z")
_MODE = "scoped-staging-sa-v1"
_ENV_FIELDS = (
    "NFCORE_WORKER_GSM_CREDENTIAL_FILE",
    "NFCORE_WORKER_GSM_KEY_CREATED_AT",
    "NFCORE_WORKER_GSM_KEY_NOT_AFTER",
    "NFCORE_WORKER_GSM_TENANT_ID",
    "NFCORE_WORKER_GSM_UNIT_ID",
    "NFCORE_WORKER_GSM_SIGNING_REFERENCE",
    "NFCORE_WORKER_GSM_SIGNING_VERSION",
    "NFCORE_WORKER_GSM_PROVIDER_ID",
    "NFCORE_WORKER_GSM_DESTINATION_ID",
    "NFCORE_WORKER_GSM_RESOURCE",
)


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
) -> Callable[[PostgresFiscalDatabase, RuntimeSettings], Mapping[str, FiscalOutboxHandler]] | None:
    """Fixed canonical composition selected by an explicit, exact staging opt-in."""
    values = dict(os.environ if environ is None else environ)
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
    file = _private_file(values["NFCORE_WORKER_GSM_CREDENTIAL_FILE"])
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
    except (ValueError, TypeError):
        raise RuntimeConfigurationError("worker GSM signing metadata invalid") from None
    provider = values["NFCORE_WORKER_GSM_PROVIDER_ID"]
    destination = values["NFCORE_WORKER_GSM_DESTINATION_ID"]

    def build(
        database: PostgresFiscalDatabase, settings: RuntimeSettings
    ) -> Mapping[str, FiscalOutboxHandler]:
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
            credentials = ServiceAccountCredentials.from_service_account_file(str(file))
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
        return build_canonical_worker_handlers(uow_factory=database, webhook=webhook)

    return build
