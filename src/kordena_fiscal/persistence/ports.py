"""Persistence ports for the independently operable FM Fiscal application layer.

The domain stays persistence-agnostic. Existing atomic store contracts for
idempotency, numbering, outbox, archive and inbox are reused here; repository
ports and the unit-of-work boundary keep application coordination transactional.
"""

from __future__ import annotations

from datetime import datetime
from types import TracebackType
from typing import Protocol, Self

from kordena_fiscal.archive import FiscalArchiveStore
from kordena_fiscal.contingency import FiscalOutboxStore
from kordena_fiscal.control_plane.models import (
    ControlPlaneAuditEvent,
    FiscalOrganization,
    FiscalUnitRegistration,
    SecretReference,
    SecretReferenceKind,
)
from kordena_fiscal.domain import (
    ExecutionScope,
    FiscalAccountBinding,
    FiscalDomainError,
    FiscalEnvironment,
    FiscalProfile,
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


class ControlPlaneStore(Protocol):
    """Durable administrative state used by the independent FM Fiscal Control Plane."""

    def add_organization(self, organization: FiscalOrganization) -> FiscalOrganization: ...

    def get_organization(self, tenant_id: str) -> FiscalOrganization | None: ...

    def add_unit(self, registration: FiscalUnitRegistration) -> FiscalUnitRegistration: ...

    def get_unit(self, tenant_id: str, unit_id: str) -> FiscalUnitRegistration | None: ...

    def add_secret_reference(self, reference: SecretReference) -> SecretReference: ...

    def get_secret_reference(
        self,
        tenant_id: str,
        unit_id: str,
        environment: FiscalEnvironment,
        kind: SecretReferenceKind,
    ) -> SecretReference | None: ...

    def add_profile(self, profile: FiscalProfile) -> FiscalProfile: ...

    def get_profile(self, profile_id: str, version: int) -> FiscalProfile | None: ...

    def resolve_profile(
        self,
        *,
        host_namespace: str,
        tenant_id: str,
        unit_id: str,
        environment: FiscalEnvironment,
        instant: datetime,
    ) -> FiscalProfile | None: ...

    def append_audit(self, event: ControlPlaneAuditEvent) -> ControlPlaneAuditEvent: ...

    def list_audit(self, tenant_id: str | None = None) -> tuple[ControlPlaneAuditEvent, ...]: ...


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

    @property
    def control_plane(self) -> ControlPlaneStore: ...

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
