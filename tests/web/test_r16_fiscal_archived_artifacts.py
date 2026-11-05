"""Scoped archive access: never fabricate XML or DANFE."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

import pytest
from fastapi import HTTPException

from kordena_fiscal.archive import (
    FiscalArchiveEntry,
    FiscalArchiveKind,
    InMemoryFiscalArchiveStore,
    RetentionPolicyMetadata,
)
from kordena_fiscal.domain import ExecutionScope, FiscalEnvironment
from kordena_fiscal.persistence.ports import FiscalUnitOfWorkFactory
from kordena_fiscal.security.human_identity import AuthenticatedHuman, PortalPermission
from kordena_fiscal.web.portal_runtime import DurableHumanPortalExecutor


class _Authorized:
    def __init__(self, tenant_id: str) -> None:
        self.tenant_id = tenant_id

    def assert_permission(self, permission: PortalPermission, *, unit_id: str) -> None:
        assert permission is PortalPermission.DOCUMENT_QUERY
        assert unit_id == "unit-a"


class _Uow:
    def __init__(self, archive: InMemoryFiscalArchiveStore) -> None:
        self.archive = archive

    def __enter__(self) -> _Uow:
        return self

    def __exit__(self, *_args: object) -> None:
        pass


def test_xml_danfe_and_tenant_isolation() -> None:
    scope = ExecutionScope(
        host_namespace="fm-nfcore", tenant_id="tenant-a", unit_id="unit-a",
        environment=FiscalEnvironment.HOMOLOGATION, correlation_id="test",
    )
    archive = InMemoryFiscalArchiveStore()
    archive.append(FiscalArchiveEntry.build(
        scope=scope, document_reference="NF-123",
        kind=FiscalArchiveKind.AUTHORIZED_XML,
        content=b"<nfeProc/>", media_type="application/xml",
        archived_at=datetime.now(UTC),
        retention=RetentionPolicyMetadata(policy_id="test", policy_version=1),
    ))
    executor = DurableHumanPortalExecutor(
        cast(FiscalUnitOfWorkFactory, lambda: _Uow(archive))
    )

    def read(tenant: str, kind: FiscalArchiveKind) -> tuple[bytes, str]:
        return executor.fiscal_artifact(
            authority=cast(AuthenticatedHuman, _Authorized(tenant)),
            unit_id="unit-a", environment=FiscalEnvironment.HOMOLOGATION,
            document_reference="NF-123", kind=kind,
        )

    assert read("tenant-a", FiscalArchiveKind.AUTHORIZED_XML) == (
        b"<nfeProc/>", "application/xml"
    )
    with pytest.raises(HTTPException) as different_tenant:
        read("tenant-b", FiscalArchiveKind.AUTHORIZED_XML)
    assert different_tenant.value.status_code == 404
    with pytest.raises(HTTPException) as not_archived:
        read("tenant-a", FiscalArchiveKind.DANFE)
    assert not_archived.value.status_code == 404
    with pytest.raises(HTTPException) as forbidden_kind:
        read("tenant-a", FiscalArchiveKind.OTHER)
    assert forbidden_kind.value.status_code == 400


def test_danfe_is_rendered_only_after_scoped_authorized_xml_lookup() -> None:
    scope = ExecutionScope(
        host_namespace="fm-nfcore", tenant_id="tenant-a", unit_id="unit-a",
        environment=FiscalEnvironment.HOMOLOGATION, correlation_id="pdf-test",
    )
    archive = InMemoryFiscalArchiveStore()
    xml = b"<nfeProc versao='4.00'/>"
    archive.append(FiscalArchiveEntry.build(
        scope=scope, document_reference="NF-123",
        kind=FiscalArchiveKind.AUTHORIZED_XML,
        content=xml, media_type="application/xml",
        archived_at=datetime.now(UTC),
        retention=RetentionPolicyMetadata(policy_id="test", policy_version=1),
    ))
    observed: list[bytes] = []

    def mock_renderer(document: bytes) -> bytes:
        observed.append(document)
        return b"%PDF-1.7\\nNFCore test"

    executor = DurableHumanPortalExecutor(
        cast(FiscalUnitOfWorkFactory, lambda: _Uow(archive)),
        danfe_renderer=mock_renderer,
    )

    def render(tenant: str) -> tuple[bytes, str]:
        return executor.fiscal_artifact(
            authority=cast(AuthenticatedHuman, _Authorized(tenant)),
            unit_id="unit-a", environment=FiscalEnvironment.HOMOLOGATION,
            document_reference="NF-123", kind=FiscalArchiveKind.DANFE,
        )

    assert render("tenant-a") == (b"%PDF-1.7\\nNFCore test", "application/pdf")
    assert observed == [xml]
    with pytest.raises(HTTPException) as foreign:
        render("different-tenant")
    assert foreign.value.status_code == 404
    assert observed == [xml]
