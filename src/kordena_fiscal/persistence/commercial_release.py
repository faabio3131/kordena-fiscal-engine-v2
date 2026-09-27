"""Durable PostgreSQL persistence for commercial release decisions."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, cast

from kordena_fiscal.control_plane.commercial_release import (
    CommercialReleasePublication,
)
from kordena_fiscal.product.commercial_release import (
    CommercialReleaseDecision,
    CommercialReleaseError,
    CommercialReleaseStatus,
)

if TYPE_CHECKING:
    from kordena_fiscal.persistence.postgres import PostgresFiscalDatabase


class PostgresCommercialReleaseRepository:
    """Append-only release decision repository with optimistic versioning."""

    _LOCK_MATERIAL = "nfcore:commercial-release-catalog"

    def __init__(self, database: PostgresFiscalDatabase) -> None:
        self._database = database

    @staticmethod
    def _publication(row: tuple[object, ...]) -> CommercialReleasePublication:
        decision = CommercialReleaseDecision(
            version=int(cast(int, row[0])),
            status=CommercialReleaseStatus(str(row[1])),
            public_message=None if row[2] is None else str(row[2]),
            human_decision_reference=None if row[3] is None else str(row[3]),
        )
        return CommercialReleasePublication(
            decision=decision,
            actor_id=str(row[4]),
            correlation_id=str(row[5]),
            published_at=datetime.fromisoformat(str(row[6])),
        )

    @property
    def current(self) -> CommercialReleaseDecision | None:
        with self._database.connection() as connection:
            row = connection.execute(
                """
                SELECT version, status, public_message, human_decision_reference,
                       actor_id, correlation_id, published_at
                FROM fm_commercial_release_versions
                ORDER BY version DESC
                LIMIT 1
                """
            ).fetchone()
        return None if row is None else self._publication(row).decision

    def history(self) -> tuple[CommercialReleasePublication, ...]:
        with self._database.connection() as connection:
            rows = connection.execute(
                """
                SELECT version, status, public_message, human_decision_reference,
                       actor_id, correlation_id, published_at
                FROM fm_commercial_release_versions
                ORDER BY version DESC
                """
            ).fetchall()
        return tuple(self._publication(row) for row in rows)

    def publish(
        self,
        decision: CommercialReleaseDecision,
        *,
        expected_version: int | None,
        actor_id: str,
        correlation_id: str,
        published_at: datetime,
    ) -> CommercialReleasePublication:
        if not isinstance(decision, CommercialReleaseDecision):
            raise CommercialReleaseError(
                "decision must be CommercialReleaseDecision"
            )
        if published_at.tzinfo is None or published_at.utcoffset() is None:
            raise CommercialReleaseError("published_at must be timezone-aware")

        with self._database.connection() as connection:
            try:
                connection.execute(
                    "SELECT pg_advisory_xact_lock(hashtextextended(?, 0))",
                    (self._LOCK_MATERIAL,),
                )
                row = connection.execute(
                    """
                    SELECT version
                    FROM fm_commercial_release_versions
                    ORDER BY version DESC
                    LIMIT 1
                    """
                ).fetchone()
                current_version = None if row is None else int(cast(int, row[0]))
                if current_version is None:
                    if expected_version is not None or decision.version != 1:
                        raise CommercialReleaseError(
                            "first commercial release decision must be version 1"
                        )
                else:
                    if expected_version != current_version:
                        raise CommercialReleaseError(
                            "commercial release version conflict"
                        )
                    if decision.version != current_version + 1:
                        raise CommercialReleaseError(
                            "commercial release version must increment by one"
                        )

                connection.execute(
                    """
                    INSERT INTO fm_commercial_release_versions (
                        version, status, public_message, human_decision_reference,
                        actor_id, correlation_id, published_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        decision.version,
                        decision.status.value,
                        decision.public_message,
                        decision.human_decision_reference,
                        actor_id,
                        correlation_id,
                        published_at.isoformat(),
                    ),
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise

        return CommercialReleasePublication(
            decision=decision,
            actor_id=actor_id,
            correlation_id=correlation_id,
            published_at=published_at,
        )
