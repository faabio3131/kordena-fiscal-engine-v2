"""Govern schema migration execution for staging and production runtimes."""

from __future__ import annotations

import argparse
import os
import re

from kordena_fiscal.persistence.postgres import PostgresFiscalDatabase
from kordena_fiscal.persistence.sqlite import _MIGRATIONS

_DESTRUCTIVE = re.compile(
    r"\b(?:DROP\s+(?:TABLE|SCHEMA|DATABASE|COLUMN)|TRUNCATE|DELETE\s+FROM)\b",
    re.IGNORECASE,
)


def validate_policy() -> tuple[int, ...]:
    versions = tuple(migration.version for migration in _MIGRATIONS) + (
        PostgresFiscalDatabase.HUMAN_MIGRATION_VERSION,
    )
    if versions != tuple(range(1, max(versions) + 1)):
        raise RuntimeError(f"migration versions must be contiguous from 1: {versions!r}")

    for migration in _MIGRATIONS:
        for statement in migration.statements:
            if _DESTRUCTIVE.search(statement):
                raise RuntimeError(
                    f"destructive migration blocked: version={migration.version} "
                    f"name={migration.name}"
                )
    print(f"migration policy: PASS versions={','.join(str(item) for item in versions)}")
    return versions


def _require_apply_approval(environment: str) -> None:
    if os.getenv("NFCORE_SCHEMA_MIGRATION_APPROVED", "").casefold() != "true":
        raise RuntimeError("schema migration blocked: NFCORE_SCHEMA_MIGRATION_APPROVED=true required")
    if environment == "production" and os.getenv("NFCORE_PRODUCTION_APPROVAL") != "PRODUCTION_APPROVED":
        raise RuntimeError(
            "production migration blocked: NFCORE_PRODUCTION_APPROVAL=PRODUCTION_APPROVED required"
        )


def apply() -> None:
    validate_policy()
    environment = os.getenv("NFCORE_ENVIRONMENT", "").strip().casefold()
    if environment not in {"staging", "production"}:
        raise RuntimeError("schema migration apply is restricted to staging/production profiles")
    _require_apply_approval(environment)
    dsn = os.getenv("DATABASE_URL", "").strip()
    if not dsn:
        raise RuntimeError("schema migration blocked: DATABASE_URL is required")

    database = PostgresFiscalDatabase(dsn)
    try:
        before = database.applied_migrations()
        applied = database.initialize()
        after = database.applied_migrations()
    finally:
        database.close()
    print(
        "schema migration: PASS "
        f"environment={environment} before={before} applied={applied} after={after}"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--check-policy", action="store_true")
    action.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    if args.check_policy:
        validate_policy()
    else:
        apply()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
