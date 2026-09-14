import pytest

from kordena_fiscal.product.onboarding import (
    ONBOARDING_SEQUENCE,
    OnboardingEvidence,
    OnboardingStep,
    SelfServiceOnboarding,
    SelfServiceOnboardingError,
)


def fill(onboarding: SelfServiceOnboarding) -> None:
    for index, step in enumerate(ONBOARDING_SEQUENCE):
        onboarding.record(OnboardingEvidence(step, f"ref://demo/{index}/{step.value}"))


def test_homologation_onboarding_completes_without_production_readiness() -> None:
    onboarding = SelfServiceOnboarding("demo-1", environment="HOMOLOGATION")
    fill(onboarding)
    onboarding.complete()
    assert onboarding.completed is True
    assert onboarding.progress_percent == 100


def test_production_onboarding_requires_explicit_readiness() -> None:
    onboarding = SelfServiceOnboarding("demo-2", environment="PRODUCTION")
    fill(onboarding)
    with pytest.raises(SelfServiceOnboardingError, match="explicit production readiness"):
        onboarding.complete()
    onboarding.set_production_readiness(approved=True)
    onboarding.complete()
    assert onboarding.completed is True


def test_homologation_cannot_receive_production_readiness() -> None:
    onboarding = SelfServiceOnboarding("demo-3", environment="HOMOLOGATION")
    fill(onboarding)
    with pytest.raises(SelfServiceOnboardingError, match="homologation"):
        onboarding.set_production_readiness(approved=True)


def test_onboarding_is_strictly_ordered() -> None:
    onboarding = SelfServiceOnboarding("demo-4", environment="HOMOLOGATION")
    with pytest.raises(SelfServiceOnboardingError, match="out-of-order"):
        onboarding.record(OnboardingEvidence(OnboardingStep.UNIT, "ref://unit/demo"))


def test_retrying_same_step_is_idempotent_but_conflict_fails() -> None:
    onboarding = SelfServiceOnboarding("demo-5", environment="HOMOLOGATION")
    evidence = OnboardingEvidence(OnboardingStep.ORGANIZATION, "ref://org/demo")
    onboarding.record(evidence)
    onboarding.record(evidence)
    with pytest.raises(SelfServiceOnboardingError, match="conflicts"):
        onboarding.record(
            OnboardingEvidence(OnboardingStep.ORGANIZATION, "ref://org/other")
        )


def test_checkpoint_restore_resumes_at_exact_next_step() -> None:
    onboarding = SelfServiceOnboarding("demo-6", environment="HOMOLOGATION")
    first_steps = ONBOARDING_SEQUENCE[:5]
    for index, step in enumerate(first_steps):
        onboarding.record(OnboardingEvidence(step, f"ref://checkpoint/{index}"))

    restored = SelfServiceOnboarding.restore(onboarding.checkpoint())
    assert restored.next_step is ONBOARDING_SEQUENCE[5]
    assert restored.progress_percent == len(first_steps) * 100 // len(ONBOARDING_SEQUENCE)


def test_completed_onboarding_is_immutable() -> None:
    onboarding = SelfServiceOnboarding("demo-7", environment="HOMOLOGATION")
    fill(onboarding)
    onboarding.complete()
    with pytest.raises(SelfServiceOnboardingError, match="immutable"):
        onboarding.record(
            OnboardingEvidence(OnboardingStep.ORGANIZATION, "ref://org/rewrite")
        )


def test_reference_id_rejects_secret_like_freeform_whitespace() -> None:
    with pytest.raises(SelfServiceOnboardingError, match="unsafe characters"):
        OnboardingEvidence(
            OnboardingStep.CERTIFICATE_REFERENCE,
            "raw password should not be here",
        )


def test_readiness_cannot_finalize_before_checklist() -> None:
    onboarding = SelfServiceOnboarding("demo-8", environment="PRODUCTION")
    with pytest.raises(SelfServiceOnboardingError, match="checklist"):
        onboarding.set_production_readiness(approved=True)


def test_environment_is_fail_closed() -> None:
    with pytest.raises(SelfServiceOnboardingError, match="HOMOLOGATION or PRODUCTION"):
        SelfServiceOnboarding("demo-9", environment="staging")
