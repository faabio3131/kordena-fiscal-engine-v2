"""Persistence ports for the independently operable FM Fiscal application layer.

The domain stays persistence-agnostic. Existing atomic store contracts for
idempotency, numbering, outbox, archive and inbox are reused here; repository
ports and the unit-of-work boundary keep application coordination transactional.
"""

from __future__ import annotations

from types import TracebackType
from typing import Protocol, Self

from kordena_fiscal.archive import FiscalArchiveStore
from kordena_fiscal.contingency import FiscalOutboxStore
from kordena_fiscal.domain import (
    ExecutionScope,
    FiscalAccountBinding,
    FiscalDomainError,
    HostScope,
    SourceReference,
)
from kordena_fiscal.events import FiscalDeliveryAuditStore, FiscalInboxStore
from kordena_fiscal.lifecycle import FiscalStateSnapshot, IdempotencyStore
from kordena_fiscal.numbering import FiscalSequenceStore
from kordena_fiscal.reconciliation import FiscalReconciliationResult


class FiscalPersistenceError(FiscalDomainError):
    """Base error for durable persistence contract violations."""


class PersistenceConflictError(FiscalPersistenceError):
    """Raised on duplicate identity or optimistic-concurrency conflict."""


class PersistenceStateError(FiscalPersistenceError):
    """Raised when durable state is missing, corrupt or violates a repository contract."""


class FiscalBindingRepository(Protocol):
    """Durable exact resolver for host scope -> fiscal account binding."""

    def add(self, binding: FiscalAccountBinding) -> FiscalAccountBinding: ...

    def resolve(self, host_scope: HostScope) -> FiscalAccountBinding: ...

    def get_by_id(self, binding_id: str) -> FiscalAccountBinding | None: ...


class FiscalLifecycleRepository(Protocol):
    """Optimistically-versioned persistence for complete lifecycle snapshots."""

    def add(self, snapshot: FiscalStateSnapshot) -> FiscalStateSnapshot: ...

    def get(self, document_id: str) -> FiscalStateSnapshot | None: ...

    def save(
        self,
        snapshot: FiscalStateSnapshot,
        *,
        expected_version: int,
    ) -> FiscalStateSnapshot: ...


class FiscalReconciliationRepository(Protocol):
    """Durable latest reconciliation state for one operation identity."""

    def save(self, result: FiscalReconciliationResult) -> FiscalReconciliationResult: ...

    def get(
        self,
        scope: ExecutionScope,
        source: SourceReference,
    ) -> FiscalReconciliationResult | None: ...


class FiscalOutboxOrderingStore(Protocol):
    """Optional explicit ordering metadata; no key means no ordering dependency."""

    def register(self, entry_id: str, ordering_key: str) -> str: ...

    def get(self, entry_id: str) -> str | None: ...


class FiscalUnitOfWork(Protocol):
    """One atomic local transaction spanning all durable fiscal repositories."""

    @property
    def idempotency(self) -> IdempotencyStore: ...

    @property
    def sequences(self) -> FiscalSequenceStore: ...

    @property
    def inbox(self) -> FiscalInboxStore: ...

    @property
    def outbox(self) -> FiscalOutboxStore: ...

    @property
    def outbox_ordering(self) -> FiscalOutboxOrderingStore: ...

    @property
    def delivery_audit(self) -> FiscalDeliveryAuditStore: ...

    @property
    def archive(self) -> FiscalArchiveStore: ...

    @property
    def bindings(self) -> FiscalBindingRepository: ...

    @property
    def lifecycle(self) -> FiscalLifecycleRepository: ...

    @property
    def reconciliations(self) -> FiscalReconciliationRepository: ...

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...


class FiscalUnitOfWorkFactory(Protocol):
    def __call__(self) -> FiscalUnitOfWork: ...
