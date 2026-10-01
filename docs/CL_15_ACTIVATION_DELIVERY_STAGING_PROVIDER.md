# CL-15 — Real Activation Delivery Provider for Staging

**Status:** IMPLEMENTATION CANDIDATE / REAL PROVIDER CREDENTIAL PENDING  
**Date:** 2026-10-01  
**Provider selected for staging:** Brevo transactional email free plan

## Objective

Close the CL-15 activation-delivery gap without introducing a second credential authority,
provider lock-in inside the Core, or a new recurring subscription during pre-launch work.

The canonical authorities remain unchanged:

- password/reset grant authority: `PasswordRecoveryService`;
- provider-neutral delivery adapter: `SecureActivationEmailDelivery`;
- external delivery port: `PasswordResetDelivery`;
- concrete provider transport: runtime-only adapter outside the Core.

## Current provider decision

Brevo is selected only as the first real **staging** transport.

The selection is operational, not constitutional. The Core does not import Brevo types or
persist Brevo-specific identifiers. Another transport can replace it behind the same
`ActivationMessageTransport` contract.

Production provider choice must be re-evaluated before CL-18 against deliverability, SLA,
data-processing terms, support, observability, cost and operational requirements.

## Runtime variables

The following values are supplied outside Git:

- `NFCORE_ACTIVATION_EMAIL_PROVIDER=brevo`;
- `NFCORE_ACTIVATION_EMAIL_API_KEY=<secret>`;
- `NFCORE_ACTIVATION_EMAIL_SENDER=<verified sender address>`;
- `NFCORE_ACTIVATION_BASE_URL=<HTTPS NFCore portal root>`;
- `NFCORE_ACTIVATION_EMAIL_TIMEOUT_SECONDS=10` (optional).

The API key must exist only in the approved runtime secret/configuration boundary. It must
never be committed, printed in logs, returned by readiness endpoints or placed in CI
artifacts.

If a provider is explicitly selected but its required values are missing/invalid, runtime
composition fails closed.

## Transport contract

The Brevo transport sends a plain-text transactional email through the fixed HTTPS endpoint
`https://api.brevo.com/v3/smtp/email`.

Security properties:

- endpoint is fixed in code, not caller-controlled;
- bounded timeout;
- provider/API failures are normalized without provider body or credential leakage;
- response must be 2xx and contain a non-empty provider message ID;
- recipient open-tracking consent is explicitly set to false for the activation message;
- raw reset token exists only in the ephemeral email body;
- `ActivationEmailMessage.__repr__` remains redacted.

## Secure activation URL

The canonical activation adapter intentionally produces:

`https://<portal>/#token=<one-time-reset-token>`

The token is in the URL fragment so it is not sent to the web server in the initial GET.

A CL-15 audit found the portal still expected the historical query-string form
`?reset_token=...`. This candidate change aligns the portal with the fragment contract while
temporarily preserving query-string compatibility for previously issued links.

After successful password setup, the portal removes both fragment/query token representations
from browser history.

## Acceptance gates

Internal implementation is not enough to close CL-15.

Required before `STAGING_DEPLOYED_AND_E2E_VALIDATED=true`:

1. CI for this candidate is fully green.
2. Merge is explicitly authorized and post-merge CI is green.
3. A Brevo free account/sender is configured and verified by the human owner.
4. The real API key is inserted only into Railway staging variables.
5. API and portal are deployed from the exact same certified main revision.
6. `/runtime/profile` proves:
   - `password_reset_delivery_configured=true`;
   - `commercial_activation_delivery_configured=true`.
7. Controlled real delivery is proven to an approved test inbox.
8. The received fragment link opens the password setup UI.
9. Password setup completes through the real staging API.
10. Login succeeds with the newly set password.
11. No token/API key/recipient PII is emitted into application logs.
12. Evidence is persisted.

## Cost-control classification

This staging provider path is deliberately compatible with a no-new-subscription pre-launch
strategy. A free-tier limitation must never be interpreted as production capacity or
commercial SLA.

Paid transactional-email capacity, a dedicated secret manager and any production-grade
delivery/retention/observability capability remain subject to CL-18 Go/No-Go preparation.
