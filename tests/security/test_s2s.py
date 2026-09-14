from datetime import UTC, datetime, timedelta

import pytest

from kordena_fiscal.domain import (
    FiscalAccountBinding,
    FiscalAccountId,
    FiscalBindingRegistry,
    FiscalEnvironment,
    FiscalUnitId,
    FiscalValidationError,
    HostNamespace,
    HostScope,
)
from kordena_fiscal.security import (
    CallerIdentity,
    FiscalCapability,
    FixedWindowRateLimiter,
    HostScopeGrant,
    InMemorySecurityAuditSink,
    InMemoryWebhookKeyRing,
    S2SAuthorizer,
    SecurityAuditOutcome,
    WebhookSecurity,
    WebhookSignature,
    WebhookSignatureError,
    WorkloadAuthenticationError,
    WorkloadAuthenticator,
    WorkloadAuthorizationError,
    WorkloadCredentialRecord,
    WorkloadRateLimitError,
)

NOW = datetime(2026, 9, 11, 20, 0, tzinfo=UTC)
SECRET = "synthetic-workload-secret-0123456789abcdef"


def _host_scope(
    namespace: str = "kordena",
    tenant_id: str = "tenant-a",
    unit_id: str = "unit-1",
) -> HostScope:
    return HostScope(
        namespace=HostNamespace(namespace),
        tenant_id=tenant_id,
        unit_id=unit_id,
    )


def _caller(
    *,
    namespace: str = "kordena",
    capabilities: frozenset[FiscalCapability] | None = None,
    grants: tuple[HostScopeGrant, ...] | None = None,
) -> CallerIdentity:
    return CallerIdentity(
        caller_id=f"{namespace}-backend",
        host_namespace=HostNamespace(namespace),
        capabilities=capabilities
        or frozenset(
            {
                FiscalCapability.ISSUE,
                FiscalCapability.QUERY,
                FiscalCapability.RECONCILE,
            }
        ),
        scope_grants=grants or (HostScopeGrant(tenant_id="tenant-a"),),
    )


def _credential(
    caller: CallerIdentity | None = None,
    *,
    credential_id: str = "cred-current",
    secret: str = SECRET,
    revoked: bool = False,
    valid_from: datetime | None = None,
    expires_at: datetime | None = None,
) -> WorkloadCredentialRecord:
    return WorkloadCredentialRecord.from_secret(
        credential_id=credential_id,
        caller=caller or _caller(),
        secret=secret,
        valid_from=valid_from or (NOW - timedelta(hours=1)),
        expires_at=expires_at or (NOW + timedelta(hours=1)),
        revoked=revoked,
    )


def _registry() -> FiscalBindingRegistry:
    bindings = (
        FiscalAccountBinding(
            binding_id="bind-kordena-a-1",
            host_scope=_host_scope(),
            fiscal_account_id=FiscalAccountId("fiscal-account-k"),
            fiscal_unit_id=FiscalUnitId("fiscal-unit-k1"),
        ),
        FiscalAccountBinding(
            binding_id="bind-iron-a-1",
            host_scope=_host_scope("iron", "tenant-a", "unit-1"),
            fiscal_account_id=FiscalAccountId("fiscal-account-i"),
            fiscal_unit_id=FiscalUnitId("fiscal-unit-i1"),
        ),
    )
    return FiscalBindingRegistry(bindings)


def _authenticated(caller: CallerIdentity | None = None):
    authenticator = WorkloadAuthenticator((_credential(caller),))
    return authenticator.authenticate(
        credential_id="cred-current",
        presented_secret=SECRET,
        now=NOW,
    )


def test_workload_authentication_accepts_hashed_secret_without_storing_raw_secret() -> None:
    record = _credential()
    assert record.secret_sha256 != SECRET
    assert len(record.secret_sha256) == 64

    authenticated = WorkloadAuthenticator((record,)).authenticate(
        credential_id=record.credential_id,
        presented_secret=SECRET,
        now=NOW,
    )

    assert authenticated.identity.caller_id == "kordena-backend"


