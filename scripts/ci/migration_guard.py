"""Govern schema migration execution for staging and production runtimes."""

from __future__ import annotations

import argparse
import hashlib
import os
import re

from kordena_fiscal.persistence.cakto import (
    CAKTO_SCHEMA_NAME,
    CAKTO_SCHEMA_STATEMENTS,
    CAKTO_SCHEMA_VERSION,
)
from kordena_fiscal.persistence.postgres import (
    _COMMERCIAL_RELEASE_SCHEMA,
    _PRICING_SCHEMA,
    PostgresFiscalDatabase,
)
from kordena_fiscal.persistence.sqlite import _MIGRATIONS

_DESTRUCTIVE = re.compile(
    r"\b(?:DROP\s+(?:TABLE|SCHEMA|DATABASE|COLUMN)|TRUNCATE|DELETE\s+FROM)\b",
    re.IGNORECASE,
)
# Migration 5 predates WP-WEB-09 and was already certified. Its destructive step is
# fingerprint-pinned so changing it, or adding any new destructive migration, fails closed.
_APPROVED_LEGACY_DESTRUCTIVE = {
    (
        5,
        "51652667759562a46b810dde224253444c5dc93916a601dc36205d3f4a8441d5",
    ),
}


def _statement_fingerprint(statement: str) -> str:
    normalized = " ".join(statement.split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _reject_unapproved_destructive(
    *,
    version: int,
    name: str,
    statements: tuple[str, ...],
) -> None:
    for statement in statements:
        if not _DESTRUCTIVE.search(statement):
            continue
        fingerprint = _statement_fingerprint(statement)
        if (version, fingerprint) not in _APPROVED_LEGACY_DESTRUCTIVE:
            raise RuntimeError(
                f"destructive migration blocked: version={version} name={name}"
            )


def validate_policy() -> tuple[int, ...]:
    versions = tuple(migration.version for migration in _MIGRATIONS) + (
        PostgresFiscalDatabase.HUMAN_MIGRATION_VERSION,
        PostgresFiscalDatabase.PRICING_MIGRATION_VERSION,
        PostgresFiscalDatabase.COMMERCIAL_RELEASE_MIGRATION_VERSION,
    )
    if versions != tuple(range(1, max(versions) + 1)):
        raise RuntimeError(f"migration versions must be contiguous from 1: {versions!r}")

    for migration in _MIGRATIONS:
        _reject_unapproved_destructive(
            version=migration.version,
            name=migration.name,
            statements=migration.statements,
        )
    _reject_unapproved_destructive(
        version=PostgresFiscalDatabase.PRICING_MIGRATION_VERSION,
        name=PostgresFiscalDatabase.PRICING_MIGRATION_NAME,
        statements=_PRICING_SCHEMA,
    )
    _reject_unapproved_destructive(
        version=PostgresFiscalDatabase.COMMERCIAL_RELEASE_MIGRATION_VERSION,
        name=PostgresFiscalDatabase.COMMERCIAL_RELEASE_MIGRATION_NAME,
        statements=_COMMERCIAL_RELEASE_SCHEMA,
    )
    _reject_unapproved_destructive(
        version=CAKTO_SCHEMA_VERSION,
        name=CAKTO_SCHEMA_NAME,
        statements=CAKTO_SCHEMA_STATEMENTS,
    )
    print(
        "migration policy: PASS "
        f"versions={','.join(str(item) for item in versions)} "
        f"cakto_schema={CAKTO_SCHEMA_VERSION}"
    )
    return versions


def _require_apply_approval(environment: str) -> None:
    if os.getenv("NFCORE_SCHEMA_MIGRATION_APPROVED", "").casefold() != "true":
        raise RuntimeError(
            "schema migration blocked: NFCORE_SCHEMA_MIGRATION_APPROVED=true required"
        )
    production_approval = os.getenv("NFCORE_PRODUCTION_APPROVAL")
    if environment == "production" and production_approval != "PRODUCTION_APPROVED":
        raise RuntimeError(
            "production migration blocked: "
            "NFCORE_PRODUCTION_APPROVAL=PRODUCTION_APPROVED required"
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
