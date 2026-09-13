"""Pre-cutover convergence contracts for FM Fiscal Core V2.

These types describe readiness and authority ownership. They do not execute a
cutover, promote production readiness, mutate providers, or archive the legacy
engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ConvergenceValidationError(ValueError):
    """Raised when a convergence plan is incomplete or unsafe."""


class CutoverNotReadyError(ConvergenceValidationError):
    """Raised when a cutover is requested without every mandatory prerequisite."""


class CutoverReadinessStatus(StrEnum):
    READY_INTERNAL = "ready_internal"
    BLOCKED_PRODUCT = "blocked_product"
    BLOCKED_EXTERNAL = "blocked_external"
    HUMAN_APPROVAL_REQUIRED = "human_approval_required"


@dataclass(frozen=True, slots=True)
class CutoverRequirement:
    requirement_id: str
    status: CutoverReadinessStatus
    evidence: str
    mandatory: bool = True

    def __post_init__(self) -> None:
        if not self.requirement_id.strip():
            raise ConvergenceValidationError("requirement_id must not be blank")
        if not self.evidence.strip():
            raise ConvergenceValidationError("evidence must not be blank")
        if not isinstance(self.status, CutoverReadinessStatus):
            raise ConvergenceValidationError("status must be CutoverReadinessStatus")


@dataclass(frozen=True, slots=True)
class CutoverReadinessMatrix:
    requirements: tuple[CutoverRequirement, ...]

    def __post_init__(self) -> None:
        if not self.requirements:
            raise ConvergenceValidationError("cutover readiness matrix must not be empty")
        ids = tuple(item.requirement_id for item in self.requirements)
        if len(ids) != len(set(ids)):
            raise ConvergenceValidationError("cutover readiness requirement ids must be unique")

    @property
    def blocking_requirements(self) -> tuple[CutoverRequirement, ...]:
        return tuple(
            item
            for item in self.requirements
            if item.mandatory and item.status is not CutoverReadinessStatus.READY_INTERNAL
        )

    @property
    def cutover_allowed(self) -> bool:
        return not self.blocking_requirements

    def require_cutover_ready(self) -> None:
        if self.cutover_allowed:
            return
        blocked = ", ".join(item.requirement_id for item in self.blocking_requirements)
        raise CutoverNotReadyError(f"cutover prerequisites are not satisfied: {blocked}")


class FiscalAuthorityDomain(StrEnum):
    SEQUENCE = "sequence"
    IDEMPOTENCY = "idempotency"
    DOCUMENT_LIFECYCLE = "document_lifecycle"
    ARCHIVE = "archive"
    RECONCILIATION = "reconciliation"
    PROVIDER_STATE = "provider_state"
    FISCAL_BINDING = "fiscal_binding"
    CAPABILITY = "capability"
    READINESS = "readiness"
    AUDIT = "audit"
    EVENTS = "events"


class LegacyAuthorityMode(StrEnum):
    READ_ONLY = "read_only"
    DISABLED = "disabled"
    READ_WRITE = "read_write"


@dataclass(frozen=True, slots=True)
class AuthorityAssignment:
    domain: FiscalAuthorityDomain
    current_authority: str
    future_authority: str
    legacy_mode_after_cutover: LegacyAuthorityMode

    def __post_init__(self) -> None:
        if not isinstance(self.domain, FiscalAuthorityDomain):
            raise ConvergenceValidationError("domain must be FiscalAuthorityDomain")
        if not self.current_authority.strip():
            raise ConvergenceValidationError("current_authority must not be blank")
        if not self.future_authority.strip():
            raise ConvergenceValidationError("future_authority must not be blank")
        if not isinstance(self.legacy_mode_after_cutover, LegacyAuthorityMode):
            raise ConvergenceValidationError(
                "legacy_mode_after_cutover must be LegacyAuthorityMode"
            )


@dataclass(frozen=True, slots=True)
class SingleFiscalAuthorityPlan:
    future_authority: str
    assignments: tuple[AuthorityAssignment, ...]

    def __post_init__(self) -> None:
        authority = self.future_authority.strip()
        if not authority:
            raise ConvergenceValidationError("future_authority must not be blank")
        if not self.assignments:
            raise ConvergenceValidationError("authority plan must not be empty")

        domains = tuple(item.domain for item in self.assignments)
        if len(domains) != len(set(domains)):
            raise ConvergenceValidationError("each fiscal authority domain must be unique")
        if set(domains) != set(FiscalAuthorityDomain):
            raise ConvergenceValidationError("authority plan must cover every fiscal domain")

        for assignment in self.assignments:
            if assignment.future_authority != authority:
                raise ConvergenceValidationError(
                    "every fiscal domain must converge to the same future authority"
                )
            if (
                assignment.current_authority != authority
                and assignment.legacy_mode_after_cutover is LegacyAuthorityMode.READ_WRITE
            ):
                raise ConvergenceValidationError(
                    "legacy authority cannot remain read-write after cutover"
                )

        object.__setattr__(self, "future_authority", authority)

    @property
    def has_future_dual_writer(self) -> bool:
        return any(
            item.current_authority != self.future_authority
            and item.legacy_mode_after_cutover is LegacyAuthorityMode.READ_WRITE
            for item in self.assignments
        )
