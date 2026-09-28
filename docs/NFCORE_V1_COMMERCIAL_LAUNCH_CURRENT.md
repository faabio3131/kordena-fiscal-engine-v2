# FM NFCORE V1 — Commercial Launch CURRENT

**Canonical status date:** 2026-09-27  
**Canonical NFCore repository:** `faabio3131/kordena-fiscal-engine-v2`  
**Canonical NFCore main:** `19f1102d64a956de3eefa6cb2d6f2f0ddefb0f09`  
**Canonical FM commercial-site repository:** `faabio3131/fm-tecnologia-web-platform`  
**Canonical Site main:** `8e25261a74b8dd4d7b5f335de76366bd24920d45`

This file is the persistent CURRENT checkpoint for FM NFCORE V1 Commercial Launch. GitHub remains the first technical source of truth and must be revalidated on every resume.

## 1. Confirmed integration state

### NFCore

PR #66 — **CL-10R — restore commercial provider independence** — is **MERGED**.

- certified PR HEAD: `f792ef7ca12369d3444a6760c799c77477e6f653`;
- merge/main commit: `19f1102d64a956de3eefa6cb2d6f2f0ddefb0f09`;
- candidate `FM NFCORE V1 CI` #438: **SUCCESS**;
- post-merge `FM NFCORE V1 CI` #439: **SUCCESS** on exact main;
- compare certified HEAD -> merge commit: zero file changes.

CL-10R restored the canonical provider-neutral checkout/commercial contract without replacing billing, pricing, tenant, provisioning or fiscal authorities.

### Site FM

PR #22 — **NFCore — restore provider-neutral checkout contract** — is **MERGED**.

- certified PR HEAD: `124892f8af689c25dbcf280bdd4075adfa5bd9f2`;
- merge/main commit: `8e25261a74b8dd4d7b5f335de76366bd24920d45`;
- Site Validation #530: **SUCCESS** on certified PR HEAD;
- Cloudflare Worker Validation #104: **SUCCESS** on certified PR HEAD;
- compare certified HEAD -> merge commit: zero file changes.

CURRENT Site workflows do not trigger on `push: main`; therefore no post-merge Site workflow exists for this merge. This is a governance gap to correct separately, not evidence of a failed merge.

### Superseded CL-11

PR #65 — **SUPERSEDED — CL-11 post-purchase provisioning bridge design** — is **CLOSED / NOT MERGED**.

Its Cakto-specific acquisition/callback design must not be used as implementation authority.

No CL-11 production code from PR #65 entered `main`.

## 2. Architecture authority reconciled

FM architecture requires one evolving application line and keeps external providers behind infrastructure/adapters.

The canonical NFCore separation is:

`Domain/Core -> Application -> Infrastructure/Adapters -> External Systems`

Commercial authorities remain separate:

`Pricing != Checkout != Billing/Entitlement != Commercial Release != Fiscal Production Authority`

Supported customer/provider differences are configuration. A previously unsupported provider protocol may require one reusable adapter; account, offer, product, endpoint and secret differences do not justify customer-specific source forks.

## 3. Provider-neutral commercial CURRENT

The canonical checkout contract is `src/kordena_fiscal/product/checkout.py`:

- `CommercialCheckoutProjector`;
- `CommercialCheckoutProjection`;
- `CommercialCheckoutItem`;
- `CommercialCheckoutStatus`.

The canonical public commercial-offer path does not depend on Cakto types.

Cakto remains a provider-specific optional adapter. It may own:

- Cakto webhook authentication/parsing;
- provider-local product/offer bindings;
- provider-local inbox/retry/dead-letter/reconciliation;
- provider-local external customer references;
- provider-specific admin surface;
- provider-specific external-state evidence.

It must not own canonical NFCore organization identity, billing authority, tenant authority, login/RBAC or fiscal production authority.

## 4. Site FM commercial boundary

The Site consumes:

`Browser -> /api/nfcore/commercial-offer -> NFCORE_API_URL/v1/commercial/offer`

The Site contract:

- accepts a governed provider identifier;
- has no Cakto-only provider literal;
- has no Cakto-only checkout host requirement;
- validates checkout URLs as absolute HTTPS without embedded credentials;
- keeps `NFCORE_API_URL` server-side;
- fails closed when upstream state is absent/invalid;
- cannot create pricing, commercial approval, payment approval or fiscal authority.

## 5. Confirmed functional foundations

The integrated main contains:

