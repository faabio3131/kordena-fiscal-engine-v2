# CL-11.7A — Canonical First-Party Acquisition Boundary — Certification

**Status:** CERTIFICATION CANDIDATE — implementation HEAD passed complete CI; exact documentary HEAD must pass before merge.  
**Date:** 2026-09-28  
**Repository:** `faabio3131/kordena-fiscal-engine-v2`  
**Base main:** `07cb0f861146ad236c801e582a5a2623cd1facc0`  
**PR:** #73  
**Branch:** `feat/nfcore-cl11-first-party-acquisition`  
**Implementation HEAD:** `26964bf48ce195eff81d90a9a68bc3dba146fb62`  
**Implementation CI:** `FM NFCORE V1 CI #479` / run `36430150636` — SUCCESS

## Objective

Implement the NFCore-owned boundary for CL-11.7 first-party Site purchases without turning the Site or a payment provider into commercial, tenant, RBAC, entitlement or fiscal authority.

The canonical flow introduced by this block is:

```text
Site BFF
 -> signed minimum acquisition facts
 -> NFCore canonical acquisition reference
 -> selected provider checkout starter
 -> provider payment
 -> authenticated/validated commercial event
 -> acquisition correlation
 -> canonical purchase
 -> existing claim/provisioning/activation chain
```

## Canonical authority

NFCore owns the acquisition reference.

The browser cannot supply or manufacture:

- provider selection;
- payment success;
- tenant identity;
- OWNER authority;
- entitlements;
- fiscal-production authority.

The provider remains an adapter boundary.

## New canonical acquisition state

Migration 11, `cl11_first_party_acquisition`, adds durable pre-payment acquisition state containing:

- NFCore-owned opaque acquisition id;
- SHA-256 of the idempotency key;
- SHA-256 request fingerprint;
- selected provider id;
- canonical plan id;
- canonical price id;
- minimum buyer e-mail;
- legal/organization name;
- created/expires timestamps;
- optional immutable link to the resulting canonical purchase.

No raw idempotency key is persisted.

PII-bearing acquisition representations redact e-mail and legal name.

## First-party application service

`CommercialAcquisitionService`:

- reuses the canonical release/pricing/checkout/readiness authorities;
- reuses the CL-11.6 purchase-readiness gate;
- validates the selected canonical plan/price against the active checkout projection;
- generates an NFCore-owned reference;
- is idempotent by hashed key + request fingerprint;
- rejects idempotency-key payload drift;
- rejects expired acquisition replay;
- delegates provider redirect construction only through the provider-neutral `CommercialCheckoutStarter` port;
- validates the returned checkout URL as absolute HTTPS without embedded credentials.

No Cakto-specific starter is implemented in this block.

## Server-to-server boundary

`POST /v1/commercial/acquisitions` is mounted only when the runtime has all required first-party dependencies.

The boundary:

- verifies timestamped HMAC-SHA256 using the existing provider-neutral `WebhookSecurity`;
- requires `Idempotency-Key`;
- rate-limits by signing key id;
- accepts only `plan_id`, `price_id`, `buyer_email`, `legal_name`;
- rejects added authority fields;
- returns no buyer PII;
- returns no tenant/account/entitlement/payment-success authority;
- remains fail-closed when the purchase path is not operationally ready.

No production secret is present in the repository.

## Validated event correlation

`ValidatedCommercialEvent` may carry the opaque NFCore acquisition reference.

Before a paid event can reuse first-party identity, fulfillment requires:

- acquisition exists;
- acquisition is not expired;
- acquisition is not bound to another purchase;
- provider matches;
- canonical plan matches;
- canonical price matches;
- buyer e-mail matches when supplied by the provider.

Any mismatch fails closed and rolls back the commercial event receipt and purchase creation.

A successful correlation may carry the verified minimum buyer/legal identity into the canonical purchase, but does not create a tenant or account. Tenant/OWNER creation remains in the existing secure claim/provisioning path.

## Provider independence

The new provider-neutral `CommercialCheckoutStarter` is a port, not a provider implementation.

CL-11.7A does not:

- make Cakto canonical;
- implement a real Cakto first-party correlation;
- configure a provider account/product/offer;
- introduce Hotmart/Kax as real integrations.

Provider-specific reconciliation remains CL-11.8/CL-11.9.

## Migration governance

Migration policy is contiguous through version 11 and the new migration is checked by the existing destructive-migration guard.

Tests cover fresh schema and upgrade to v11, including upgrade from pre-v11 state.

## Security evidence

The tests prove:

- unsigned acquisition request is rejected;
- body tampering invalidates HMAC;
- extra browser authority such as `payment_success` is rejected;
- authenticated caller is rate-limited;
- idempotency replay returns the same NFCore reference;
- idempotency-key data drift is rejected;
- purchase-readiness failure blocks acquisition;
- unavailable plan/price blocks acquisition;
- provider/plan/price/e-mail collisions on paid-event correlation fail closed;
- expired acquisition reference fails closed;
- re-binding an acquisition to another purchase fails closed;
- event/purchase writes roll back on correlation conflict;
- tenant/account remain absent before the canonical claim path.

## CI evidence

Implementation HEAD `26964bf48ce195eff81d90a9a68bc3dba146fb62` passed `FM NFCORE V1 CI #479` with the complete quality matrix green:

- repository secret scan;
- migration policy;
- Ruff;
- Mypy;
- full Pytest;
- Python dependency audit;
- Node dependency audit;
- frontend lint/typecheck/tests/build;
- critical E2E;
- compose and operational script validation;
- runtime image builds;
- non-root validation;
- insecure production profile rejection;
- API/worker/portal smokes;
- forbidden-secret artifact inspection;
- container vulnerability policy;
- SBOM generation/upload;
- PostgreSQL backup/restore rehearsal;
- application readiness against restored database.

## Scope explicitly not performed

This block does not authorize or perform:

- Site FM production secret configuration;
- real Cakto correlation metadata;
- real payment;
- deploy;
- DNS/TLS changes;
- staging/production activation;
- fiscal homologation;
- fiscal production activation;
- `PRODUCTION_APPROVED`;
- Go-Live.

## Exit condition

The exact documentary HEAD must pass the complete `FM NFCORE V1 CI` matrix.  
After merge and post-merge certification, CL-11.7B may implement the Site FM same-origin BFF and first-party customer UX against this contract.
