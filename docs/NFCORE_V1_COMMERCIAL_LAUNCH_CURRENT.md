# FM NFCORE V1 — Commercial Launch CURRENT

**Canonical status date:** 2026-09-27  
**Canonical NFCore repository:** `faabio3131/kordena-fiscal-engine-v2`  
**Canonical NFCore main before CL-10R:** `08294a0d86ee865bd5aa6eb9868885ae121d55c1`  
**Canonical FM commercial-site repository:** `faabio3131/fm-tecnologia-web-platform`  
**Canonical Site main before provider-neutral correction:** `34ca03515b3addf2c71497548445feba0b47dcf4`

This document is a CURRENT tracker, not authority over GitHub. Every resume must revalidate both repositories before work.

## Architecture authority reconciled

The FM Master Foundation Architecture and the existing NFCore commercial configurability decisions require:

- one evolving product line;
- domain/application authority independent from accidental infrastructure details;
- external providers behind adapters/boundaries;
- pricing, checkout, billing and fiscal production authority kept separate;
- supported customer/provider differences resolved through governed configuration;
- no customer-specific source fork;
- no secret material in source;
- no external sales channel becoming the canonical business authority.

NFCore is a commercial, configurable SaaS. Cakto, Hotmart, Kax, a first-party FM checkout, marketplaces or future channels are external sales/integration options. A previously unsupported protocol/provider may require one reusable adapter implementation; after the capability exists, account/product/offer/secret differences are configuration.

## Confirmed integrated NFCore main

Current `main` at the start of CL-10R:

`08294a0d86ee865bd5aa6eb9868885ae121d55c1`

The integrated line contains the commercial/fiscal foundation through CL-10, including:

- canonical auth/session/RBAC and tenant/unit authority;
- durable Control Plane and PostgreSQL;
- provider-neutral fiscal configuration and provider selection;
- external secret boundaries;
- billing plans/subscriptions/entitlements independent from fiscal authority;
- governed pricing with generic `external_price_reference`;
- CL-09 human Commercial Release Authority;
- Cakto provider-specific webhook/persistence/reconciliation adapter;
- CL-06 canonical commercial provisioning of organization + first OWNER;
- CL-10 Cakto checkout administration and public checkout projection.

Post-merge `FM NFCORE V1 CI` #432 previously passed on exact main `08294a0d...`.

## Confirmed integrated Site main

Current Site `main` at the start of the correction:

`34ca03515b3addf2c71497548445feba0b47dcf4`

The Site consumes NFCore server-side through:

`Browser -> /api/nfcore/commercial-offer -> NFCORE_API_URL/v1/commercial/offer`

The BFF is fail-closed and `NFCORE_API_URL` remains server-side only.

## Reconciliation finding — localized CL-10 regression

**FATO CONFIRMADO:** the pre-CL-10 commercial/billing/configuration foundation is provider-neutral.

**FATO CONFIRMADO:** CL-10 introduced a localized architectural regression by making the canonical public commercial offer depend directly on Cakto checkout types/readiness. Site PR #21 mirrored that regression by requiring `provider="cakto"` and the canonical Cakto checkout host.

This did not invalidate the underlying billing, pricing, tenant, provisioning, fiscal or Cakto adapter architecture. The correction is localized.

## CL-10R — provider-independence correction

PR #66: `CL-10R — restore commercial provider independence`  
Branch: `fix/nfcore-commercial-provider-independence`  
Status: **DRAFT / IMPLEMENTED / FINAL CI REQUIRED**

CL-10R:

- adds the canonical provider-neutral `CommercialCheckoutProjector` contract;
- removes Cakto imports/types from `web/commercial_release.py`;
- preserves Cakto as a provider-specific adapter implementing the neutral contract;
- makes Cakto checkout composition opt-in instead of unconditional;
- adds `NFCORE_COMMERCIAL_CHECKOUT_PROVIDER` as runtime configuration;
- keeps no-provider state fail-closed;
- adds a provider-independence architecture fitness test using a synthetic non-Cakto provider;
- does not create a second billing, pricing, tenant or checkout authority.

Formal candidate evidence:
`docs/CL_10R_COMMERCIAL_PROVIDER_INDEPENDENCE_CERTIFICATION.md`.

## Site provider-neutral correction

Site PR #22: `NFCore — restore provider-neutral checkout contract`  
Branch: `fix/site-nfcore-provider-neutral-checkout`  
Status: **DRAFT / IMPLEMENTED / FINAL DOCUMENTARY CI REQUIRED**

