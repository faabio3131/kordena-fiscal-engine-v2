"""Trusted commercial provisioning for a newly acquired NFCORE customer.

This boundary is intentionally not a browser self-signup endpoint. Creating an organization is
a privileged Control Plane operation, so an authenticated FM commercial ingress (for example the
website/Cakto orchestration) must call this service after purchase/trial validation. The service
reuses the canonical Control Plane, human-account repository and password-recovery service.
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass

from kordena_fiscal.control_plane.durable import DurableControlPlaneService
from kordena_fiscal.control_plane.models import AdminPrincipal, ControlPlanePermission
from kordena_fiscal.control_plane.service import ControlPlaneConflictError
from kordena_fiscal.persistence.ports import FiscalUnitOfWorkFactory
from kordena_fiscal.security.human_identity import (
    HumanAccount,
    HumanAccountRepository,
    PortalRole,
    ScryptPasswordHasher,
)
from kordena_fiscal.security.human_recovery import (
    IssuedPasswordReset,
    PasswordRecoveryService,
)


class CommercialProvisioningError(ValueError):
    """Trusted commercial provisioning could not preserve canonical identity invariants."""


@dataclass(frozen=True, slots=True)
class CommercialCustomerProvisioningResult:
    tenant_id: str
    account_id: str
    organization_created: bool
    account_created: bool
    activation_reset: IssuedPasswordReset | None

    def __repr__(self) -> str:
        return (
            "CommercialCustomerProvisioningResult("
            f"tenant_id={self.tenant_id!r}, account_id={self.account_id!r}, "
            f"organization_created={self.organization_created!r}, "
            f"account_created={self.account_created!r}, activation_reset=<redacted>)"
        )


class CommercialCustomerProvisioningService:
    """Idempotently create the canonical organization and first owner account."""

    def __init__(
        self,
        *,
        unit_of_work_factory: FiscalUnitOfWorkFactory,
        accounts: HumanAccountRepository,
        password_hasher: ScryptPasswordHasher,
        password_recovery: PasswordRecoveryService,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._accounts = accounts
        self._password_hasher = password_hasher
        self._password_recovery = password_recovery

    def provision(
        self,
        *,
        tenant_id: str,
        legal_name: str,
        owner_email: str,
        correlation_id: str,
        now,
    ) -> CommercialCustomerProvisioningResult:
        normalized_tenant = tenant_id.strip().lower()
        normalized_name = legal_name.strip()
        normalized_email = owner_email.strip().casefold()
        normalized_correlation = correlation_id.strip()
        if not normalized_tenant or not normalized_name or not normalized_correlation:
            raise CommercialProvisioningError(
                "tenant_id, legal_name and correlation_id are required"
            )
        if "@" not in normalized_email:
            raise CommercialProvisioningError("owner_email must be a valid email identity")
        if now.tzinfo is None or now.utcoffset() is None:
            raise CommercialProvisioningError("now must be timezone-aware")

        control_plane = DurableControlPlaneService(self._unit_of_work_factory)
        with self._unit_of_work_factory() as uow:
            existing_organization = uow.control_plane.get_organization(normalized_tenant)

        organization_created = False
        if existing_organization is None:
            try:
                control_plane.onboard_organization(
                    actor=AdminPrincipal(
                        actor_id="commercial-provisioner",
                        permissions=frozenset(
                            {ControlPlanePermission.ORGANIZATION_WRITE}
                        ),
                        global_scope=True,
                    ),
                    tenant_id=normalized_tenant,
                    legal_name=normalized_name,
                    correlation_id=normalized_correlation,
                )
            except ControlPlaneConflictError:
                # Concurrent provisioning may win between our read and write. Re-read and
                # validate exact identity instead of creating parallel state.
                with self._unit_of_work_factory() as uow:
                    existing_organization = uow.control_plane.get_organization(
                        normalized_tenant
                    )
                if (
                    existing_organization is None
                    or existing_organization.legal_name != normalized_name
                ):
                    raise CommercialProvisioningError(
                        "commercial organization conflicts with existing canonical state"
                    ) from None
            else:
                organization_created = True
        elif existing_organization.legal_name != normalized_name:
            raise CommercialProvisioningError(
                "commercial organization conflicts with existing canonical state"
            )

        expected_account_id = self._account_id(normalized_tenant, normalized_email)
        existing_account = self._accounts.by_email(normalized_email)
        account_created = False
        if existing_account is None:
            initial_password = secrets.token_urlsafe(48)
            account = HumanAccount(
                account_id=expected_account_id,
                email=normalized_email,
                password_hash=self._password_hasher.hash(initial_password),
                tenant_id=normalized_tenant,
                role=PortalRole.OWNER,
                unit_ids=None,
            )
            self._accounts.save(account)
            account_created = True
        else:
            exact_identity = (
                existing_account.account_id == expected_account_id
                and existing_account.tenant_id == normalized_tenant
                and existing_account.role is PortalRole.OWNER
                and existing_account.enabled
            )
            if not exact_identity:
                raise CommercialProvisioningError(
                    "owner email conflicts with existing canonical account"
                )

        activation = None
        if account_created:
            activation = self._password_recovery.request_reset(
                email=normalized_email,
                now=now,
            )
            if activation is None:
                raise CommercialProvisioningError(
                    "new commercial owner account did not produce activation reset"
                )

        return CommercialCustomerProvisioningResult(
            tenant_id=normalized_tenant,
            account_id=expected_account_id,
            organization_created=organization_created,
            account_created=account_created,
            activation_reset=activation,
        )

    @staticmethod
    def _account_id(tenant_id: str, email: str) -> str:
        digest = hashlib.sha256(f"{tenant_id}|{email}".encode("utf-8")).hexdigest()
        return f"commercial-owner-{digest[:32]}"
