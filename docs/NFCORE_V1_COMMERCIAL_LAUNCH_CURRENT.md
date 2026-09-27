# FM NFCORE V1 — Commercial Launch CURRENT

**Canonical status date:** 2026-09-27  
**Canonical NFCore repository:** `faabio3131/kordena-fiscal-engine-v2`  
**Canonical NFCore main:** `08294a0d86ee865bd5aa6eb9868885ae121d55c1`  
**Canonical FM commercial-site repository:** `faabio3131/fm-tecnologia-web-platform`  
**Canonical site main:** `34ca03515b3addf2c71497548445feba0b47dcf4`

This document is a CURRENT tracker, not authority over GitHub. Every resume must revalidate both repositories before work.

## Confirmed integrated NFCore baseline

The canonical NFCore main contains:

- CL-01 Production Composition Root;
- CL-02 Production Worker Runtime;
- CL-03 Production External Secret Boundary;
- CL-04 Staging Infrastructure Contract;
- CL-05 Cakto Commercial Runtime/E2E;
- CL-06 Commercial Onboarding and Customer Recovery E2E;
- Pricing Governance;
- CL-07 Premium Product Experience;
- CL-08 Durable Pricing Administration Runtime;
- CL-09 Commercial Release Authority;
- CL-10 Governed Cakto Checkout Authority.

CL-10 was merged through PR #64.

Certified candidate HEAD:
`1853183756fbbed687e08cc20aa1cef06803ab1e`

Candidate `FM NFCORE V1 CI` #431: **SUCCESS**.

Post-merge main:
`08294a0d86ee865bd5aa6eb9868885ae121d55c1`

Post-merge `FM NFCORE V1 CI` #432 / run `36353662606`: **SUCCESS** on that exact main SHA.

CL-10 reuses the existing Cakto commercial store and `CaktoPlanBinding`; it does not create a second checkout database.

Public purchase remains fail-closed. `purchase_enabled` requires:

1. explicit human `commercial_approved`;
2. published pricing;
3. complete enabled Cakto mapping for every active public plan/price pair;
4. Cakto webhook processing composed in runtime.

Trial release remains a separate authority and is not inferred from pricing `trial_days`.

## Confirmed integrated FM commercial-site baseline

The FM commercial site contains the premium institutional/product surface, the canonical NFCore commercial-offer consumer and the CL-10 checkout projection consumer.

### PR #20 — canonical commercial offer

Merged and certified.

Validated PR HEAD:
`85ca357b5e015f5cf85b2353b2580bcb72fce53a`

Evidence:

- Site Validation #518 / run `36351826809`: **SUCCESS**;
- Cloudflare Worker Validation #92 / run `36351826818`: **SUCCESS**.

The site consumes NFCore through the server-side same-origin flow:

`Browser -> /api/nfcore/commercial-offer -> NFCORE_API_URL/v1/commercial/offer`

`NFCORE_API_URL` remains server-side only. Missing/unavailable/invalid upstream state fails closed.

### PR #21 — governed Cakto checkout projection

Merged after exact-head certification.

Validated PR HEAD:
`da7c26d301dbb8f759d47ceb995cc755dc36e7cb`

Evidence:

- Site Validation #522 / run `36354076535`: **SUCCESS**;
- Cloudflare Worker Validation #96 / run `36354076558`: **SUCCESS**.

Current site main merge commit:
`34ca03515b3addf2c71497548445feba0b47dcf4`

Git compare from validated PR HEAD to the merge commit shows **zero file changes**. No separate post-merge workflow was emitted for that SHA, so no third gate is invented.

The site now:

- accepts `unconfigured | partial | configured` checkout projections;
- validates Cakto processing readiness;
- validates exact plan/price correlation;
- accepts only canonical HTTPS `pay.cakto.com.br` checkout URLs;
- renders `Contratar NFCore` only when the canonical NFCore payload is internally coherent and `purchase_enabled=true`;
- keeps arbitrary/malformed/contradictory upstream state fail-closed;
- does not hardcode NFCore prices or Cakto checkout URLs.

No Cloudflare deploy, DNS change, real NFCore runtime URL configuration, real Cakto credentials, billing activation, fiscal activation, homologation or Go-Live was performed.

## Current internal closure block — CL-11 design gate

A new INTERNAL integration gap was confirmed after CL-10/Site closure.

### CURRENT

`CaktoCommercialProcessor`:

- authenticates/processes Cakto events;
- derives a commercial tenant from Cakto `customer.id`;
- activates/suspends/cancels entitlements.

`CommercialCustomerProvisioningService` independently:

- creates/reuses the canonical Control Plane organization;
- creates/reuses the first OWNER account;
- creates an activation password-reset grant.

There is no CURRENT runtime bridge from a paid Cakto event to `CommercialCustomerProvisioningService`.

Therefore the chain:

`Site -> Checkout -> Payment -> Cakto event -> Entitlement`

is implemented, and:

`Trusted provisioning -> Organization -> OWNER -> activation/recovery -> login`

is implemented, but the transition:

`Paid Cakto event -> canonical organization + first OWNER`

is not yet proven end-to-end.

This is an **INTERNAL GAP**, not merely an external-credential blocker.