- canonical auth/session/RBAC;
- tenant/unit authority and anti-spoofing boundaries;
- durable Control Plane and PostgreSQL;
- zero-code fiscal provider/configuration bindings;
- external secret boundaries;
- generic pricing with `external_price_reference`;
- human Commercial Release Authority;
- provider-neutral checkout projection;
- generic billing-domain contracts (`CommercialPlan`, `CommercialSubscription`, quotas/status);
- trusted `CommercialCustomerProvisioningService`;
- first OWNER provisioning;
- password recovery/one-time activation mechanics;
- authenticated portal;
- tenant-scoped basic unit onboarding;
- observability contracts;
- container/security/backup/restore CI gates;
- staging/production promotion contracts that remain fail-closed without external infrastructure.

## 6. New CURRENT blocker — CL-11

The remaining internally solvable commercial gap is now defined as:

**CL-11 — Provider-Neutral Commercial Acquisition & Provisioning**

Formal design candidate:

`docs/CL_11_PROVIDER_NEUTRAL_COMMERCIAL_ACQUISITION_PROVISIONING_DESIGN.md`

### B1 — validated payment is not connected to canonical provisioning

CURRENT has two independent capabilities:

```text
external provider event -> provider-specific commercial state
```

and

```text
CommercialCustomerProvisioningService
-> canonical organization
-> first OWNER
-> activation reset
```

There is no provider-neutral application orchestration joining those paths end-to-end.

### B2 — purchase can become enabled before the post-purchase journey is operational

CURRENT `purchase_enabled` checks:

- human commercial approval;
- configured checkout projection;
- checkout items;
- provider processing configured.

It does not yet require:

- canonical post-purchase orchestration readiness;
- durable provider-neutral subscription/entitlement readiness;
- provisioning readiness;
- activation-delivery readiness.

Until CL-11 closes this, real paid checkout must not be treated as commercially launch-ready.

### B3 — durable canonical billing/subscription runtime is incomplete

The provider-neutral billing domain exists, but CURRENT repository structure has no equivalent provider-neutral durable subscription/entitlement persistence/runtime authority.

Provider-specific Cakto commercial persistence therefore must not be promoted into canonical NFCore billing.

CL-11 must extend the existing generic billing model with durable provider-neutral application/persistence authority.

### B4 — provider-local customer identity must remain provider-local

Cakto currently has a provider-local commercial tenant/customer mapping derived from its external customer ID.

That identity may remain useful for adapter reconciliation, but it must never become the canonical NFCore tenant/organization identity.

The same invariant applies to every provider.

## 7. Frozen CL-11 invariants

Before implementation, CL-11 must preserve:

1. canonical organization/tenant identity is NFCore-owned;
2. external provider IDs are adapter-local references;
3. browser input is never payment, tenant, entitlement or fiscal authority;
4. adapters authenticate/validate/translate provider events;
5. one provider-neutral canonical subscription/entitlement authority governs NFCore commercial access;
6. existing provider state may remain for reconciliation/audit only;
7. provisioning is idempotent and retry-safe;
8. duplicate/replayed events cannot duplicate org, OWNER, subscription or entitlement;
9. payment never grants fiscal production authority;
10. activation delivery is part of paid-journey readiness;
11. first-party Site purchase and externally initiated marketplace purchase must both be supportable;
12. no sales channel becomes mandatory architecture.

## 8. CL-11 target

```text
Cakto / Hotmart / Kax / Site / Marketplace / Future channel
                           |
                           v
                 Provider-specific adapter
                           |
                           v
                Validated Commercial Event
                           |
                           v
             Commercial Acquisition Orchestrator
                           |
             +-------------+--------------+
             |                            |
             v                            v
 canonical subscription/entitlement   identity resolution
             |                            |
             +-------------+--------------+
                           |
                           v
          CommercialCustomerProvisioningService
                           |
                  organization + OWNER
                           |
                           v
                  activation delivery
                           |
                           v
                  login + onboarding
```

Provider-specific callback/metadata mechanics belong to adapters and are not canonical business authority.

## 9. Purchase-readiness target

After CL-11, public purchase must remain fail-closed unless the end-to-end journey is operational.

At minimum the readiness decision must account for:

- commercial approval;
- published pricing;
- configured checkout provider;
- complete checkout mapping;
- provider event processing;
- canonical acquisition/subscription runtime;
- trusted provisioning runtime;
- activation delivery readiness.

Exact API/data shape requires design approval and implementation review.

## 10. Trial status

`trial_enabled` remains explicitly **false** in CURRENT and is a separate authority.

Trial must not be inferred from `trial_days` in pricing.

No trial launch may be claimed until a governed trial acquisition/provisioning journey exists and is certified.

## 11. Portal/branding audit finding

CURRENT portal/login still uses:

`portal/assets/fm-nfcore-mark.svg`

while Site FM uses newer approved NFCore image assets.

The existing Brand Kit still declares the old SVG asset canonical.

