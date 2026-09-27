"""Governed commercial release state for FM NFCORE.

Pricing, checkout/billing and fiscal production authority remain separate concerns.
This model represents only the explicit human-controlled public commercial release
state. It never infers approval from CI, pricing, Cakto, staging or fiscal readiness.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class CommercialReleaseError(ValueError):
    """Raised when commercial release configuration is invalid."""


class CommercialReleaseStatus(StrEnum):
    UNAVAILABLE = "unavailable"
    INTERNAL_ONLY = "internal_only"
    WAITLIST = "waitlist"
    READY_FOR_CHECKOUT_CONFIGURATION = "ready_for_checkout_configuration"
    READY_FOR_COMMERCIAL_REVIEW = "ready_for_commercial_review"
    COMMERCIAL_APPROVED = "commercial_approved"


def _text(
    value: str | None,
    field_name: str,
    *,
    required: bool,
    max_length: int,
) -> str | None:
    if value is None:
        if required:
            raise CommercialReleaseError(f"{field_name} is required")
        return None
    normalized = value.strip()
    if not normalized:
        if required:
            raise CommercialReleaseError(f"{field_name} is required")
        return None
    if len(normalized) > max_length:
        raise CommercialReleaseError(
            f"{field_name} must be <= {max_length} characters"
        )
    return normalized


@dataclass(frozen=True, slots=True)
class CommercialReleaseDecision:
    """One immutable versioned human-controlled commercial release decision."""

    version: int
    status: CommercialReleaseStatus
    public_message: str | None = None
    human_decision_reference: str | None = None

    def __post_init__(self) -> None:
        if (
            not isinstance(self.version, int)
            or isinstance(self.version, bool)
            or self.version < 1
        ):
            raise CommercialReleaseError("version must be integer >= 1")
        if not isinstance(self.status, CommercialReleaseStatus):
            raise CommercialReleaseError("status must be CommercialReleaseStatus")
        object.__setattr__(
            self,
            "public_message",
            _text(
                self.public_message,
                "public_message",
                required=False,
                max_length=320,
            ),
        )
        object.__setattr__(
            self,
            "human_decision_reference",
            _text(
                self.human_decision_reference,
                "human_decision_reference",
                required=self.status is CommercialReleaseStatus.COMMERCIAL_APPROVED,
                max_length=256,
            ),
        )

    @property
    def commercially_approved(self) -> bool:
        return self.status is CommercialReleaseStatus.COMMERCIAL_APPROVED

    def to_mapping(self) -> dict[str, object]:
        return {
            "version": self.version,
            "status": self.status.value,
            "public_message": self.public_message,
            "human_decision_reference": self.human_decision_reference,
        }

    @classmethod
    def from_mapping(cls, payload: object) -> "CommercialReleaseDecision":
        if not isinstance(payload, dict):
            raise CommercialReleaseError("commercial release payload must be an object")
        version = payload.get("version")
        status = payload.get("status")
        if not isinstance(status, str):
            raise CommercialReleaseError("status must be string")
        if not isinstance(version, int) or isinstance(version, bool):
            raise CommercialReleaseError("version must be integer")
        public_message = payload.get("public_message")
        if public_message is not None and not isinstance(public_message, str):
            raise CommercialReleaseError("public_message must be string or null")
        decision_reference = payload.get("human_decision_reference")
        if decision_reference is not None and not isinstance(decision_reference, str):
            raise CommercialReleaseError(
                "human_decision_reference must be string or null"
            )
        try:
            release_status = CommercialReleaseStatus(status)
        except ValueError as exc:
            raise CommercialReleaseError("unsupported commercial release status") from exc
        return cls(
            version=version,
            status=release_status,
            public_message=public_message,
            human_decision_reference=decision_reference,
        )
