"""A-01: one canonical database and fiscal-binding authority for Bling installations."""
from __future__ import annotations

from pathlib import Path

import pytest

from kordena_fiscal.application.service import FiscalApplicationService
from kordena_fiscal.domain import (
    FiscalAccountBinding,
    FiscalAccountId,
    FiscalEnvironment,
    FiscalUnitId,
    FiscalValidationError,
    HostNamespace,
    HostScope,
)
from kordena_fiscal.integrations.bling_contracts import BlingInstallationState
from kordena_fiscal.persistence.bling_installations import BlingInstallationRepository
from kordena_fiscal.persistence.ports import PersistenceConflictError
from kordena_fiscal.persistence.sqlite import SqliteFiscalDatabase


def registered_database(tmp_path: Path) -> SqliteFiscalDatabase:
    db = SqliteFiscalDatabase(tmp_path / "bling-multitenant.sqlite")
    db.initialize()
    with db() as uow:
        for tenant in ("t1", "t2"):
            for unit in ("u1", "u2"):
                uow.bindings.add(FiscalAccountBinding(
                    binding_id=f"binding-{tenant}-{unit}",
                    host_scope=HostScope(HostNamespace("bling"), tenant, unit),
                    fiscal_account_id=FiscalAccountId(f"fiscal-{tenant}"),
                    fiscal_unit_id=FiscalUnitId(f"fiscal-{unit}"),
                ))
        uow.commit()
    return db


def scoped(db: SqliteFiscalDatabase, tenant: str, unit: str):
    return FiscalApplicationService(db).resolve_scope(
        HostScope(HostNamespace("bling"), tenant, unit),
        environment=FiscalEnvironment.HOMOLOGATION,
        correlation_id="test-a01",
    )


def test_multitenant_multiunit_scoped_installations(tmp_path: Path) -> None:
    db = registered_database(tmp_path)
    store = BlingInstallationRepository(db)
    installations = {}
    for tenant in ("t1", "t2"):
        for unit in ("u1", "u2"):
            view = store.create(
                host_scope=HostScope(HostNamespace("bling"), tenant, unit),
                company_id="same-provider-company",
                environment=FiscalEnvironment.HOMOLOGATION,
            )
            installations[(tenant, unit)] = view
            assert view.state is BlingInstallationState.NOT_CONFIGURED
    for tenant in ("t1", "t2"):
        for unit in ("u1", "u2"):
            scope = scoped(db, tenant, unit)
            current = installations[(tenant, unit)]
            assert store.get_for_scope(scope, current.installation_id) == current
            assert store.host_binding(current.installation_id) == HostScope(
                HostNamespace("bling"), tenant, unit
            )
            assert len(store.list_for_scope(scope)[0]) == 1
            for other, item in installations.items():
                if other != (tenant, unit):
                    assert store.get_for_scope(scope, item.installation_id) is None


def test_cas_rejects_concurrent_transition_and_duplicate_binding(tmp_path: Path) -> None:
    db = registered_database(tmp_path)
    store = BlingInstallationRepository(db)
    host = HostScope(HostNamespace("bling"), "t1", "u1")
    created = store.create(host_scope=host, company_id="company", environment=FiscalEnvironment.HOMOLOGATION)
    with pytest.raises(PersistenceConflictError):
        store.create(host_scope=host, company_id="company", environment=FiscalEnvironment.HOMOLOGATION)
    scope = scoped(db, "t1", "u1")
    connected = store.transition(scope, created.installation_id, expected_revision=1, state=BlingInstallationState.CONNECTED)
    assert connected.revision == 2
    with pytest.raises(PersistenceConflictError):
        store.transition(scope, created.installation_id, expected_revision=1, state=BlingInstallationState.PAUSED)
    assert store.get_for_scope(scope, created.installation_id).state is BlingInstallationState.CONNECTED


def test_pagination_cursor_and_invalid_host_binding_fail_closed(tmp_path: Path) -> None:
    db = registered_database(tmp_path)
    store = BlingInstallationRepository(db)
    host = HostScope(HostNamespace("bling"), "t1", "u1")
    for name in ("a", "b", "c"):
        store.create(host_scope=host, company_id=name, environment=FiscalEnvironment.HOMOLOGATION)
    scope = scoped(db, "t1", "u1")
    seen = []
    cursor = None
    while True:
        rows, cursor = store.list_for_scope(scope, cursor=cursor, limit=1)
        seen.extend(item.installation_id for item in rows)
        if cursor is None:
            break
    assert len(seen) == len(set(seen)) == 3
    with pytest.raises(FiscalValidationError):
        store.list_for_scope(scoped(db, "t2", "u1"), cursor="invalid", limit=1)
    with pytest.raises(FiscalValidationError):
        store.create(
            host_scope=HostScope(HostNamespace("bling"), "ghost", "u1"),
            company_id="unbound", environment=FiscalEnvironment.HOMOLOGATION,
        )
