"""Governed platform administration for the NFCORE commercial release state.

The service owns only release-state publication. Pricing, checkout/billing and fiscal
production authority remain independent. Approval is explicit, human-controlled,
versioned and auditable.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from kordena_fiscal.domain import FiscalValidationError
from kordena_fiscal.product.commercial_release import (
    CommercialReleaseDecision,
    CommercialReleaseError,
)

from .models import AdminPrincipal, ControlPlanePermission
from .service import ControlPlaneAuthorizationError


@dataclass(frozen=True, slots=True)
class CommercialReleasePublication:
    decision: CommercialReleaseDecision
    actor_id: str
    correlation_id: str
    published_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.decision, CommercialReleaseDecision):
            raise FiscalValidationError("decision must be CommercialReleaseDecision")
        if not self.actor_id.strip():
            raise FiscalValidationError("actor_id must not be blank")
        if not self.correlation_id.strip():
            raise FiscalValidationError("correlation_id must not be blank")
        if self.published_at.tzinfo is None or self.published_at.utcoffset() is None:
            raise FiscalValidationError("published_at must be timezone-aware")


class CommercialReleaseCatalog(Protocol):
    @property
    def current(self) -> CommercialReleaseDecision | None: ...

    def history(self) -> tuple[CommercialReleasePublication, ...]: ...

    def publish(
        self,
        decision: CommercialReleaseDecision,
        *,
        expected_version: int | None,
        actor_id: str,
        correlation_id: str,
        published_at: datetime,
    ) -> CommercialReleasePublication: ...


class InMemoryCommercialReleaseCatalog:
    """Test/runtime compatibility implementation preserving the same version contract."""

    def __init__(self) -> None:
        self._history: list[CommercialReleasePublication] = []

    @property
    def current(self) -> CommercialReleaseDecision | None:
        if not self._history:
            return None
        return self._history[-1].decision

    def history(self) -> tuple[CommercialReleasePublication, ...]:
        return tuple(reversed(self._history))

    def publish(
        self,
        decision: CommercialReleaseDecision,
        *,
        expected_version: int | None,
        actor_id: str,
        correlation_id: str,
        published_at: datetime,
    ) -> CommercialReleasePublication:
        current = self.current
        if current is None:
            if expected_version is not None or decision.version != 1:
                raise CommercialReleaseError(
                    "first commercial release decision must be version 1"
                )
        else:
            if expected_version != current.version:
                raise CommercialReleaseError("commercial release version conflict")
            if decision.version != current.version + 1:
                raise CommercialReleaseError(
                    "commercial release version must increment by one"
                )
        publication = CommercialReleasePublication(
            decision=decision,
            actor_id=actor_id,
            correlation_id=correlation_id,
            published_at=published_at,
        )
        self._history.append(publication)
        return publication


class CommercialReleaseAdministrationService:
    """Publish release decisions only from explicit global FM platform authority."""

    def __init__(self, catalog: CommercialReleaseCatalog) -> None:
        self._catalog = catalog

    @property
    def current(self) -> CommercialReleaseDecision | None:
        return self._catalog.current

    def history(self) -> tuple[CommercialReleasePublication, ...]:
        return self._catalog.history()

    def publish(
        self,
        *,
        actor: AdminPrincipal,
        decision: CommercialReleaseDecision,
        expected_version: int | None,
        correlation_id: str = "commercial-release-admin",
        published_at: datetime | None = None,
    ) -> CommercialReleaseDecision:
        self._require_platform_admin(actor)
        if not isinstance(decision, CommercialReleaseDecision):
            raise FiscalValidationError("decision must be CommercialReleaseDecision")
        correlation = correlation_id.strip()
        if not correlation:
            raise FiscalValidationError("correlation_id must not be blank")
        publication = self._catalog.publish(
            decision,
            expected_version=expected_version,
            actor_id=actor.actor_id,
            correlation_id=correlation,
            published_at=published_at or datetime.now(UTC),
        )
        return publication.decision

    @staticmethod
    def _require_platform_admin(actor: AdminPrincipal) -> None:
        if not isinstance(actor, AdminPrincipal):
            raise FiscalValidationError("actor must be AdminPrincipal")
        permission = ControlPlanePermission.COMMERCIAL_CONFIG_WRITE
        if not actor.has_permission(permission):
            raise ControlPlaneAuthorizationError(
                f"actor lacks required permission: {permission.value}"
            )
        if not actor.global_scope:
            raise ControlPlaneAuthorizationError(
                "commercial release publication requires global FM platform authority"
            )


__all__ = [
    "CommercialReleaseAdministrationService",
    "CommercialReleaseCatalog",
    "CommercialReleasePublication",
    "InMemoryCommercialReleaseCatalog",
]
