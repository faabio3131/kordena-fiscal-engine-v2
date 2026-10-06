"""Synthetic durable records for internal HTTP tests; no fiscal/provider simulation."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from kordena_fiscal.application.service import FiscalApplicationService
from kordena_fiscal.archive import FiscalArchiveEntry, FiscalArchiveKind, RetentionPolicyMetadata
from kordena_fiscal.contingency import FiscalOutboxEntry, FiscalOutboxStatus
from kordena_fiscal.control_plane import (
    AdminPrincipal,
    ControlPlanePermission,
    DurableControlPlaneService,
    FiscalUnitRegistration,
)
from kordena_fiscal.domain import ExecutionScope, FiscalEnvironment, SourceReference
from kordena_fiscal.lifecycle import FiscalDocumentState, FiscalStateSnapshot, IdempotencyKey
from kordena_fiscal.persistence.ports import FiscalUnitOfWorkFactory
from kordena_fiscal.reconciliation import (
    FiscalReconciliationResult,
    ReconciliationIssue,
    ReconciliationIssueCode,
    ReconciliationStatus,
)
from kordena_fiscal.runtime.fiscal_runtime import (
    CanonicalFiscalOperationPath,
    CanonicalPortalOperationExecutor,
)
from kordena_fiscal.security.human_identity import (
    HumanAccount,
    HumanAccountRepository,
    HumanIdentityService,
    InMemoryHumanAccountRepository,
    InMemoryWebSessionRepository,
    PortalRole,
    ScryptPasswordHasher,
)
from kordena_fiscal.web import create_app
from kordena_fiscal.web.portal_runtime import DurableHumanPortalExecutor

NOW = datetime(2026, 10, 6, 12, tzinfo=UTC)
PASSWORD = "synthetic-p02-http-password-2026"
PROTECTED = "PROTECTED_SYNTHETIC_RAW_CONTENT"


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def scope(
    tenant="tenant-a", unit="unit-a", host="fm-nfcore", environment=FiscalEnvironment.HOMOLOGATION
):
    return ExecutionScope(
        tenant_id=tenant,
        unit_id=unit,
        host_namespace=host,
        environment=environment,
        correlation_id="corr-fixture",
    )


def seed(database: FiscalUnitOfWorkFactory) -> None:
    service = DurableControlPlaneService(database)
    global_actor = AdminPrincipal(
        actor_id="synthetic-global",
        global_scope=True,
        permissions=frozenset({ControlPlanePermission.ORGANIZATION_WRITE}),
    )
    for tenant, units in (("tenant-a", ("unit-a", "unit-b")), ("tenant-b", ("unit-a",))):
        service.onboard_organization(
            actor=global_actor,
            tenant_id=tenant,
            legal_name="Synthetic " + tenant,
            correlation_id="fixture-org",
        )
        actor = AdminPrincipal(
            actor_id="synthetic-tenant",
            tenant_ids=frozenset({tenant}),
            permissions=frozenset({ControlPlanePermission.UNIT_WRITE}),
        )
        for unit in units:
            service.onboard_unit(
                actor=actor,
                registration=FiscalUnitRegistration(
                    tenant_id=tenant,
                    unit_id=unit,
                    display_name="Synthetic " + unit,
                    enabled_environments=frozenset(
                        {FiscalEnvironment.HOMOLOGATION, FiscalEnvironment.PRODUCTION}
                    ),
                ),
                correlation_id="fixture-unit",
            )
    app = FiscalApplicationService(database)
    partitions = (
        ("a", scope()),
        ("b", scope(unit="unit-b")),
        ("other", scope(tenant="tenant-b")),
        ("host", scope(host="other-host")),
        ("prod", scope(environment=FiscalEnvironment.PRODUCTION)),
    )
    for label, partition in partitions:
        app.reserve_issuance(
            scope=partition,
            key=IdempotencyKey(digest(label)),
            request_fingerprint=digest("request-" + label),
            document_id="DOC-" + label,
            created_at=NOW,
        )
        app.transition_lifecycle(
            "DOC-" + label,
            FiscalDocumentState.VALIDATING,
            occurred_at=NOW,
            reason=PROTECTED,
            correlation_id="fixture-state",
        )
        app.transition_lifecycle(
            "DOC-" + label,
            FiscalDocumentState.ERROR,
            occurred_at=NOW,
            reason=PROTECTED,
            correlation_id="fixture-state",
        )
        with database() as uow:
            uow.archive.append(
                FiscalArchiveEntry.build(
                    scope=partition,
                    document_reference="ARCHIVE-" + label,
                    kind=FiscalArchiveKind.OTHER,
                    content=PROTECTED.encode(),
                    media_type="application/xml",
                    archived_at=NOW,
                    retention=RetentionPolicyMetadata(policy_id="synthetic", policy_version=1),
                )
            )
            uow.outbox.enqueue(
                FiscalOutboxEntry(
                    entry_id=digest("outbox-" + label),
                    scope=partition,
                    operation="issue",
                    deduplication_key="dedup-" + label,
                    payload=PROTECTED.encode(),
                    payload_sha256=digest(PROTECTED),
                    created_at=NOW,
                    available_at=NOW,
                    status=FiscalOutboxStatus.DEAD_LETTER,
                    attempt_count=1,
                    last_error=PROTECTED,
                )
            )
            uow.reconciliations.save(
                FiscalReconciliationResult(
                    scope=partition,
                    source=SourceReference(source_type="synthetic", source_id=label),
                    status=ReconciliationStatus.DIVERGENT,
                    fingerprint=digest("reconcile-" + label),
                    selected_document_id="DOC-" + label,
                    issues=(
                        ReconciliationIssue(
                            code=ReconciliationIssueCode.FISCAL_PROCESSING_PENDING,
                            message=PROTECTED,
                            document_id="DOC-" + label,
                        ),
                    ),
                )
            )
            uow.commit()
    with database() as uow:
        uow.lifecycle.add(FiscalStateSnapshot.initial("LEGACY-UNSCOPED", NOW))
        uow.commit()


def identity(accounts: HumanAccountRepository | None = None) -> HumanIdentityService:
    repository = accounts or InMemoryHumanAccountRepository()
    hasher = ScryptPasswordHasher()
    for name, role, tenant, units in (
        ("owner", PortalRole.OWNER, "tenant-a", None),
        ("operator", PortalRole.OPERATOR, "tenant-a", frozenset({"unit-a"})),
        ("auditor", PortalRole.AUDITOR, "tenant-a", frozenset({"unit-a"})),
        ("billing", PortalRole.BILLING, "tenant-a", frozenset({"unit-a"})),
        ("other", PortalRole.OWNER, "tenant-b", None),
    ):
        repository.save(
            HumanAccount(
                account_id="synthetic-" + name,
                email=name + "@example.com",
                password_hash=hasher.hash(PASSWORD),
                tenant_id=tenant,
                role=role,
                unit_ids=units,
            )
        )
    return HumanIdentityService(
        accounts=repository, sessions=InMemoryWebSessionRepository(), password_hasher=hasher
    )


def app(database: FiscalUnitOfWorkFactory):
    path = CanonicalFiscalOperationPath(FiscalApplicationService(database))
    executor = CanonicalPortalOperationExecutor(unit_of_work_factory=database, path=path)
    return create_app(
        human_identity=identity(),
        portal_executor=DurableHumanPortalExecutor(
            database,
            operation_executor=executor,
        ),
    )