This is a confirmed brand-documentation/UI drift.

Required treatment:

- reconcile the latest approved NFCore identity;
- update the canonical Brand Kit/assets;
- apply it to login, sidebar, favicon and portal on the same application;
- preserve auth/RBAC/tenant/API behavior;
- rerun visual/accessibility gates.

This is not part of CL-11 domain implementation and must not cause a frontend rebuild.

## 12. Portal checkout-admin finding

The portal contains a provider-specific `Checkout Cakto` administration surface.

CURRENT backend only adds that surface for a platform admin when the Cakto administration adapter is composed. Therefore it is not a universal customer authority.

Future UX should organize provider-specific configuration under a neutral capability such as:

`Canais de Venda / Checkout -> provider adapters`

This is a UI/admin refinement, not a blocker to CL-11 domain design.

## 13. Site CI governance finding

CURRENT Site workflows run on pull requests, but their `push` branch filters do not include `main`.

Required separate correction:

- add `main` to Site Validation push trigger;
- add `main` to Cloudflare Worker Validation push trigger;
- preserve the existing PR gates.

The already merged PR #22 remains evidenced by green exact PR HEAD plus zero-file-diff to merge commit.

## 14. Staging and production CURRENT

NFCore contains governed workflows for staging and production promotion.

CURRENT facts:

- staging workflow is manual;
- real deployment requires external HTTPS URL, PostgreSQL, deploy driver, IAM and external secret backend;
- default provider driver is unconfigured/fail-closed;
- no real staging deployment evidence exists;
- no production promotion evidence exists;
- production requires explicit `PRODUCTION_APPROVED`;
- fiscal Go-Live remains separate from software deployment.

Therefore:

`STAGING_READY_FOR_PROVISIONING / BLOCKED_EXTERNAL`

is the maximum valid staging classification.

## 15. Commercial readiness classification

### A — Functional readiness

Strong internal fiscal/web/auth/configuration foundation. Paid acquisition is internally incomplete until CL-11.

### B — Commercial parity

Provider-neutral Site/checkout contract is integrated. Paid post-purchase provisioning and trial remain incomplete.

### C — Production technical readiness

Internal deployment/security/recovery contracts exist. Real staging/production infrastructure is not evidenced.

### D — Operational readiness

Internal observability/runbook/backup contracts exist. Real external monitoring, infrastructure credentials and cutover evidence remain absent.

### E — Commercial readiness

**NOT COMMERCIAL LIVE.**

A customer must not be charged through a real public path before CL-11 proves that the paid acquisition can reach a usable activated NFCore account.

## 16. External/human dependencies after CL-11 internal closure

Depending on selected launch channels:

- approved real prices/plans/promotions;
- selected commercial provider account(s);
- product/offer IDs and provider configuration;
- provider API/webhook secrets in approved Secret Manager/Vault;
- public HTTPS callbacks where required;
- real activation email/SMS provider and credentials;
- staging/production hosting, PostgreSQL, ingress and TLS;
- fiscal certificates/CSC/provider credentials;
- exact launch fiscal cells;
- official homologation evidence;
- controlled fiscal pilot;
- legal/LGPD operational review;
- final human Go/No-Go / `PRODUCTION_APPROVED`;
- authorized deploy/DNS/cutover/smoke.

No external commercial provider is mandatory by architecture.

## 17. Repository visibility

NFCore and Site FM remain **PUBLIC temporarily** due the previous private GitHub Actions quota constraint.

Until returned to PRIVATE:

- never commit real secrets, certificates, CSC, passwords, provider tokens or cloud credentials;
- keep secret/dependency/vulnerability scanning mandatory;
- use only synthetic provider IDs in tests.

Return to PRIVATE before introducing real production credentials/configuration into connected infrastructure.

## 18. Next execution order

1. review/approve or amend the CL-11 provider-neutral design;
2. only after human architectural approval, implement CL-11 on a dedicated implementation branch;
3. add durable provider-neutral acquisition/subscription persistence and migrations;
4. connect at least one authenticated adapter event to the canonical commercial orchestrator;
5. integrate canonical provisioning + OWNER + activation delivery readiness;
6. update Site first-party purchase flow without making Site mandatory for marketplace sales;
7. prove end-to-end paid acquisition/replay/refund/identity-failure cases;
8. correct Site `push: main` CI governance;
9. reconcile the approved NFCore brand assets on the existing portal;
10. re-audit all internally solvable gaps;
11. only then provision external staging/providers/secrets/activation delivery;
12. execute fiscal homologation/pilot;
13. final production-readiness audit -> human Go/No-Go -> authorized cutover.

No later block may convert `BLOCKED_EXTERNAL` into READY without reproducible external evidence.