The Site contract now:

- accepts a governed provider identifier instead of literal Cakto;
- uses no hardcoded checkout-provider host;
- validates checkout URLs as HTTPS without embedded credentials;
- preserves plan/price/provider coherence;
- preserves fail-closed fallback with no provider selected;
- proves a synthetic non-Cakto checkout projection is accepted.

Code HEAD `878983f3289f75eee2901121f30f7eb3a240e58c` passed:

- Site Validation #529 / run `36359210226`: SUCCESS;
- Cloudflare Worker Validation #103 / run `36359210235`: SUCCESS.

A later documentation commit requires the two workflows to pass again on the exact final PR HEAD.

## CL-11 status

PR #65 — `CL-11 — post-purchase provisioning bridge design` remains OPEN/DRAFT and unmerged.

The Cakto-specific acquisition/callback design in PR #65 was created before the provider-independence reconciliation and is therefore **SUPERSEDED AS AN IMPLEMENTATION BASIS**.

No CL-11 production code was implemented.

After CL-10R and the Site correction are integrated, CL-11 must be re-derived from the provider-neutral architecture:

`validated external commercial event -> canonical billing/entitlement -> CommercialCustomerProvisioningService -> organization + OWNER + activation`

Provider-specific webhook/callback details belong to each external adapter and must not become canonical acquisition authority.

## Commercial readiness classification

### A — Functional readiness

Strong internal foundation. CL-10R must complete final exact-HEAD CI and controlled integration before the public commercial path is considered architecture-reconciled.

### B — Commercial surface parity

The current mains still contain the Cakto-specific CL-10/Site PR #21 projection until the corrective PRs are promoted.

The corrective branches restore provider-neutral parity without duplicating pricing or release authority.

### C — Production technical readiness

Internal contracts exist for secrets, staging/deploy, observability, backup/recovery and provider-neutral fiscal runtime. Real external infrastructure is still not evidenced.

### D — Operational readiness

Internal runbooks, CI/security gates and backup/restore evidence exist. Real production monitoring endpoints, credentials, deployment driver and cutover evidence remain external.

### E — Commercial readiness

**NOT COMMERCIAL LIVE.**

## Remaining external/human dependencies after internal provider-independence closure

Depending on the selected launch channels/providers:

- approved real plans/prices/promotions;
- selected commercial checkout/sales provider account(s), if used;
- real product/offer identifiers or equivalent provider configuration;
- provider API/webhook credentials in approved Secret Manager/Vault;
- public HTTPS callbacks where required;
- controlled authenticated event delivery and reconciliation;
- real password-reset email/SMS provider and credentials;
- real staging/production hosting, PostgreSQL, ingress and HTTPS;
- real fiscal certificates/CSC/provider credentials;
- exact launch fiscal cells by document × operation × jurisdiction × provider;
- official homologation evidence for every sold fiscal cell;
- controlled fiscal pilot;
- legal/LGPD operational review where required;
- explicit human Go/No-Go / `PRODUCTION_APPROVED`;
- authorized deploy, DNS/cutover and production smoke.

No external provider is mandatory by architecture. A provider becomes a dependency only when selected for a concrete launch channel/capability.

## Repository visibility

NFCore and Site FM remain intentionally **PUBLIC temporarily** because private GitHub Actions quota previously blocked CI.

While public:

- no real secrets, certificates, CSC, passwords, provider tokens, cloud credentials or webhook secrets may enter source/history;
- provider IDs in fixtures remain synthetic;
- secret/dependency/vulnerability scanning remains mandatory;
- repositories must return to PRIVATE when the heavy internal CI cycle is complete and the operator authorizes the visibility change.

## Next execution order

1. Certify exact final HEAD of NFCore PR #66.
2. Certify exact final HEAD of Site PR #22.
3. Promote the corrective PRs only under the applicable merge authorization.
4. Close/supersede the old CL-11 design PR #65.
5. Re-audit the integrated mains for provider independence.
6. Redesign CL-11 as provider-neutral post-purchase provisioning orchestration.
7. Close remaining internally solvable commercial/onboarding/recovery gaps.
8. Configure selected external launch channel(s), staging, Secret Manager/Vault and communication provider.
9. Execute fiscal homologation matrix and controlled pilot with real evidence.
10. Final production readiness audit -> human Go/No-Go -> authorized cutover.

No later block may convert `BLOCKED_EXTERNAL` into READY without reproducible external evidence.
