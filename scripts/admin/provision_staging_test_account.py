"""Governed one-off staging account provisioning for NFCore activation E2E.

This command never writes identity rows directly. It reuses the canonical PostgreSQL
runtime composition, CommercialCustomerProvisioningService, PasswordRecoveryService,
and the configured PasswordResetDelivery adapter.

The command is deliberately staging-only and requires an explicit operational approval
gate before it can run.
"""

from __future__ import annotations

import argparse
import os
from datetime import UTC, datetime

from kordena_fiscal.persistence.postgres import PostgresFiscalDatabase
from kordena_fiscal.runtime.activation_email import build_activation_delivery_from_environ
from kordena_fiscal.runtime.composition import build_postgres_runtime_composition


def _require_staging_approval() -> None:
    environment = os.getenv("NFCORE_ENVIRONMENT", "").strip().casefold()
    if environment != "staging":
        raise RuntimeError("staging test account provisioning is restricted to staging")
    if os.getenv("NFCORE_STAGING_TEST_ACCOUNT_APPROVED", "").casefold() != "true":
        raise RuntimeError(
            "staging test account provisioning blocked: "
            "NFCORE_STAGING_TEST_ACCOUNT_APPROVED=true required"
        )


def run(*, email: str, tenant_id: str, legal_name: str) -> str:
    _require_staging_approval()

    normalized_email = email.strip().casefold()
    normalized_tenant = tenant_id.strip().lower()
    normalized_name = legal_name.strip()
    if not normalized_email or "@" not in normalized_email:
        raise ValueError("email must be a valid email identity")
    if not normalized_tenant or not normalized_name:
        raise ValueError("tenant_id and legal_name are required")

    dsn = os.getenv("DATABASE_URL", "").strip()
    if not dsn:
        raise RuntimeError(
            "staging test account provisioning blocked: DATABASE_URL is required"
        )

    database = PostgresFiscalDatabase(dsn)
    try:
        composition = build_postgres_runtime_composition(database)
        existing = database.human_accounts().by_email(normalized_email)
        now = datetime.now(UTC)

        action = "recovery"
        if existing is None:
            result = composition.commercial_provisioning.provision(
                tenant_id=normalized_tenant,
                legal_name=normalized_name,
                owner_email=normalized_email,
                correlation_id=f"staging-e2e:{normalized_tenant}",
                now=now,
            )
            reset = result.activation_reset
            action = "created"
        else:
            if not existing.enabled:
                raise RuntimeError("existing staging account is disabled")
            reset = composition.password_recovery.request_reset(
                email=normalized_email,
                now=now,
            )

        if reset is None:
            raise RuntimeError("canonical password reset was not issued")

        delivery = build_activation_delivery_from_environ()
        if delivery is None:
            raise RuntimeError("activation delivery is not configured")

        delivery.deliver(email=normalized_email, reset=reset)
        print(f"staging test account activation: PASS action={action}")
        return action
    finally:
        database.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", required=True)
    parser.add_argument("--tenant-id", default="nfcore-staging-e2e")
    parser.add_argument("--legal-name", default="NFCore Staging E2E Test")
    args = parser.parse_args()

    run(
        email=args.email,
        tenant_id=args.tenant_id,
        legal_name=args.legal_name,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
