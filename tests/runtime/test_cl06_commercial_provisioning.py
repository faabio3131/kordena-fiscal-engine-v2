from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from kordena_fiscal.persistence import SqliteFiscalDatabase
from kordena_fiscal.runtime.commercial_provisioning import (
    CommercialCustomerProvisioningService,
    CommercialProvisioningError,
)
from kordena_fiscal.security.human_identity import (
    HumanAccount,
    InMemoryHumanAccountRepository,
    InMemoryWebSessionRepository,
    PortalRole,
    ScryptPasswordHasher,
)
from kordena_fiscal.security.human_recovery import (
    InMemoryPasswordResetRepository,
    PasswordRecoveryService,
)

NOW = datetime(2026, 9, 16, 18, 15, tzinfo=UTC)


def _service(tmp_path: Path) -> tuple[
    CommercialCustomerProvisioningService,
    SqliteFiscalDatabase,
    InMemoryHumanAccountRepository,
]:
    database = SqliteFiscalDatabase(tmp_path / "commercial-provisioning.sqlite3")
    database.initialize()
    accounts = InMemoryHumanAccountRepository()
    sessions = InMemoryWebSessionRepository()
    hasher = ScryptPasswordHasher()
    recovery = PasswordRecoveryService(
        accounts=accounts,
        sessions=sessions,
        resets=InMemoryPasswordResetRepository(),
        password_hasher=hasher,
    )
    return (
        CommercialCustomerProvisioningService(
            unit_of_work_factory=database,
            accounts=accounts,
            password_hasher=hasher,
            password_recovery=recovery,
        ),
        database,
        accounts,
    )


def test_trusted_provisioning_creates_canonical_org_owner_and_activation_once(
    tmp_path: Path,
) -> None:
    service, database, accounts = _service(tmp_path)

    first = service.provision(
        tenant_id="Acme-Fiscal",
        legal_name="Acme Fiscal Ltda",
        owner_email="Owner@Acme.example",
        correlation_id="purchase-cakto-123",
        now=NOW,
    )
    repeated = service.provision(
        tenant_id="acme-fiscal",
        legal_name="Acme Fiscal Ltda",
        owner_email="owner@acme.example",
        correlation_id="purchase-cakto-123-retry",
        now=NOW,
    )

    assert first.organization_created is True
    assert first.account_created is True
    assert first.activation_reset is not None
    assert "reset_token=<redacted>" in repr(first.activation_reset)
    assert repeated.organization_created is False
    assert repeated.account_created is False
    assert repeated.activation_reset is None
    assert repeated.account_id == first.account_id

    with database.unit_of_work() as uow:
        organization = uow.control_plane.get_organization("acme-fiscal")
    assert organization is not None
    assert organization.legal_name == "Acme Fiscal Ltda"

    owner = accounts.by_email("owner@acme.example")
    assert owner is not None
    assert owner.tenant_id == "acme-fiscal"
    assert owner.role is PortalRole.OWNER
    assert owner.unit_ids is None


def test_trusted_provisioning_rejects_owner_email_cross_tenant_collision(
    tmp_path: Path,
) -> None:
    service, _database, accounts = _service(tmp_path)
    hasher = ScryptPasswordHasher()
    accounts.save(
        HumanAccount(
            account_id="existing-owner",
            email="owner@example.com",
            password_hash=hasher.hash("existing-owner-password-2026"),
            tenant_id="other-tenant",
            role=PortalRole.OWNER,
        )
    )

    with pytest.raises(CommercialProvisioningError, match="owner email conflicts"):
        service.provision(
            tenant_id="new-tenant",
            legal_name="New Tenant Ltda",
            owner_email="owner@example.com",
            correlation_id="commercial-collision",
            now=NOW,
        )


def test_trusted_provisioning_rejects_conflicting_organization_identity(
    tmp_path: Path,
) -> None:
    service, _database, _accounts = _service(tmp_path)
    service.provision(
        tenant_id="same-tenant",
        legal_name="Original Legal Name Ltda",
        owner_email="owner@same.example",
        correlation_id="first",
        now=NOW,
    )

    with pytest.raises(CommercialProvisioningError, match="organization conflicts"):
        service.provision(
            tenant_id="same-tenant",
            legal_name="Different Legal Name Ltda",
            owner_email="owner@same.example",
            correlation_id="second",
            now=NOW,
        )
