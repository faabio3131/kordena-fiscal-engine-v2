"""Read-only, sanitized operational views for the independent FM Fiscal Control Plane."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from kordena_fiscal.archive import FiscalArchiveEntry, FiscalArchiveKind
from kordena_fiscal.contingency import FiscalOutboxEntry, FiscalOutboxStatus
from kordena_fiscal.domain import (
    ExecutionScope,
    FiscalEnvironment,
    FiscalValidationError,
    SourceReference,
)
from kordena_fiscal.events import DeliveryAttemptStatus, FiscalDeliveryAttempt
from kordena_fiscal.persistence.ports import FiscalUnitOfWorkFactory
from kordena_fiscal.reconciliation import (
    FiscalReconciliationResult,
    ReconciliationIssue,
    ReconciliationIssueCode,
    ReconciliationStatus,
)

from .models import AdminPrincipal, ControlPlanePermission
from .service import ControlPlaneAuthorizationError, ControlPlaneNotFoundError


@dataclass(frozen=True, slots=True)
class DeliveryAttemptView:
    attempt_count: int
    status: DeliveryAttemptStatus
    started_at: datetime
    finished_at: datetime | None
    next_available_at: datetime | None
    ordering_key: str | None
    outcome_reference: str | None
    last_error: str | None


@dataclass(frozen=True, slots=True)
class DeliveryOperationView:
    """Operational delivery metadata with no message payload bytes."""

    entry_id: str
    host_namespace: str
    tenant_id: str
    unit_id: str
    environment: FiscalEnvironment
    correlation_id: str
    operation: str
    payload_sha256: str
    created_at: datetime
    available_at: datetime
    status: FiscalOutboxStatus
    attempt_count: int
    lease_until: datetime | None
    ordering_key: str | None
    last_error: str | None
    completion_reference: str | None
    attempts: tuple[DeliveryAttemptView, ...]


@dataclass(frozen=True, slots=True)
class ArchiveReferenceView:
    """Archive metadata only; immutable fiscal content is intentionally excluded."""

    entry_id: str
    document_reference: str
    kind: FiscalArchiveKind
    content_sha256: str
    media_type: str
    archived_at: datetime
    retention_policy_id: str
    retention_policy_version: int
    retain_until: datetime | None
    legal_basis_reference: str | None
    previous_manifest_sha256: str | None


@dataclass(frozen=True, slots=True)
class ReconciliationIssueView:
    code: ReconciliationIssueCode
    message: str
    document_id: str | None


@dataclass(frozen=True, slots=True)
class ReconciliationControlView:
    status: ReconciliationStatus
    source_type: str
    source_id: str
    fingerprint: str
    selected_document_id: str | None
    issues: tuple[ReconciliationIssueView, ...]


class OperationalControlPlaneService:
    """Governed read model over certified durable operational repositories."""

    def __init__(self, unit_of_work_factory: FiscalUnitOfWorkFactory) -> None:
        self._unit_of_work_factory = unit_of_work_factory

    def get_delivery_operation(
        self,
        *,
        actor: AdminPrincipal,
        scope: ExecutionScope,
        entry_id: str,
    ) -> DeliveryOperationView:
        self._authorize(actor=actor, scope=scope)
        with self._unit_of_work_factory() as uow:
            entry = uow.outbox.get(entry_id)
            if entry is None or not self._same_partition(entry.scope, scope):
                raise ControlPlaneNotFoundError("delivery operation was not found in scope")
            ordering_key = uow.outbox_ordering.get(entry.entry_id)
            attempts = uow.delivery_audit.list_for_entry(entry.entry_id)
        return self._delivery_view(entry, ordering_key, attempts)

    def list_archive_references(
        self,
        *,
        actor: AdminPrincipal,
        scope: ExecutionScope,
        document_reference: str,
    ) -> tuple[ArchiveReferenceView, ...]:
        self._authorize(actor=actor, scope=scope)
        with self._unit_of_work_factory() as uow:
            entries = uow.archive.list_for_document(scope, document_reference)
        return tuple(self._archive_view(entry) for entry in entries)

    def get_reconciliation(
        self,
        *,
        actor: AdminPrincipal,
        scope: ExecutionScope,
        source: SourceReference,
    ) -> ReconciliationControlView | None:
        self._authorize(actor=actor, scope=scope)
        if not isinstance(source, SourceReference):
            raise FiscalValidationError("source must be SourceReference")
        with self._unit_of_work_factory() as uow:
            result = uow.reconciliations.get(scope, source)
        return None if result is None else self._reconciliation_view(result)

    def _authorize(self, *, actor: AdminPrincipal, scope: ExecutionScope) -> None:
        if not isinstance(actor, AdminPrincipal):
            raise FiscalValidationError("actor must be AdminPrincipal")
        if not isinstance(scope, ExecutionScope):
            raise FiscalValidationError("scope must be ExecutionScope")
        if scope.host_namespace is None:
            raise FiscalValidationError(
                "Operational Control Plane requires an explicit host_namespace"
            )
        if not actor.has_permission(ControlPlanePermission.OPERATIONS_READ):
            raise ControlPlaneAuthorizationError(
                "actor lacks required permission: operations.read"
            )
        if not actor.can_access_tenant(scope.tenant_id):
            raise ControlPlaneAuthorizationError(
                f"actor cannot access tenant: {scope.tenant_id}"
            )
        with self._unit_of_work_factory() as uow:
            if uow.control_plane.get_organization(scope.tenant_id) is None:
                raise ControlPlaneNotFoundError(
                    f"organization is not onboarded: {scope.tenant_id}"
                )
            unit = uow.control_plane.get_unit(scope.tenant_id, scope.unit_id)
            if unit is None:
                raise ControlPlaneNotFoundError(
                    f"unit is not onboarded: {scope.tenant_id}/{scope.unit_id}"
                )
            if scope.environment not in unit.enabled_environments:
                raise ControlPlaneAuthorizationError(
                    "operational environment is not enabled for the target unit"
                )

    @staticmethod
    def _same_partition(left: ExecutionScope, right: ExecutionScope) -> bool:
        return left.identity_partition_key == right.identity_partition_key

    @staticmethod
    def _attempt_view(attempt: FiscalDeliveryAttempt) -> DeliveryAttemptView:
        return DeliveryAttemptView(
            attempt_count=attempt.attempt_count,
            status=attempt.status,
            started_at=attempt.started_at,
            finished_at=attempt.finished_at,
            next_available_at=attempt.next_available_at,
            ordering_key=attempt.ordering_key,
            outcome_reference=attempt.outcome_reference,
            last_error=attempt.last_error,
        )

    @classmethod
    def _delivery_view(
        cls,
        entry: FiscalOutboxEntry,
        ordering_key: str | None,
        attempts: tuple[FiscalDeliveryAttempt, ...],
    ) -> DeliveryOperationView:
        host_namespace = entry.scope.host_namespace
        assert host_namespace is not None
        return DeliveryOperationView(
            entry_id=entry.entry_id,
            host_namespace=host_namespace,
            tenant_id=entry.scope.tenant_id,
            unit_id=entry.scope.unit_id,
            environment=entry.scope.environment,
            correlation_id=entry.scope.correlation_id,
            operation=entry.operation,
            payload_sha256=entry.payload_sha256,
            created_at=entry.created_at,
            available_at=entry.available_at,
            status=entry.status,
            attempt_count=entry.attempt_count,
            lease_until=entry.lease_until,
            ordering_key=ordering_key,
            last_error=entry.last_error,
            completion_reference=entry.completion_reference,
            attempts=tuple(cls._attempt_view(item) for item in attempts),
        )

    @staticmethod
    def _archive_view(entry: FiscalArchiveEntry) -> ArchiveReferenceView:
        return ArchiveReferenceView(
            entry_id=entry.entry_id,
            document_reference=entry.document_reference,
            kind=entry.kind,
            content_sha256=entry.content_sha256,
            media_type=entry.media_type,
            archived_at=entry.archived_at,
            retention_policy_id=entry.retention.policy_id,
            retention_policy_version=entry.retention.policy_version,
            retain_until=entry.retention.retain_until,
            legal_basis_reference=entry.retention.legal_basis_reference,
            previous_manifest_sha256=entry.previous_manifest_sha256,
        )

    @staticmethod
    def _issue_view(issue: ReconciliationIssue) -> ReconciliationIssueView:
        return ReconciliationIssueView(
            code=issue.code,
            message=issue.message,
            document_id=issue.document_id,
        )

    @classmethod
    def _reconciliation_view(
        cls,
        result: FiscalReconciliationResult,
    ) -> ReconciliationControlView:
        return ReconciliationControlView(
            status=result.status,
            source_type=result.source.source_type,
            source_id=result.source.source_id,
            fingerprint=result.fingerprint,
            selected_document_id=result.selected_document_id,
            issues=tuple(cls._issue_view(issue) for issue in result.issues),
        )
