"""Load a deployment-managed snapshot of fiscal Bridge credential verifiers."""

import json
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path

from kordena_fiscal.domain import FiscalEnvironment, HostNamespace
from kordena_fiscal.security.s2s import (
    CallerIdentity,
    FiscalCapability,
    HostScopeGrant,
    WorkloadCredentialRecord,
)

from .config import RuntimeConfigurationError


def load_bridge_credentials(
    environ: Mapping[str, str],
) -> tuple[WorkloadCredentialRecord, ...]:
    path = environ.get("NFCORE_BRIDGE_CREDENTIALS_FILE", "").strip()
    if not path:
        return ()

    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(payload, list) or not payload:
            raise ValueError("expected a non-empty array")
        records = tuple(
            WorkloadCredentialRecord(
                credential_id=entry["credential_id"],
                caller=CallerIdentity(
                    caller_id=entry["caller_id"],
                    host_namespace=HostNamespace(entry["host_namespace"]),
                    capabilities=frozenset(map(FiscalCapability, entry["capabilities"])),
                    scope_grants=tuple(
                        HostScopeGrant(tenant_id=grant["tenant_id"], unit_id=grant["unit_id"])
                        for grant in entry["scope_grants"]
                    ),
                    environments=frozenset(map(FiscalEnvironment, entry["environments"])),
                ),
                secret_sha256=entry["secret_sha256"],
                valid_from=datetime.fromisoformat(entry["valid_from"]),
                expires_at=datetime.fromisoformat(entry["expires_at"]),
                revoked=entry["revoked"],
            )
            for entry in payload
        )
        if len({record.credential_id for record in records}) != len(records):
            raise ValueError("duplicate credential ID")
    except (OSError, ValueError, TypeError, KeyError, AttributeError, OverflowError):
        raise RuntimeConfigurationError("Invalid fiscal Bridge credential configuration") from None
    return records
