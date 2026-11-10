"""Versioned Bling integration ports shared between independent A/B tracks.

These are contracts, not a second fiscal authority, database, router or worker.
Concrete adapters must rely on canonical sessions, scope resolution and outbox.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol, TypedDict

from kordena_fiscal.domain import ExecutionScope, FiscalEnvironment


class BlingInstallationState(StrEnum):
    NOT_CONFIGURED = "not_configured"
    CONNECTED = "connected"
    NEEDS_REAUTH = "needs_reauth"
    PAUSED = "paused"
    ERROR = "error"


class BlingRecoveryOutcome(StrEnum):
    ALREADY_RECORDED = "already_recorded"
    QUEUED = "queued"
    REQUIRES_REVIEW = "requires_review"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class BlingInstallationView:
    installation_id: str
    company_id: str
    tenant_id: str
    unit_id: str
    environment: FiscalEnvironment
    state: BlingInstallationState
    health_code: str
    credential_status: str
    updated_at: datetime
    revision: int

    def __post_init__(self) -> None:
        if (
            not all((self.installation_id, self.company_id, self.tenant_id, self.unit_id))
            or self.revision < 1
            or self.updated_at.tzinfo is None
            or self.updated_at.utcoffset() is None
        ):
            raise ValueError("invalid Bling installation view")


class BlingOrderSummary(TypedDict):
    order_id: int
    state: str
    document_id: str | None
    review_required: bool
    retryable: bool
    updated_at: str


@dataclass(frozen=True, slots=True)
class BlingOrderPage:
    rows: tuple[BlingOrderSummary, ...]
    next_cursor: str | None
    limit: int

    def __post_init__(self) -> None:
        if not 1 <= self.limit <= 100 or len(self.rows) > self.limit:
            raise ValueError("invalid Bling order page")


@dataclass(frozen=True, slots=True)
class BlingRecoveryResult:
    operation_id: str
    installation_id: str
    order_id: int
    outcome: BlingRecoveryOutcome
    correlation_id: str

    def __post_init__(self) -> None:
        if (
            not all((self.operation_id, self.installation_id, self.correlation_id))
            or self.order_id <= 0
        ):
            raise ValueError("invalid Bling recovery result")


class BlingInstallationReader(Protocol):
    """Caller must supply a canonical validated scope, never browser authority."""

    def list_for_scope(
        self, scope: ExecutionScope, *, cursor: str | None = None, limit: int = 50
    ) -> tuple[tuple[BlingInstallationView, ...], str | None]: ...

    def get_for_scope(
        self, scope: ExecutionScope, installation_id: str
    ) -> BlingInstallationView | None: ...


class BlingOrderReader(Protocol):
    def list_orders(
        self, scope: ExecutionScope, installation_id: str, *,
        cursor: str | None = None, limit: int = 50,
    ) -> BlingOrderPage: ...


class BlingRecoveryPort(Protocol):
    def reconcile(
        self, scope: ExecutionScope, installation_id: str, order_id: int, *,
        request_id: str, actor_id: str,
    ) -> BlingRecoveryResult: ...

    def retry_status(
        self, scope: ExecutionScope, installation_id: str, order_id: int, *,
        request_id: str, actor_id: str,
    ) -> BlingRecoveryResult: ...


class BlingProviderSearch(Protocol):
    """Secrets and transport remain inside the A-owned adapter."""

    def fetch_order(
        self, scope: ExecutionScope, installation_id: str, order_id: int,
    ) -> dict[str, object]: ...

    def search_orders(
        self, scope: ExecutionScope, installation_id: str, *,
        cursor: str | None = None, limit: int = 50,
    ) -> tuple[tuple[dict[str, object], ...], str | None]: ...
