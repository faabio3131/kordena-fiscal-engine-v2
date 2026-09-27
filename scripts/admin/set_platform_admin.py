"""Governed bootstrap for assigning explicit NFCORE platform administration.

This script never creates an account, accepts a password, or infers platform authority
from a tenant role. It only toggles the explicit platform_admin flag on an existing
canonical human account after an operational approval environment gate.
"""

from __future__ import annotations

import argparse
import os
from dataclasses import replace

from kordena_fiscal.persistence.postgres import PostgresFiscalDatabase


def run(*, account_id: str, enabled: bool) -> None:
    if os.getenv("NFCORE_PLATFORM_ADMIN_CHANGE_APPROVED", "").casefold() != "true":
        raise RuntimeError(
            "platform admin change blocked: "
            "NFCORE_PLATFORM_ADMIN_CHANGE_APPROVED=true required"
        )
    dsn = os.getenv("DATABASE_URL", "").strip()
    if not dsn:
        raise RuntimeError("platform admin change blocked: DATABASE_URL is required")

    database = PostgresFiscalDatabase(dsn)
    try:
        if PostgresFiscalDatabase.PRICING_MIGRATION_VERSION not in database.applied_migrations():
            raise RuntimeError(
                "platform admin change blocked: pricing/platform-admin migration is not applied"
            )
        repository = database.human_accounts()
        account = repository.by_id(account_id.strip())
        if account is None:
            raise RuntimeError("platform admin change blocked: account does not exist")
        repository.save(replace(account, platform_admin=enabled))
    finally:
        database.close()

    state = "enabled" if enabled else "disabled"
    print(f"platform admin authority: {state} account_id={account_id.strip()}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--account-id", required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--enable", action="store_true")
    mode.add_argument("--disable", action="store_true")
    args = parser.parse_args()
    run(account_id=args.account_id, enabled=bool(args.enable))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
