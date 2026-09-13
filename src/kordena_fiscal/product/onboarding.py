"""Resumable, reference-only self-service onboarding for FM Fiscal."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class SelfServiceOnboardingError(ValueError):
    """Raised when commercial onboarding violates a governance invariant."""


class OnboardingStep(StrEnum):
    ORGANIZATION = "organization"
    COMPANY = "company"
    TENANT = "tenant"
    UNIT = "unit"
    USERS_ROLES = "users_roles"
    ENVIRONMENT = "environment"
    FISCAL_PROFILE = "fiscal_profile"
    DOCUMENT_CAPABILITIES = "document_capabilities"
    CERTIFICATE_REFERENCE = "certificate_reference"
    CSC_REFERENCE = "csc_reference"
    PROVIDER_BINDING = "provider_binding"
    WEBHOOK_CONFIGURATION = "webhook_configuration"
    WORKLOAD_PROVISIONING = "workload_provisioning"
    READINESS_CHECKLIST = "readiness_checklist"


ONBOARDING_SEQUENCE: tuple[OnboardingStep, ...] = tuple(OnboardingStep)


@dataclass(frozen=True, slots=True)
class OnboardingEvidence:
    step: OnboardingStep
    reference_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.step, OnboardingStep):
            raise SelfServiceOnboardingError("step must be OnboardingStep")
        normalized = self.reference_id.strip()
        if not normalized or len(normalized) > 160:
            raise SelfServiceOnboardingError("reference_id must be non-blank and <= 160 chars")
        allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._:/-")
        if any(character not in allowed for character in normalized):
            raise SelfServiceOnboardingError("reference_id contains unsafe characters")
        object.__setattr__(self, "reference_id", normalized)


@dataclass(frozen=True, slots=True)
class SelfServiceOnboardingCheckpoint:
    onboarding_id: str
    environment: str
    evidence: tuple[OnboardingEvidence, ...]
    production_readiness: bool
    completed: bool


class SelfServiceOnboarding:
    """Ordered onboarding state that stores references, never secret material."""

    def __init__(self, onboarding_id: str, *, environment: str) -> None:
        normalized_id = onboarding_id.strip().lower()
        normalized_environment = environment.strip().upper()
        if not normalized_id:
            raise SelfServiceOnboardingError("onboarding_id must not be blank")
        if normalized_environment not in {"HOMOLOGATION", "PRODUCTION"}:
            raise SelfServiceOnboardingError("environment must be HOMOLOGATION or PRODUCTION")
        self.onboarding_id = normalized_id
        self.environment = normalized_environment
        self._evidence: dict[OnboardingStep, OnboardingEvidence] = {}
        self.production_readiness = False
        self.completed = False

    @property
    def evidence(self) -> tuple[OnboardingEvidence, ...]:
        return tuple(self._evidence[step] for step in ONBOARDING_SEQUENCE if step in self._evidence)

    @property
    def next_step(self) -> OnboardingStep | None:
        for step in ONBOARDING_SEQUENCE:
            if step not in self._evidence:
                return step
        return None

    @property
    def progress_percent(self) -> int:
        return len(self._evidence) * 100 // len(ONBOARDING_SEQUENCE)

    def record(self, evidence: OnboardingEvidence) -> None:
        if self.completed:
            raise SelfServiceOnboardingError("completed onboarding is immutable")
        expected = self.next_step
        existing = self._evidence.get(evidence.step)
        if existing is not None:
            if existing != evidence:
                raise SelfServiceOnboardingError("onboarding step conflicts with existing evidence")
            return
        if expected is not evidence.step:
            expected_value = "none" if expected is None else expected.value
            raise SelfServiceOnboardingError(
                f"out-of-order onboarding step; expected {expected_value}"
            )
        self._evidence[evidence.step] = evidence

    def set_production_readiness(self, *, approved: bool) -> None:
        if self.environment != "PRODUCTION" and approved:
            raise SelfServiceOnboardingError(
                "production readiness cannot be assigned to homologation onboarding"
            )
        if self.next_step is not None:
            raise SelfServiceOnboardingError(
                "readiness cannot be finalized before onboarding checklist is complete"
            )
        self.production_readiness = approved

    def complete(self) -> None:
        if self.next_step is not None:
            raise SelfServiceOnboardingError("onboarding checklist is incomplete")
        if self.environment == "PRODUCTION" and not self.production_readiness:
            raise SelfServiceOnboardingError(
                "production onboarding requires explicit production readiness"
            )
        self.completed = True

    def checkpoint(self) -> SelfServiceOnboardingCheckpoint:
        return SelfServiceOnboardingCheckpoint(
            onboarding_id=self.onboarding_id,
            environment=self.environment,
            evidence=self.evidence,
            production_readiness=self.production_readiness,
            completed=self.completed,
        )

    @classmethod
    def restore(cls, checkpoint: SelfServiceOnboardingCheckpoint) -> SelfServiceOnboarding:
        onboarding = cls(checkpoint.onboarding_id, environment=checkpoint.environment)
        for evidence in checkpoint.evidence:
            onboarding.record(evidence)
        onboarding.production_readiness = checkpoint.production_readiness
        onboarding.completed = checkpoint.completed
        return onboarding
