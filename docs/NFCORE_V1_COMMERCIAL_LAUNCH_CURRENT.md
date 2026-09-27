# FM NFCORE V1 — Commercial Launch CURRENT

**Canonical status date:** 2026-09-27
**Canonical NFCore repository:** `faabio3131/kordena-fiscal-engine-v2`
**Canonical NFCore main before CL-10:** `f679a8a25012235a314ccef1cd78f67abc88ccfb`
**Canonical FM commercial-site repository:** `faabio3131/fm-tecnologia-web-platform`
**Canonical site main:** `f863930cbcf00cc3dfa8f489311274e62e655901`

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
- CL-09 Commercial Release Authority.

CL-09 was merged through PR #63 at `f679a8a25012235a314ccef1cd78f67abc88ccfb`.

Post-merge `FM NFCORE V1 CI` #428 passed on that exact main commit.

## Confirmed integrated FM commercial-site baseline

The FM commercial site contains the previously consolidated premium institutional/product surface plus the canonical NFCore commercial-offer consumer.

Site PR #20 was certified and merged.

Current site main:
`f863930cbcf00cc3dfa8f489311274e62e655901`.

The exact pre-merge content passed:

- Site Validation #518 / run `36351826809`: SUCCESS;
- Cloudflare Worker Validation #92 / run `36351826818`: SUCCESS.

Git compare from the validated PR HEAD `85ca357b5e015f5cf85b2353b2580bcb72fce53a` to the site main merge commit showed zero file changes.

The site now consumes NFCore through the server-side same-origin flow:

`Browser -> /api/nfcore/commercial-offer -> NFCORE_API_URL/v1/commercial/offer`

`NFCORE_API_URL` is server-side only. Missing/unavailable/invalid upstream state fails closed.

No Cloudflare deploy, DNS change or production publication was performed.

## Current internal closure block

CL-10 — Governed Cakto Checkout Authority is implemented in PR #64.

Functional candidate HEAD:
`d5423cd2e74dba19f129a84e259fd609d1fdcb3a`

`FM NFCORE V1 CI` #429 / run `36352614997`: **SUCCESS**.

Pytest: **953 passed, 1 warning**.

CL-10 reuses the existing Cakto commercial store and `CaktoPlanBinding`; it does not create a second checkout database.

Published prices may reference a Cakto product/offer using `cakto://product/offer`. The NFCore resolves that reference against the durable Cakto binding and derives the trusted Cakto checkout URL from the canonical binding.

Public purchase remains fail-closed. `purchase_enabled` requires:

1. explicit human `commercial_approved`;
2. published pricing;
3. complete enabled Cakto mapping for every active public plan/price pair;
4. Cakto webhook processing composed in runtime.

Trial release remains a separate authority and is not inferred from pricing `trial_days`.

## Commercial readiness classification

### A — Functional readiness

Internally strong/certified through CL-09 on main. CL-10 is a certification candidate pending exact final documentary-head CI and green-gated promotion.

Core, Web runtime, auth/session/RBAC, tenant/unit authority, worker, PostgreSQL, onboarding/recovery, premium portal, durable pricing, commercial release and governed checkout configuration are implemented in the canonical line.

### B — Commercial surface parity

The FM site and NFCore now share one commercial-offer contract.

The site does not duplicate NFCore pricing, release or checkout authority. Until an authorized NFCore environment is configured through server-side `NFCORE_API_URL`, the public site remains visibly fail-closed.

After CL-10 integration, a follow-up site contract block must accept the new checkout projection states and render a purchase CTA only when NFCore itself returns `purchase_enabled=true` plus a validated canonical Cakto checkout URL.

### C — Production technical readiness

Internal provider-neutral contracts exist for secrets, staging/deploy, observability, backup/recovery and runtime profiles.

Real provider-specific staging/production infrastructure is not yet evidenced.

### D — Operational readiness

Internal runbooks/gates and backup/restore evidence exist. Real external incident/monitoring endpoints, production credentials, provider driver and operational cutover have not yet been evidenced.

### E — Commercial readiness

**NOT COMMERCIAL LIVE.**

Remaining external/human dependencies include:

1. real approved plans/prices/promotions published through governed pricing;
2. real Cakto product/offer identifiers configured through checkout administration;
3. real Cakto API credentials and webhook secret stored in the approved external secret manager;
4. public HTTPS Cakto callback;
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

- no real secrets, certificates, CSC, passwords, Cakto tokens, cloud credentials or webhook secrets may enter source/history;
- real Cakto product/offer IDs should be configured through runtime administration, not committed as source fixtures;
- secret/dependency/vulnerability scanning must remain enabled;
- once the heavy internal CI cycle ends, explicitly notify the operator that the repositories can return to PRIVATE.

## Next execution order

1. Finish CL-10 exact-head certification and green-gated promotion to NFCore main.
2. Update the FM site contract to consume CL-10 checkout projection and render purchase CTA only from canonical `purchase_enabled=true` + trusted Cakto URL.
3. Audit and close any remaining internally solvable commercial/onboarding/recovery/observability gaps.
4. Select/provision external infrastructure and Secret Manager/Vault under explicit human decision.
5. Provision real staging and execute staging gates.
6. Configure/test real Cakto, callback/reconciliation and password-reset delivery.
7. Execute exact fiscal homologation matrix and controlled fiscal pilot with real evidence.
8. Perform final production readiness audit.
9. Human Go/No-Go.
10. Authorized production cutover and hypercare.

No later block may convert `BLOCKED_EXTERNAL` into READY without reproducible external evidence.