@pytest.mark.parametrize(
    ("record", "secret"),
    [
        (_credential(), "wrong-secret-value-that-is-still-long-enough"),
        (_credential(revoked=True), SECRET),
        (
            _credential(
                valid_from=NOW + timedelta(minutes=1),
                expires_at=NOW + timedelta(hours=2),
            ),
            SECRET,
        ),
        (
            _credential(
                valid_from=NOW - timedelta(hours=2),
                expires_at=NOW,
            ),
            SECRET,
        ),
    ],
)
def test_workload_authentication_fails_closed(
    record: WorkloadCredentialRecord,
    secret: str,
) -> None:
    with pytest.raises(WorkloadAuthenticationError):
        WorkloadAuthenticator((record,)).authenticate(
            credential_id=record.credential_id,
            presented_secret=secret,
            now=NOW,
        )


def test_workload_authentication_supports_credential_rotation() -> None:
    caller = _caller()
    previous = _credential(
        caller,
        credential_id="cred-previous",
        secret="previous-synthetic-secret-0123456789abcdef",
    )
    current = _credential(caller, credential_id="cred-current", secret=SECRET)
    authenticator = WorkloadAuthenticator((previous, current))

    old_identity = authenticator.authenticate(
        credential_id="cred-previous",
        presented_secret="previous-synthetic-secret-0123456789abcdef",
        now=NOW,
    )
    new_identity = authenticator.authenticate(
        credential_id="cred-current",
        presented_secret=SECRET,
        now=NOW,
    )

    assert old_identity.identity == new_identity.identity


def test_authorizer_binds_authenticated_caller_to_internal_fiscal_scope() -> None:
    audit = InMemorySecurityAuditSink()
    authorized = S2SAuthorizer(bindings=_registry(), audit_sink=audit).authorize(
        caller=_authenticated(),
        host_scope=_host_scope(),
        environment=FiscalEnvironment.PRODUCTION,
        capability=FiscalCapability.ISSUE,
        correlation_id="corr-001",
        now=NOW,
    )

    assert authorized.scope.host_namespace == "kordena"
    assert authorized.scope.tenant_id == "fiscal-account-k"
    assert authorized.scope.unit_id == "fiscal-unit-k1"
    assert audit.records[-1].outcome is SecurityAuditOutcome.ALLOWED
    assert audit.records[-1].reason_code == "authorized"


def test_authorizer_rejects_cross_host_spoofing_before_binding_resolution() -> None:
    audit = InMemorySecurityAuditSink()
    authorizer = S2SAuthorizer(bindings=_registry(), audit_sink=audit)

    with pytest.raises(WorkloadAuthorizationError):
        authorizer.authorize(
            caller=_authenticated(),
            host_scope=_host_scope("iron", "tenant-a", "unit-1"),
            environment=FiscalEnvironment.PRODUCTION,
            capability=FiscalCapability.ISSUE,
            correlation_id="corr-cross-host",
            now=NOW,
        )

    assert audit.records[-1].reason_code == "host_namespace_mismatch"


def test_authorizer_rejects_missing_capability() -> None:
    caller = _caller(capabilities=frozenset({FiscalCapability.QUERY}))
    audit = InMemorySecurityAuditSink()

    with pytest.raises(WorkloadAuthorizationError):
        S2SAuthorizer(bindings=_registry(), audit_sink=audit).authorize(
            caller=_authenticated(caller),
            host_scope=_host_scope(),
            environment=FiscalEnvironment.HOMOLOGATION,
            capability=FiscalCapability.CANCEL,
            correlation_id="corr-capability",
            now=NOW,
        )

    assert audit.records[-1].reason_code == "capability_denied"


def test_authorizer_rejects_cross_tenant_and_cross_unit_scope() -> None:
    caller = _caller(grants=(HostScopeGrant(tenant_id="tenant-a", unit_id="unit-1"),))
    authorizer = S2SAuthorizer(
        bindings=_registry(),
        audit_sink=InMemorySecurityAuditSink(),
    )

    for host_scope in (
        _host_scope("kordena", "tenant-b", "unit-1"),
        _host_scope("kordena", "tenant-a", "unit-2"),
    ):
        with pytest.raises(WorkloadAuthorizationError):
            authorizer.authorize(
                caller=_authenticated(caller),
                host_scope=host_scope,
                environment=FiscalEnvironment.PRODUCTION,
                capability=FiscalCapability.QUERY,
                correlation_id="corr-scope",
                now=NOW,
            )


