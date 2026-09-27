"""Durable PostgreSQL persistence for the commercial pricing catalog.

The catalog is platform configuration, not fiscal authority. Every publication keeps
an immutable payload plus actor/correlation/timestamp audit metadata and uses
optimistic version checks under a PostgreSQL advisory lock.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import TYPE_CHECKING, cast

from kordena_fiscal.control_plane.pricing_admin import PricingCatalogPublication
from kordena_fiscal.product.pricing import (
    CommercialPricingConfiguration,
    CommercialPricingError,
)

if TYPE_CHECKING:
    from kordena_fiscal.persistence.postgres import PostgresFiscalDatabase


def pricing_configuration_payload(
    configuration: CommercialPricingConfiguration,
) -> dict[str, object]:
    """Serialize a pricing configuration using the canonical product mapping."""

    if not isinstance(configuration, CommercialPricingConfiguration):
        raise CommercialPricingError(
            "configuration must be CommercialPricingConfiguration"
        )
    return configuration.to_mapping()


class PostgresPricingCatalogRepository:
    """Append-only durable pricing publication repository."""

    _LOCK_MATERIAL = "nfcore:commercial-pricing-catalog"

    def __init__(self, database: PostgresFiscalDatabase) -> None:
        self._database = database

    @staticmethod
    def _publication(row: tuple[object, ...]) -> PricingCatalogPublication:
        try:
            decoded = json.loads(str(row[2]))
        except json.JSONDecodeError as exc:
            raise CommercialPricingError("persisted pricing payload is invalid JSON") from exc
        if not isinstance(decoded, dict):
            raise CommercialPricingError("persisted pricing payload must be an object")
        configuration = CommercialPricingConfiguration.from_mapping(
            cast(dict[str, object], decoded)
        )
        if configuration.version != int(cast(int, row[0])):
            raise CommercialPricingError("persisted pricing version does not match payload")
        if configuration.configuration_id != str(row[1]):
            raise CommercialPricingError(
                "persisted pricing configuration_id does not match payload"
            )
        published_at = datetime.fromisoformat(str(row[5]))
        return PricingCatalogPublication(
            configuration=configuration,
            actor_id=str(row[3]),
            correlation_id=str(row[4]),
            published_at=published_at,
        )

    @property
    def current(self) -> CommercialPricingConfiguration | None:
        with self._database.connection() as connection:
            row = connection.execute(
                """
                SELECT version, configuration_id, payload_json, actor_id,
                       correlation_id, published_at
                FROM fm_commercial_pricing_catalog_versions
                ORDER BY version DESC
                LIMIT 1
                """
            ).fetchone()
        return None if row is None else self._publication(row).configuration

    def history(self) -> tuple[PricingCatalogPublication, ...]:
        with self._database.connection() as connection:
            rows = connection.execute(
                """
                SELECT version, configuration_id, payload_json, actor_id,
                       correlation_id, published_at
                FROM fm_commercial_pricing_catalog_versions
                ORDER BY version DESC
                """
            ).fetchall()
        return tuple(self._publication(row) for row in rows)

    def publish(
        self,
        configuration: CommercialPricingConfiguration,
        *,
        expected_version: int | None,
        actor_id: str,
        correlation_id: str,
        published_at: datetime,
    ) -> PricingCatalogPublication:
        if not isinstance(configuration, CommercialPricingConfiguration):
            raise CommercialPricingError(
                "configuration must be CommercialPricingConfiguration"
            )
        if published_at.tzinfo is None or published_at.utcoffset() is None:
            raise CommercialPricingError("published_at must be timezone-aware")
        payload_json = json.dumps(
            pricing_configuration_payload(configuration),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )

        with self._database.connection() as connection:
            try:
                connection.execute(
                    "SELECT pg_advisory_xact_lock(hashtextextended(?, 0))",
                    (self._LOCK_MATERIAL,),
                )
                row = connection.execute(
                    """
                    SELECT version
                    FROM fm_commercial_pricing_catalog_versions
                    ORDER BY version DESC
                    LIMIT 1
                    """
                ).fetchone()
                current_version = None if row is None else int(cast(int, row[0]))
                if current_version is None:
                    if expected_version is not None or configuration.version != 1:
                        raise CommercialPricingError(
                            "first pricing configuration must be version 1"
                        )
                else:
                    if expected_version != current_version:
                        raise CommercialPricingError(
                            "pricing configuration version conflict"
                        )
                    if configuration.version != current_version + 1:
                        raise CommercialPricingError(
                            "pricing configuration version must increment by one"
                        )

                connection.execute(
                    """
                    INSERT INTO fm_commercial_pricing_catalog_versions (
                        version, configuration_id, payload_json, actor_id,
                        correlation_id, published_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        configuration.version,
                        configuration.configuration_id,
                        payload_json,
                        actor_id,
                        correlation_id,
                        published_at.isoformat(),
                    ),
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise

        return PricingCatalogPublication(
            configuration=configuration,
            actor_id=actor_id,
            correlation_id=correlation_id,
            published_at=published_at,
        )
