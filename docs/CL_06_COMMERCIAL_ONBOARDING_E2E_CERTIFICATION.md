# CL-06 — Commercial Onboarding E2E Certification

## Scope

CL-06 closes the internal customer-journey gaps that can be completed without inventing external Cakto, website, email/SMS or fiscal-production evidence.

The implementation deliberately reuses the canonical Control Plane, human identity/session repositories, password-recovery service and durable portal executor. It does not create a second authentication system, tenant authority, billing authority or fiscal authority.

## Internally implemented journey

The internally testable journey now contains:

1. trusted commercial provisioning of the canonical organization and first OWNER account;
2. one-time activation/reset grant created for a newly provisioned owner;
3. browser login and session authority derived only from the persisted account;
4. generic password-reset request that does not disclose whether an account exists;
5. external reset delivery through an injected port, never by returning the token from the request endpoint;
6. one-time password reset that revokes existing sessions;
7. authenticated portal bootstrap with an explicit onboarding stage;
8. tenant-scoped self-service unit onboarding using the tenant from the session, never from browser authority fields;
9. idempotent retry of identical unit setup;
10. initial customer unit restricted to homologation, with no fiscal-production promotion;
11. navigation constrained to backend-declared durable surfaces so unavailable product areas are not presented as functioning screens.

## Trusted provisioning boundary

Creating a Control Plane organization is a privileged global administrative operation. CL-06 therefore does **not** expose public browser self-signup that can manufacture global authority.

`CommercialCustomerProvisioningService` is the trusted server-side ingress intended to be called only after the commercial acquisition/trial channel has authenticated and validated the customer context. It creates the existing canonical organization and human OWNER account idempotently. It returns an activation reset only to the trusted caller; it is not an HTTP browser endpoint.

The FM website/Cakto orchestration that will invoke this ingress with real customer data is an external integration dependency and is not fabricated inside this repository.

## Password recovery boundary

The HTTP request endpoint always returns the same accepted response for known and unknown accounts. A raw reset token is never returned by the request endpoint and is never logged by this implementation.

A production email/SMS delivery provider must implement the injected `PasswordResetDelivery` port. Without that provider, the public request remains non-enumerating but no external message is sent.

## Portal/onboarding boundary

The portal exposes only backend-declared durable surfaces. Basic unit onboarding is available only to a session with `configuration.write`, requires CSRF plus `Idempotency-Key`, derives tenant identity from the authenticated session and creates only a homologation-enabled unit.

If the trusted commercial provisioning step has not created the organization, onboarding fails closed with `COMMERCIAL_PROVISIONING_REQUIRED` rather than granting the browser global Control Plane authority.

## Test evidence

The CL-06 suite covers:

- known/unknown password-reset request indistinguishability;
- reset token not returned in the request response;
- one-time reset completion;
- existing-session revocation after password change;
- old-password rejection and new-password acceptance;
- missing external delivery behavior without account enumeration;
- trusted organization/OWNER provisioning and idempotent retry;
- cross-tenant owner-email collision rejection;
- conflicting organization identity rejection;
- owner self-service unit onboarding;
- homologation-only initial unit;
- idempotent onboarding replay;
- browser tenant mass-assignment rejection;
- frontend contracts for recovery, CSRF/idempotency and backend-constrained navigation.

The existing broader commercial/fiscal suites remain authoritative for entitlement, quota, fiscal operation and production-authority invariants.

## External blockers

The following are real external integration inputs, not internal engineering evidence:

- real Cakto account/offer/product configuration and controlled event delivery;
- FM website/post-purchase handoff into trusted commercial provisioning;
- selected production email/SMS reset-delivery provider and credentials;
- public HTTPS production/staging endpoints and infrastructure from CL-04;
- real fiscal credentials/homologation/pilot/production approvals.

Until those integrations are configured and proven, the maximum factual state is:

`INTERNAL_COMMERCIAL_ONBOARDING_READY / BLOCKED_EXTERNAL`

This state is not `DEPLOYED`, `LIVE`, `CUTOVER_COMPLETE`, fiscal `HOMOLOGATED` or `PRODUCTION_APPROVED`.

## Certification rule

The exact certified SHA is the final PR HEAD containing this document only after the complete `FM NFCORE V1 CI` matrix reports `completed/success`. The immutable SHA and workflow run are recorded in the execution report/PR evidence after CI completion.

No merge, deploy, DNS change, cutover, real fiscal emission or fiscal production activation is authorized by this document.
