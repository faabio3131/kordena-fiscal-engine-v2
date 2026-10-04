"""Production composition root for canonical NFCORE application services.

This module only wires already-certified boundaries. It does not create a second auth,
portal, billing, fiscal authority or secret system. Raw secret material remains outside
this composition root and fiscal production authority is injected independently.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from kordena_fiscal.application.commercial_activation import (
    CommercialCustomerActivationService,
)
from kordena_fiscal.application.commercial_claim import CommercialClaimService
from kordena_fiscal.application.commercial_fulfillment import CommercialFulfillmentService
from kordena_fiscal.application.commercial_trial import GovernedTrialService
from kordena_fiscal.control_plane.cakto_checkout import (
    CaktoCheckoutAdministrationService,
)
from kordena_fiscal.control_plane.commercial_release import (
    CommercialReleaseAdministrationService,
)
from kordena_fiscal.control_plane.pricing_admin import CommercialPricingAdministrationService
from kordena_fiscal.persistence.cakto import postgres_cakto_commercial_database
from kordena_fiscal.persistence.commercial_fulfillment import (
    postgres_canonical_commercial_database,
)
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
    commercial_fulfillment: CommercialFulfillmentService
    commercial_claim: CommercialClaimService
    commercial_activation: CommercialCustomerActivationService
    commercial_trial: GovernedTrialService
    pricing_administration: CommercialPricingAdministrationService
    commercial_release_administration: CommercialReleaseAdministrationService
    cakto_checkout_administration: CaktoCheckoutAdministrationService | None
    portal_executor: DurableHumanPortalExecutor


def build_postgres_runtime_composition(
    database: PostgresFiscalDatabase,
    *,
    portal_operation_executor: PortalOperationExecutor | None = None,
    enable_cakto_checkout: bool = False,
    password_reset_ttl: timedelta = timedelta(minutes=10),
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
        reset_ttl=password_reset_ttl,
    )
    provisioning = CommercialCustomerProvisioningService(
        unit_of_work_factory=database,
        accounts=accounts,
        password_hasher=password_hasher,
        password_recovery=recovery,
    )
    canonical_commercial_database = postgres_canonical_commercial_database(database)
    commercial_fulfillment = CommercialFulfillmentService(
        canonical_commercial_database
    )
    commercial_claim = CommercialClaimService(
        unit_of_work_factory=canonical_commercial_database,
        accounts=accounts,
    )
    pricing_administration = CommercialPricingAdministrationService(
        database.pricing_catalog()
    )
    commercial_activation = CommercialCustomerActivationService(
        unit_of_work_factory=canonical_commercial_database,
        provisioning=provisioning,
        password_recovery=recovery,
        pricing=pricing_administration,
    )
    commercial_trial = GovernedTrialService(
        unit_of_work_factory=canonical_commercial_database,
        activation=commercial_activation,
        pricing=pricing_administration,
        accounts=accounts,
    )
    commercial_release_administration = CommercialReleaseAdministrationService(
        database.commercial_release_catalog()
    )
    cakto_checkout_administration: CaktoCheckoutAdministrationService | None = None
    if enable_cakto_checkout:
        cakto_commercial_database = postgres_cakto_commercial_database(database)
        cakto_commercial_database.initialize()
        cakto_checkout_administration = CaktoCheckoutAdministrationService(
            cakto_commercial_database
        )
    portal = DurableHumanPortalExecutor(
        database,
        operation_executor=portal_operation_executor,
    )
    return RuntimeComposition(
        human_identity=identity,
        password_recovery=recovery,
        commercial_provisioning=provisioning,
        commercial_fulfillment=commercial_fulfillment,
        commercial_claim=commercial_claim,
        commercial_activation=commercial_activation,
        commercial_trial=commercial_trial,
        pricing_administration=pricing_administration,
        commercial_release_administration=commercial_release_administration,
        cakto_checkout_administration=cakto_checkout_administration,
        portal_executor=portal,
    )
