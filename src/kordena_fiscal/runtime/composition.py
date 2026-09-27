"""Production composition root for canonical NFCORE application services.

This module only wires already-certified boundaries. It does not create a second auth,
portal, billing, fiscal authority or secret system. Raw secret material remains outside
this composition root and fiscal production authority is injected independently.
"""

from __future__ import annotations

from dataclasses import dataclass

from kordena_fiscal.control_plane.commercial_release import (
    CommercialReleaseAdministrationService,
)
from kordena_fiscal.control_plane.pricing_admin import CommercialPricingAdministrationService
from kordena_fiscal.persistence.postgres import PostgresFiscalDatabase
from kordena_fiscal.security.human_identity import (
    HumanIdentityService,
    LoginAttemptLimiter,
    ScryptPasswordHasher,
)
from kordena_fiscal.security.human_recovery import PasswordRecoveryService
from kordena_fiscal.web.portal_runtime import (
    DurableHumanPortalExecutor,
    PortalOperationExecutor,
)

from .commercial_provisioning import CommercialCustomerProvisioningService


@dataclass(frozen=True, slots=True)
class RuntimeComposition:
    """Canonical durable services owned by one runtime database lifecycle."""

    human_identity: HumanIdentityService
    password_recovery: PasswordRecoveryService
    commercial_provisioning: CommercialCustomerProvisioningService
    pricing_administration: CommercialPricingAdministrationService
    commercial_release_administration: CommercialReleaseAdministrationService
    portal_executor: DurableHumanPortalExecutor


def build_postgres_runtime_composition(
    database: PostgresFiscalDatabase,
    *,
    portal_operation_executor: PortalOperationExecutor | None = None,
) -> RuntimeComposition:
    """Compose human web services over the canonical PostgreSQL repositories."""

    accounts = database.human_accounts()
    sessions = database.web_sessions()
    password_resets = database.password_resets()
    password_hasher = ScryptPasswordHasher()

    identity = HumanIdentityService(
        accounts=accounts,
        sessions=sessions,
        password_hasher=password_hasher,
        login_limiter=LoginAttemptLimiter(),
    )
    recovery = PasswordRecoveryService(
        accounts=accounts,
        sessions=sessions,
        resets=password_resets,
        password_hasher=password_hasher,
    )
    provisioning = CommercialCustomerProvisioningService(
        unit_of_work_factory=database,
        accounts=accounts,
        password_hasher=password_hasher,
        password_recovery=recovery,
    )
    pricing_administration = CommercialPricingAdministrationService(
        database.pricing_catalog()
    )
    commercial_release_administration = CommercialReleaseAdministrationService(
        database.commercial_release_catalog()
    )
    portal = DurableHumanPortalExecutor(
        database,
        operation_executor=portal_operation_executor,
    )
    return RuntimeComposition(
        human_identity=identity,
        password_recovery=recovery,
        commercial_provisioning=provisioning,
        pricing_administration=pricing_administration,
        commercial_release_administration=commercial_release_administration,
        portal_executor=portal,
    )
