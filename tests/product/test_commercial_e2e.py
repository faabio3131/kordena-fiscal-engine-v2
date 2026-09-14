import hashlib
import hmac
from datetime import UTC, datetime, timedelta

import pytest

from fm_fiscal_sdk import BridgeClient, BridgeRequest, BridgeResponse, verify_webhook_signature
from kordena_fiscal.product.billing import (
    CommercialBillingError,
    CommercialPlan,
    CommercialSubscription,
    SubscriptionStatus,
    UsageQuota,
)
from kordena_fiscal.product.onboarding import (
    ONBOARDING_SEQUENCE,
    OnboardingEvidence,
    SelfServiceOnboarding,
    SelfServiceOnboardingError,
)


class RecordingTransport:
    def __init__(self) -> None:
        self.requests: list[BridgeRequest] = []

    def send(self, request: BridgeRequest) -> BridgeResponse:
        self.requests.append(request)
        if request.path == "/v1/capabilities/query":
            return BridgeResponse(200, b'{"status":"READY_INTERNAL"}')
        if request.path == "/v1/issuances":
            return BridgeResponse(202, b'{"issuance_id":"ISS-SYN-1"}')
        if request.path == "/v1/queries":
            return BridgeResponse(200, b'{"document_id":"DOC-SYN-1"}')
        if request.path == "/v1/reconciliations":
            return BridgeResponse(202, b'{"reconciliation_id":"REC-SYN-1"}')
        return BridgeResponse(404, b"{}")


def _complete_homologation_onboarding() -> SelfServiceOnboarding:
    onboarding = SelfServiceOnboarding("onb-syn-1", environment="HOMOLOGATION")
    for index, step in enumerate(ONBOARDING_SEQUENCE, start=1):
        onboarding.record(OnboardingEvidence(step, f"ref-syn-{index}"))
    onboarding.complete()
    return onboarding


def _subscription() -> CommercialSubscription:
    start = datetime(2026, 9, 13, tzinfo=UTC)
    plan = CommercialPlan(
        "growth-synthetic",
        (
            "documents.issue",
            "documents.query",
            "webhooks.delivery",
            "reconciliation",
            "archive.reference",
        ),
        (UsageQuota("documents.issue", 2),),
    )
    return CommercialSubscription(
        tenant_id="tenant-syn-a",
        plan=plan,
        status=SubscriptionStatus.TRIAL,
        period_start=start,
        period_end=start + timedelta(days=30),
    )


def _client(transport: RecordingTransport, *, tenant_id: str = "tenant-syn-a") -> BridgeClient:
    return BridgeClient(
        transport=transport,
        workload_credential_id="workload-ref-syn",
        bearer_secret="synthetic-not-a-real-secret",
        host_namespace="fm-test-product",
        tenant_id=tenant_id,
        unit_id="unit-syn-1",
        environment="HOMOLOGATION",
    )


def test_complete_synthetic_commercial_journey() -> None:
    onboarding = _complete_homologation_onboarding()
    assert onboarding.completed is True
    assert onboarding.progress_percent == 100

    subscription = _subscription()
    subscription.require_entitlement("documents.issue")
    subscription.require_entitlement("documents.query")
    subscription.require_entitlement("webhooks.delivery")

    transport = RecordingTransport()
    client = _client(transport)

    capability = client.capability_query(b'{"document_kind":"NFE"}', correlation_id="corr-syn-1")
    issuance = client.issue(
        b'{"operation":"authorize","synthetic":true}',
        correlation_id="corr-syn-2",
        idempotency_key="idem-syn-1",
        causation_id="cause-syn-1",
    )
    query = client.query(b'{"document_id":"DOC-SYN-1"}', correlation_id="corr-syn-3")
    reconciliation = client.reconcile(
        b'{"document_id":"DOC-SYN-1"}',
        correlation_id="corr-syn-4",
        idempotency_key="idem-rec-syn-1",
        causation_id="cause-syn-2",
    )

    status_codes = [
        capability.status_code,
        issuance.status_code,
        query.status_code,
        reconciliation.status_code,
    ]
    assert status_codes == [200, 202, 200, 202]
    assert subscription.record_usage("documents.issue") == 1
    assert transport.requests[1].headers["Idempotency-Key"] == "idem-syn-1"
    assert transport.requests[1].headers["X-Correlation-Id"] == "corr-syn-2"
    assert transport.requests[1].headers["X-Causation-Id"] == "cause-syn-1"
    assert transport.requests[1].headers["X-FM-Environment"] == "HOMOLOGATION"

    payload = b'{"event":"document.authorized","synthetic":true}'
    key = b"synthetic-webhook-key"
    signature = hmac.new(key, payload, hashlib.sha256).hexdigest()
    assert verify_webhook_signature(payload, signature_hex=signature, key=key)


def test_tenant_scope_is_carried_by_each_bridge_client() -> None:
    transport_a = RecordingTransport()
    transport_b = RecordingTransport()
    _client(transport_a, tenant_id="tenant-syn-a").capability_query(b"{}", correlation_id="corr-a")
    _client(transport_b, tenant_id="tenant-syn-b").capability_query(b"{}", correlation_id="corr-b")
    assert transport_a.requests[0].headers["X-FM-Tenant-Id"] == "tenant-syn-a"
    assert transport_b.requests[0].headers["X-FM-Tenant-Id"] == "tenant-syn-b"
    assert transport_a.requests[0].headers != transport_b.requests[0].headers


def test_production_onboarding_cannot_complete_without_explicit_readiness() -> None:
    onboarding = SelfServiceOnboarding("onb-prod-syn", environment="PRODUCTION")
    for index, step in enumerate(ONBOARDING_SEQUENCE, start=1):
        onboarding.record(OnboardingEvidence(step, f"prod-ref-syn-{index}"))
    with pytest.raises(SelfServiceOnboardingError, match="explicit production readiness"):
        onboarding.complete()


def test_suspension_blocks_new_commercial_operations_but_preserves_fiscal_state() -> None:
    subscription = _subscription()
    subscription.transition(SubscriptionStatus.SUSPENDED)
    assert subscription.preserves_existing_fiscal_state is True
    with pytest.raises(CommercialBillingError, match="blocks new commercial operation"):
        subscription.require_entitlement("documents.issue")
    with pytest.raises(CommercialBillingError, match="does not accept new metered usage"):
        subscription.record_usage("documents.issue")


def test_missing_entitlement_and_quota_are_fail_closed() -> None:
    subscription = _subscription()
    with pytest.raises(CommercialBillingError, match="entitlement is not granted"):
        subscription.require_entitlement("support.premium")
    assert subscription.record_usage("documents.issue") == 1
    assert subscription.record_usage("documents.issue") == 2
    with pytest.raises(CommercialBillingError, match="quota exceeded"):
        subscription.record_usage("documents.issue")


def test_duplicate_synthetic_issue_keeps_same_idempotency_identity() -> None:
    transport = RecordingTransport()
    client = _client(transport)
    for correlation in ("corr-dup-1", "corr-dup-2"):
        client.issue(
            b'{"operation":"authorize","synthetic":true}',
            correlation_id=correlation,
            idempotency_key="idem-stable-syn",
        )
    assert len(transport.requests) == 2
    assert {request.headers["Idempotency-Key"] for request in transport.requests} == {
        "idem-stable-syn"
    }
    assert {request.headers["X-Correlation-Id"] for request in transport.requests} == {
        "corr-dup-1",
        "corr-dup-2",
    }
