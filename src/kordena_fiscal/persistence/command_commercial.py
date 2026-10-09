"""Governed Command bindings and durable inbox on the existing PostgreSQL boundary."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime

from kordena_fiscal.control_plane.models import AdminPrincipal, ControlPlanePermission
from kordena_fiscal.persistence.commercial_fulfillment import ConnectionContextFactory
from kordena_fiscal.product.command_commercial import CommandBinding, CommandCommercialEvent
from kordena_fiscal.product.commercial_fulfillment import CommercialFulfillmentError


class CommandCommercialStore:
    def __init__(self, acquire: ConnectionContextFactory) -> None:
        self._acquire = acquire

    def binding(self, key_id: str) -> tuple[CommandBinding, int] | None:
        with self._acquire() as connection:
            connection.execute("SET LOCAL statement_timeout = '2s'")
            row = connection.execute(
                "SELECT binding_json, revision FROM fm_command_bindings WHERE key_id = ?",
                (key_id,),
            ).fetchone()
        if row is None:
            return None
        payload = json.loads(str(row[0]))
        payload["not_after"] = datetime.fromisoformat(payload["not_after"])
        return CommandBinding(**payload), int(str(row[1]))

    def readiness_bindings(
        self, *, product_id: str, environment: str, limit: int = 8,
    ) -> tuple[CommandBinding, ...]:
        """Bounded, read-only candidates from platform-owned configuration."""
        if not 1 <= limit <= 32:
            raise CommercialFulfillmentError("invalid Command readiness budget")
        with self._acquire() as connection:
            connection.execute("SET LOCAL statement_timeout = '2s'")
            rows = connection.execute(
                "SELECT binding_json FROM fm_command_bindings "
                "WHERE CAST(binding_json AS JSONB)->>'product_id' = ? "
                "AND CAST(binding_json AS JSONB)->>'environment' = ? "
                "AND CAST(binding_json AS JSONB)->>'enabled' = 'true' "
                "ORDER BY key_id LIMIT ?",
                (product_id, environment, limit + 1),
            ).fetchall()
        if len(rows) > limit:
            raise CommercialFulfillmentError("Command readiness budget exceeded")
        bindings = []
        for row in rows:
            payload = json.loads(str(row[0]))
            payload["not_after"] = datetime.fromisoformat(payload["not_after"])
            bindings.append(CommandBinding(**payload))
        return tuple(bindings)

    def configure(
        self,
        *,
        actor: AdminPrincipal,
        binding: CommandBinding,
        expected_revision: int | None,
        now: datetime,
    ) -> int:
        if not isinstance(actor, AdminPrincipal) or not (
            actor.global_scope
            and actor.has_permission(ControlPlanePermission.COMMERCIAL_CONFIG_WRITE)
            and actor.has_permission(ControlPlanePermission.SECRET_REFERENCE_WRITE)
        ):
            raise CommercialFulfillmentError("platform commercial administration required")
        if now.tzinfo is None or now.utcoffset() is None:
            raise CommercialFulfillmentError("configuration time must be aware")
        payload = json.dumps(
            {**asdict(binding), "not_after": binding.not_after.isoformat()}, sort_keys=True
        )
        with self._acquire() as connection:
            connection.execute("SET LOCAL lock_timeout = '5s'")
            connection.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(?, 0))",
                (f"command-binding:{binding.key_id}",),
            )
            row = connection.execute(
                "SELECT binding_json, revision FROM fm_command_bindings WHERE key_id = ?",
                (binding.key_id,),
            ).fetchone()
            revision = None if row is None else int(str(row[1]))
            if revision != expected_revision:
                raise CommercialFulfillmentError("Command binding revision conflict")
            if row is not None:
                old = json.loads(str(row[0]))
                for field in ("binding_id", "product_id", "environment", "contract_version"):
                    if old[field] != asdict(binding)[field]:
                        raise CommercialFulfillmentError("Command key scope is immutable")
            next_revision = (revision or 0) + 1
            connection.execute(
                "INSERT INTO fm_command_bindings (key_id, binding_json, revision) VALUES (?, ?, ?) "
                "ON CONFLICT (key_id) DO UPDATE SET binding_json=excluded.binding_json, "
                "revision=excluded.revision",
                (binding.key_id, payload, next_revision),
            )
            connection.execute(
                "INSERT INTO fm_command_binding_audit "
                "(key_id, revision, actor_id, binding_json, changed_at) VALUES (?, ?, ?, ?, ?)",
                (binding.key_id, next_revision, actor.actor_id, payload, now.isoformat()),
            )
            connection.commit()
        return next_revision

    @contextmanager
    def guard(self, event: CommandCommercialEvent) -> Iterator[None]:
        # Hold transaction locks across the existing canonical UOWs. Independent
        # instances/restarts share these locks; no process-local deduplication.
        identities = (
            f"event:{event.event_id}",
            f"subscription:{event.command_subscription_id}",
            f"acquisition:{event.acquisition_id}",
        )
        with self._acquire() as connection:
            try:
                connection.execute("SET LOCAL lock_timeout = '5s'")
                for identity in sorted(identities):
                    connection.execute(
                        "SELECT pg_advisory_xact_lock(hashtextextended(?, 0))",
                        (f"command:{event.product_id}:{event.environment}:{identity}",),
                    )
                yield
            finally:
                connection.rollback()

    def correlation(self, event: CommandCommercialEvent) -> tuple[str, ...] | None:
        with self._acquire() as connection:
            row = connection.execute(
                "SELECT command_customer_id, acquisition_id, opening_invoice_id, purchase_id "
                "FROM fm_command_commercial_correlations WHERE product_id=? AND environment=? "
                "AND command_subscription_id=?",
                (event.product_id, event.environment, event.command_subscription_id),
            ).fetchone()
        return None if row is None else tuple(str(value) for value in row)

    def reserve(
        self,
        *,
        event: CommandCommercialEvent,
        binding_id: str,
        purchase_id: str,
        opening: bool,
        now: datetime,
    ) -> tuple[bool, datetime, bool]:
        """Return processed, original receipt time and durable replay identity."""
        with self._acquire() as connection:
            row = connection.execute(
                "SELECT fingerprint, binding_id, processed_at, received_at "
                "FROM fm_command_commercial_inbox "
                "WHERE product_id=? AND environment=? AND event_id=?",
                (event.product_id, event.environment, event.event_id),
            ).fetchone()
            if row is not None:
                if row[0] != event.fingerprint or row[1] != binding_id:
                    raise CommercialFulfillmentError("Command event identity conflict")
                return row[2] is not None, datetime.fromisoformat(str(row[3])), True
            if opening:
                try:
                    connection.execute(
                        "INSERT INTO fm_command_commercial_correlations "
                        "(product_id, environment, command_subscription_id, command_customer_id, "
                        "acquisition_id, opening_invoice_id, purchase_id) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (
                            event.product_id,
                            event.environment,
                            event.command_subscription_id,
                            event.command_customer_id,
                            event.acquisition_id,
                            event.command_invoice_id,
                            purchase_id,
                        ),
                    )
                except sqlite3.IntegrityError as exc:
                    raise CommercialFulfillmentError(
                        "Command correlation identity conflict"
                    ) from exc
            connection.execute(
                "INSERT INTO fm_command_commercial_inbox "
                "(product_id, environment, event_id, binding_id, fingerprint, purchase_id, "
                "received_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    event.product_id,
                    event.environment,
                    event.event_id,
                    binding_id,
                    event.fingerprint,
                    purchase_id,
                    now.isoformat(),
                ),
            )
            connection.commit()
            return False, now, False

    def processed(self, event: CommandCommercialEvent, now: datetime) -> None:
        with self._acquire() as connection:
            connection.execute(
                "UPDATE fm_command_commercial_inbox SET processed_at=? "
                "WHERE product_id=? AND environment=? AND event_id=? AND fingerprint=?",
                (
                    now.isoformat(),
                    event.product_id,
                    event.environment,
                    event.event_id,
                    event.fingerprint,
                ),
            )
            connection.commit()