def test_authorizer_fails_closed_when_exact_fiscal_binding_does_not_exist() -> None:
    caller = _caller(grants=(HostScopeGrant(),))
    audit = InMemorySecurityAuditSink()

    with pytest.raises(FiscalValidationError):
        S2SAuthorizer(bindings=_registry(), audit_sink=audit).authorize(
            caller=_authenticated(caller),
            host_scope=_host_scope("kordena", "tenant-new", "unit-new"),
            environment=FiscalEnvironment.PRODUCTION,
            capability=FiscalCapability.QUERY,
            correlation_id="corr-no-binding",
            now=NOW,
        )

    assert audit.records[-1].reason_code == "binding_not_found"


def test_rate_limiter_is_keyed_by_authenticated_caller() -> None:
    audit = InMemorySecurityAuditSink()
    authorizer = S2SAuthorizer(
        bindings=_registry(),
        audit_sink=audit,
        rate_limiter=FixedWindowRateLimiter(max_requests=1, window_seconds=60),
    )
    authenticated = _authenticated()

    authorizer.authorize(
        caller=authenticated,
        host_scope=_host_scope(),
        environment=FiscalEnvironment.PRODUCTION,
        capability=FiscalCapability.QUERY,
        correlation_id="corr-rate-1",
        now=NOW,
    )
    with pytest.raises(WorkloadRateLimitError):
        authorizer.authorize(
            caller=authenticated,
            host_scope=_host_scope(),
            environment=FiscalEnvironment.PRODUCTION,
            capability=FiscalCapability.QUERY,
            correlation_id="corr-rate-2",
            now=NOW + timedelta(seconds=1),
        )

    assert audit.records[-1].reason_code == "rate_limited"
    assert audit.records[-1].outcome is SecurityAuditOutcome.DENIED


def test_scope_grant_rejects_unit_without_tenant() -> None:
    with pytest.raises(FiscalValidationError):
        HostScopeGrant(unit_id="unit-1")


def _webhook_security() -> WebhookSecurity:
    key_ring = InMemoryWebhookKeyRing(
        active_key_id="key-2026-09",
        keys={
            "key-2026-08": b"previous-webhook-secret-32-bytes!!",
            "key-2026-09": b"current-webhook-secret--32-bytes!!",
        },
    )
    return WebhookSecurity(
        key_resolver=key_ring,
        signing_key_id=key_ring.active_key_id,
        max_age_seconds=300,
        max_future_skew_seconds=30,
    )


def test_webhook_signature_round_trip_and_header_parse() -> None:
    body = b'{"event_id":"evt-001"}'
    security = _webhook_security()
    signature = security.sign(body, now=NOW)
    parsed = WebhookSignature.parse(signature.header_value)

    security.verify(body, parsed, now=NOW + timedelta(seconds=10))

    assert parsed.key_id == "key-2026-09"


def test_webhook_signature_rejects_tampered_body() -> None:
    security = _webhook_security()
    signature = security.sign(b'{"amount":"10.00"}', now=NOW)

    with pytest.raises(WebhookSignatureError):
        security.verify(b'{"amount":"999.00"}', signature, now=NOW)


def test_webhook_signature_rejects_stale_and_future_signatures() -> None:
    security = _webhook_security()
    stale = security.sign(b"{}", now=NOW - timedelta(minutes=10))
    future = security.sign(b"{}", now=NOW + timedelta(minutes=2))

    with pytest.raises(WebhookSignatureError, match="stale"):
        security.verify(b"{}", stale, now=NOW)
    with pytest.raises(WebhookSignatureError, match="future"):
        security.verify(b"{}", future, now=NOW)


def test_webhook_verifier_accepts_previous_rotation_key() -> None:
    previous_ring = InMemoryWebhookKeyRing(
        active_key_id="key-2026-08",
        keys={
            "key-2026-08": b"previous-webhook-secret-32-bytes!!",
            "key-2026-09": b"current-webhook-secret--32-bytes!!",
        },
    )
    previous_security = WebhookSecurity(
        key_resolver=previous_ring,
        signing_key_id=previous_ring.active_key_id,
    )
    signature = previous_security.sign(b"rotation", now=NOW)

    _webhook_security().verify(b"rotation", signature, now=NOW)


@pytest.mark.parametrize(
    "header",
    [
        "t=1,kid=key",
        "t=abc,kid=key,v1=" + ("0" * 64),
        "t=1,kid=key,v1=" + ("0" * 64) + ",extra=x",
        "t=1,t=2,kid=key,v1=" + ("0" * 64),
    ],
)
def test_webhook_signature_parser_rejects_malformed_headers(header: str) -> None:
    with pytest.raises((WebhookSignatureError, FiscalValidationError)):
        WebhookSignature.parse(header)
