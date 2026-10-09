"""Reference-only cloud bindings; no secret material or provider URL in durable state."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

from .secrets import SecretReference, SecretResolutionError, SecretScope

_RESOURCE = re.compile(r"projects/[a-z0-9][a-z0-9-]{4,62}/secrets/[A-Za-z0-9_-]{1,255}\Z")
_REF = re.compile(r"ref:[a-z0-9][a-z0-9:/_.-]{0,251}\Z")


@dataclass(frozen=True, slots=True)
class SecretBinding:
    reference_id: str
    tenant_id: str
    unit_id: str | None
    purpose: str
    runtime_environment: str
    fiscal_environment: str | None
    provider_id: str | None
    workload_id: str
    kind: str
    canonical_version: str | int
    resource: str
    cloud_version: str
    revision: int = 1
    state: str = "active"
    not_after: datetime | None = None

    def __post_init__(self) -> None:
        scope = SecretScope(self.tenant_id, self.unit_id, self.purpose)
        if (scope.tenant_id, scope.unit_id, scope.purpose) != (
            self.tenant_id,
            self.unit_id,
            self.purpose,
        ):
            raise SecretResolutionError("binding scope must be canonical")
        if self.runtime_environment not in {"test", "development", "staging", "production"}:
            raise SecretResolutionError("invalid binding environment")
        if self.state not in {"active", "revoked"} or type(self.revision) is not int:
            raise SecretResolutionError("invalid binding state/revision")
        if self.revision < 1 or not _RESOURCE.fullmatch(self.resource):
            raise SecretResolutionError("invalid binding resource/revision")
        if not re.fullmatch(r"[1-9][0-9]{0,18}", self.cloud_version):
            raise SecretResolutionError("cloud version must be numeric and pinned")
        for value in (
            self.tenant_id,
            self.unit_id,
            self.purpose,
            self.workload_id,
            self.provider_id,
        ):
            if value is not None and (
                not value
                or len(value) > 160
                or value != value.strip()
                or any(ord(c) < 32 or ord(c) == 127 for c in value)
            ):
                raise SecretResolutionError("invalid binding metadata")
        if self.not_after is not None and (
            self.not_after.tzinfo is None or self.not_after.utcoffset() is None
        ):
            raise SecretResolutionError("binding expiry must be timezone-aware")
        if self.kind == "signature":
            if type(self.canonical_version) is not int or self.fiscal_environment is not None:
                raise SecretResolutionError("invalid signature binding")
            SecretReference(self.reference_id, self.canonical_version)
            if self.provider_id is None:
                raise SecretResolutionError("signature provider must be explicit")
        elif self.kind in {"certificate", "csc", "credentials"}:
            if not _REF.fullmatch(self.reference_id) or self.unit_id is None:
                raise SecretResolutionError("invalid fiscal binding reference")
            expected_purpose = {
                "certificate": "document-signing",
                "csc": "csc-authentication",
                "credentials": "provider-authentication",
            }[self.kind]
            if self.purpose != expected_purpose:
                raise SecretResolutionError("fiscal binding purpose/kind mismatch")
            if self.fiscal_environment not in {"homologation", "production"}:
                raise SecretResolutionError("invalid fiscal binding environment")
            if (
                type(self.canonical_version) is not str
                or not self.canonical_version
                or len(self.canonical_version) > 256
            ):
                raise SecretResolutionError("invalid fiscal canonical version")
            if self.kind == "certificate" and self.provider_id is not None:
                raise SecretResolutionError("certificate binding is not provider scoped")
            if self.kind != "certificate" and self.provider_id is None:
                raise SecretResolutionError("fiscal provider must be explicit")
        else:
            raise SecretResolutionError("invalid binding kind")

    @property
    def version_name(self) -> str:
        return f"{self.resource}/versions/{self.cloud_version}"

    def metadata(self) -> dict[str, Any]:
        result = asdict(self)
        result["not_after"] = self.not_after.isoformat() if self.not_after else None
        return result

    @classmethod
    def from_metadata(cls, value: dict[str, Any]) -> SecretBinding:
        data = dict(value)
        expiry = data.get("not_after")
        if expiry is not None:
            data["not_after"] = datetime.fromisoformat(expiry)
        return cls(**data)
