"""Internal serialization helpers shared by SQLite persistence adapters."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import cast

from kordena_fiscal.domain import ExecutionScope, FiscalEnvironment, FiscalValidationError

from .ports import PersistenceStateError


def host_key(value: str | None) -> str:
    return value or ""


def scoped_page(scope: ExecutionScope, limit: int, offset: int) -> tuple[object, ...]:
    """Exact partition plus a bounded page; correlation does not select ownership."""
    if not isinstance(scope, ExecutionScope):
        raise FiscalValidationError("scope must be ExecutionScope")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
        raise FiscalValidationError("limit must be an integer between 1 and 100")
    if isinstance(offset, bool) or not isinstance(offset, int) or not 0 <= offset <= 10000:
        raise FiscalValidationError("offset must be an integer between 0 and 10000")
    return (
        host_key(scope.host_namespace),
        scope.tenant_id,
        scope.unit_id,
        scope.environment.value,
        limit,
        offset,
    )


def host_or_none(value: str) -> str | None:
    return value or None


def iso(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise FiscalValidationError("persisted datetime must be timezone-aware")
    return value.isoformat()


def dt(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise PersistenceStateError("persisted datetime is not timezone-aware")
    return parsed


def text(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise PersistenceStateError(f"persisted {field_name} must be text")
    return value


def integer(value: object, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise PersistenceStateError(f"persisted {field_name} must be integer")
    return value


def blob(value: object, field_name: str) -> bytes:
    if not isinstance(value, bytes):
        raise PersistenceStateError(f"persisted {field_name} must be bytes")
    return value


def optional_text(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    return text(value, field_name)


def one_row(cursor: sqlite3.Cursor) -> tuple[object, ...] | None:
    value = cursor.fetchone()
    if value is None:
        return None
    return cast(tuple[object, ...], value)


def scope_from_values(
    host_namespace: object,
    tenant_id: object,
    unit_id: object,
    environment: object,
    correlation_id: object,
) -> ExecutionScope:
    return ExecutionScope(
        host_namespace=host_or_none(text(host_namespace, "host_namespace")),
        tenant_id=text(tenant_id, "tenant_id"),
        unit_id=text(unit_id, "unit_id"),
        environment=FiscalEnvironment(text(environment, "environment")),
        correlation_id=text(correlation_id, "correlation_id"),
    )


def validate_sha256(value: str, field_name: str) -> str:
    normalized = value.strip().lower()
    if len(normalized) != 64:
        raise FiscalValidationError(f"{field_name} must be SHA-256 hex")
    try:
        int(normalized, 16)
    except ValueError as exc:
        raise FiscalValidationError(f"{field_name} must be hexadecimal") from exc
    return normalized
