"""Persistence ports for the independently operable FM Fiscal application layer.

The domain stays persistence-agnostic. Existing atomic store contracts for
idempotency, numbering, outbox and archive are reused here; V2-07 adds only the
missing repository and unit-of-work boundaries needed by the application layer.
"""

from __future__ import annotations

from typing import Protocol, Self

from kordena_fiscal.archive import FiscalArchiveStore
from kordena_fiscal.contingency import FiscalOutboxStore
from kordena_fiscal.domain import (
    ExecutionScope,
    FiscalAccountBinding,
    HostScope,
    SourceReference,
)
from kordena_fiscal.lifecycle import FiscalStateSnapshot, IdempotencyStore
from kordena_fiscal.numbering import FiscalSequenceStore
from kordena_fiscal.reconciliation import FiscalReconciliationResult


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


class FiscalUnitOfWork(Protocol):
    """One atomic local transaction spanning all durable fiscal repositories."""

    idempotency: IdempotencyStore
    sequences: FiscalSequenceStore
    outbox: FiscalOutboxStore
    archive: FiscalArchiveStore
    bindings: FiscalBindingRepository
    lifecycle: FiscalLifecycleRepository
    reconciliations: FiscalReconciliationRepository

    def __enter__(self) -> Self: ...

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...


class FiscalUnitOfWorkFactory(Protocol):
    def __call__(self) -> FiscalUnitOfWork: ...