### External contract facts revalidated

Current official Cakto documentation states that order webhooks include top-level `customer.id`, `customer.name` and `customer.email`, and that an opaque `callback` supplied by the merchant in the checkout URL is returned in order webhooks.

Cakto explicitly warns not to place PII in the callback.

References are recorded in:

`docs/CL_11_POST_PURCHASE_PROVISIONING_DESIGN.md`

### TARGET candidate

The design candidate uses an NFCore-owned transient **Commercial Acquisition Intent** plus a server-generated opaque Cakto callback.

Key principles:

- do not infer NFCore organization legal identity from Cakto buyer name;
- do not persist raw Cakto customer PII in the webhook inbox;
- browser/site never supplies tenant_id, entitlement IDs, provider IDs, price amount or authority flags;
- NFCore validates the canonical commercial offer before creating checkout correlation;
- authenticated `purchase_approved`, not browser redirect, remains payment authority;
- the async worker correlates the payment to the acquisition intent and then invokes the existing canonical provisioning service;
- existing pricing, release, checkout, tenant, human identity, recovery and fiscal authorities remain unchanged.

Design document:

`docs/CL_11_POST_PURCHASE_PROVISIONING_DESIGN.md`

Status:

**DESIGN CANDIDATE / HUMAN ARCHITECTURAL APPROVAL REQUIRED — no CL-11 production code started.**

## Commercial readiness classification

### A — Functional readiness

Strong/certified through CL-10 on NFCore main.

The site commercial projection is also integrated and certified.

A remaining functional integration gap exists between paid Cakto acquisition and automatic first-OWNER provisioning. Therefore the complete real customer acquisition journey is not yet internally closed.

### B — Commercial surface parity

Site FM and NFCore share the same pricing/release/checkout projection.

No second pricing, release or checkout authority exists on the site.

The direct governed checkout CTA is implemented, but CL-11 must replace the final raw checkout handoff with a correlated acquisition initiation flow before automatic post-payment provisioning can be considered complete.

### C — Production technical readiness

Internal provider-neutral contracts exist for:

- secrets;
- staging/deploy;
- observability;
- backup/recovery;
- runtime profiles;
- Cakto webhook/worker;
- onboarding/recovery.

Real provider-specific staging/production infrastructure is not yet evidenced.

### D — Operational readiness

Internal runbooks/gates, observability boundaries and backup/restore evidence exist.

Real external incident/monitoring endpoints, production credentials, provider deploy driver and operational cutover remain unevidenced.

### E — Commercial readiness

**NOT COMMERCIAL LIVE.**

Internal blocker:

1. CL-11 post-purchase acquisition -> canonical organization/OWNER provisioning bridge is not implemented/certified.

External/human dependencies after internal closure include:

1. real approved plans/prices/promotions published through governed pricing;
2. real Cakto product/offer identifiers configured through checkout administration;
3. real Cakto API credentials and webhook secret stored in the approved external secret manager;
4. public HTTPS Cakto webhook endpoint;
5. controlled authenticated real Cakto event plus successful reconciliation;
6. authorized NFCore environment URL configured server-side in the FM site;
7. real password-reset email/SMS delivery;
8. real Secret Manager/Vault provider and all required secret material;
9. real staging/production hosting, PostgreSQL, ingress and HTTPS;
10. real provider deploy driver and staging certification;
11. real fiscal certificates/CSC/provider credentials;
12. exact launch fiscal cells by document × operation × jurisdiction × provider;
13. official homologation evidence for every sold cell;
14. controlled real fiscal pilot;
15. legal/LGPD operational review where required;
16. explicit human Go/No-Go / `PRODUCTION_APPROVED`;
17. authorized deploy, DNS/cutover and production smoke.

## Repository visibility

NFCore and the FM commercial-site repositories remain intentionally **PUBLIC temporarily** because the private GitHub Actions monthly quota was exhausted and CI runners were blocked.

While public:

- never insert real secrets, certificates, CSC, passwords, Cakto tokens, cloud credentials or webhook secrets into source/history;
- configure real Cakto product/offer IDs through governed runtime administration;
- keep secret/dependency/vulnerability scanning enabled;
- once the heavy internal CI cycle ends, explicitly notify the operator that the repositories can return to PRIVATE.

## Next execution order

1. Resolve CL-11 architectural decision and freeze the acquisition/provisioning contract.
2. Implement CL-11 in the NFCore canonical line with forward schema evolution, idempotency, PII minimization and full gates.
3. Update Site FM purchase initiation to use the approved CL-11 same-origin/BFF flow.
4. Re-audit remaining internally solvable commercial/onboarding/recovery/observability gaps.
5. Select/provision external infrastructure and Secret Manager/Vault under explicit human decision.
6. Provision real staging and execute staging gates.
7. Configure/test real Cakto, webhook/reconciliation and password-reset delivery.
8. Execute exact fiscal homologation matrix and controlled fiscal pilot with real evidence.
9. Perform final production readiness audit.
10. Human Go/No-Go.
11. Authorized production cutover and hypercare.

No later block may convert `BLOCKED_EXTERNAL` into READY without reproducible external evidence.
