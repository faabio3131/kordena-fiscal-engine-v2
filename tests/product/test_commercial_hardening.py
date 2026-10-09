from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from fm_fiscal_sdk import (
    BridgeClient,
    BridgeRequest,
    BridgeResponse,
    RetryableTransportError,
    RetryPolicy,
    verify_webhook_signature,
)
from kordena_fiscal.product.billing import (
    CommercialPlan,
    CommercialSubscription,
    SubscriptionStatus,
    UsageQuota,
)
from kordena_fiscal.product.onboarding import (
    ONBOARDING_SEQUENCE,
    OnboardingEvidence,
    SelfServiceOnboarding,
)
from kordena_fiscal.product.operations import IncidentCategory, OperationsCatalog

ROOT = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 9, 13, tzinfo=UTC)


class FlakyTransport:
    def __init__(self, failures: int) -> None:
        self.failures = failures
        self.calls = 0
        self.requests: list[BridgeRequest] = []

    def send(self, request: BridgeRequest) -> BridgeResponse:
        self.calls += 1
        self.requests.append(request)
        if self.calls <= self.failures:
            raise RetryableTransportError("synthetic transport timeout")
        return BridgeResponse(200, b'{"status":"ok"}')


def _client(transport: FlakyTransport, *, max_attempts: int = 3) -> BridgeClient:
    return BridgeClient(
        transport=transport,
        workload_credential_id="workload-ref-hardening",
        bearer_secret="synthetic-hardening-secret",
        host_namespace="fm-commercial-hardening",
        tenant_id="tenant-hardening",
        unit_id="unit-hardening",
        environment="HOMOLOGATION",
        retry_policy=RetryPolicy(max_attempts=max_attempts),
    )


def _subscription() -> CommercialSubscription:
    plan = CommercialPlan(
        "hardening-plan",
        ("documents.issue", "documents.query"),
        (UsageQuota("documents.issue", 10),),
    )
    return CommercialSubscription(
        tenant_id="tenant-hardening",
        plan=plan,
        status=SubscriptionStatus.ACTIVE,
        period_start=NOW,
        period_end=NOW + timedelta(days=30),
    )


def test_sdk_retry_is_bounded_and_preserves_request_identity() -> None:
    transport = FlakyTransport(failures=2)
    response = _client(transport).issue(
        b'{"synthetic":true}',
        correlation_id="corr-hardening",
        idempotency_key="idem-hardening",
    )

    assert response.status_code == 200
    assert transport.calls == 3
    assert {request.headers["Idempotency-Key"] for request in transport.requests} == {
        "idem-hardening"
    }
    assert {request.headers["X-Correlation-Id"] for request in transport.requests} == {
        "corr-hardening"
    }


def test_sdk_retry_budget_fails_closed_when_transport_never_recovers() -> None:
    transport = FlakyTransport(failures=10)
    with pytest.raises(RetryableTransportError, match="timeout"):
        _client(transport, max_attempts=2).query(b"{}", correlation_id="corr-fail")
    assert transport.calls == 2


def test_webhook_verification_rejects_wrong_signature() -> None:
    payload = b'{"event":"synthetic"}'
    assert not verify_webhook_signature(
        payload,
        signature_hex="00" * 32,
        key=b"synthetic-hardening-webhook-key",
    )


def test_commercial_state_restores_without_usage_or_status_regression() -> None:
    subscription = _subscription()
    subscription.record_usage("documents.issue", amount=4, at=NOW)
    subscription.transition(SubscriptionStatus.GRACE)

    restored = CommercialSubscription.restore(subscription.checkpoint())

    assert restored.status is SubscriptionStatus.GRACE
    assert restored.usage("documents.issue") == 4
    assert restored.preserves_existing_fiscal_state is True


def test_onboarding_checkpoint_restart_is_deterministic() -> None:
    onboarding = SelfServiceOnboarding("restart-hardening", environment="HOMOLOGATION")
    for index, step in enumerate(ONBOARDING_SEQUENCE[:7], start=1):
        onboarding.record(OnboardingEvidence(step, f"restart-ref-{index}"))

    restored = SelfServiceOnboarding.restore(onboarding.checkpoint())

    assert restored.evidence == onboarding.evidence
    assert restored.next_step is ONBOARDING_SEQUENCE[7]
    assert restored.progress_percent == onboarding.progress_percent


def test_critical_operational_runbooks_remain_escalating_and_fail_safe() -> None:
    catalog = OperationsCatalog()
    for category in (
        IncidentCategory.UNKNOWN_OUTCOME,
        IncidentCategory.SEQUENCE_GAP,
        IncidentCategory.SECURITY,
        IncidentCategory.DISASTER_RECOVERY,
    ):
        assert catalog.runbook(category).escalation_required is True
    unknown = catalog.runbook(IncidentCategory.UNKNOWN_OUTCOME)
    assert "do not blind retry" in unknown.first_actions


def test_commercial_surfaces_contain_no_private_key_files_or_material() -> None:
    roots = [
        ROOT / "src" / "kordena_fiscal" / "product",
        ROOT / "src" / "fm_fiscal_sdk",
        ROOT / "portal",
    ]
    secret_files = [
        path
        for root in roots
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in {".pfx", ".p12", ".pem", ".key"}
    ]
    assert secret_files == []

    text = "\n".join(
        path.read_text(encoding="utf-8")
        for root in roots
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in {".py", ".js", ".html", ".css"}
    )
    assert "BEGIN " + "PRIVATE KEY" not in text
    assert "PRODUCTION_APPROVED" not in text


def test_runtime_dependencies_remain_small_and_bounded() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert '"cryptography>=50,<51"' in pyproject
    assert '"lxml>=5.3,<7"' in pyproject
    project_section = pyproject.split("[project.optional-dependencies]", maxsplit=1)[0]
    assert "requests" not in project_section
    assert "boto3" not in project_section
