# FM NFCORE V1 — Commercial Launch CURRENT

**Canonical status date:** 2026-10-05  
**Canonical NFCore repository:** `faabio3131/kordena-fiscal-engine-v2`  
**Audited base NFCore main:** `9a42045c9690c32dcaf2cf11ead1a0b38843c779`  
**Canonical FM commercial-site repository:** `faabio3131/fm-tecnologia-web-platform`  
**Canonical Site main:** `26bfe05c2891bfc68f680587d0ae47ee36f105b1`

This file is the persistent CURRENT checkpoint for FM NFCORE V1 Commercial Launch. GitHub remains the first technical source of truth and must be revalidated on every resume.


## 0AA. CURRENT authoritative checkpoint — 2026-10-05 — POST-GOVERNANCE BOOTSTRAP

This subsection is the authoritative persisted checkpoint for the 2026-10-05 execution baseline. GitHub and Railway were re-audited read-only immediately before task `NFV1-P00-T01` started. Older sections below remain historical evidence only when they conflict with this checkpoint.

### GitHub CURRENT

- canonical repository: `faabio3131/kordena-fiscal-engine-v2`;
- audited pre-task main: `9a42045c9690c32dcaf2cf11ead1a0b38843c779`;
- certified post-merge main for `NFV1-P00-T01`: `824842f2ed5586351a75cd57fc765c716899bb9e`;
- certified post-merge main for `NFV1-P00-T02`: `09dd77798122202ba1b7e548818b879556bec0ae`;
- certified post-merge main for `NFV1-P00-T03`: `3837d1e6b5a3c38e3aa2ceb032fb952fab700a4c`;
- PR #100: **MERGED** into main;
- latest main technical CI for the P0 closeout baseline: **FM NFCORE V1 CI #597 — SUCCESS** on `3837d1e6b5a3c38e3aa2ceb032fb952fab700a4c`;
- latest main plan-governance CI for the P0 closeout baseline: **NFCore Plan Governance #26 — SUCCESS** on the same exact SHA;
- open PRs at the start of `NFV1-P00-T01`: **0**;
- repository visibility: **PUBLIC**.

The governance bootstrap is therefore integrated into main. It contains the canonical completion schedule, the execution ledger, AGENTS rules, PR template and machine validator.

### Canonical execution control

The active execution authorities are:

- `docs/NFCORE_V1_COMPLETION_MASTER_EXECUTION_SCHEDULE_2026-10-05.md`;
- `docs/NFCORE_V1_EXECUTION_LEDGER.md`;
- `docs/standards/FM_AI_MASTER_PLAN_EXECUTION_STANDARD.md`;
- `AGENTS.md`.

The schedule contains phases P0-P12 and 59 task IDs `NFV1-Pxx-Tyy`. The ledger is the state/proof record. Git/GitHub, CI and runtime remain superior to documentation for determining technical CURRENT.

Execution state at the start of this checkpoint:

- P0: **DONE_CERTIFIED**;
- gate de saída: **CURRENT_RECONCILED_2026_10_05**;
- `NFV1-P00-T01 — Reconciliar documentação CURRENT`: **DONE_CERTIFIED**;
- `NFV1-P00-T02 — Congelar matriz de capacidades`: **DONE_CERTIFIED**;
- `NFV1-P00-T03 — Registrar staging drift`: **DONE_CERTIFIED**;
- P1: **IN_PROGRESS**;
- `NFV1-P01-T01 — Identificar composição canônica`: **IN_PROGRESS**;
- next task remains blocked until T01 closeout: `NFV1-P01-T02 — Implementar composition root`;
- all later tasks remain not started unless separately evidenced by historical implementation; historical implementation does not mark a task complete in the new ledger.

### P1 canonical fiscal composition — T01 snapshot

The canonical composition decision for P1 is persisted in:

- `docs/NFCORE_V1_P01_CANONICAL_FISCAL_COMPOSITION_2026-10-05.md`;
- `docs/checkpoints/NFV1_P01_T01_CANONICAL_COMPOSITION_2026-10-05.md`.

Binding decisions:

- canonical runtime entrypoint remains `runtime.api:create_runtime_app`;
- canonical durable composition remains `build_postgres_runtime_composition` / `RuntimeComposition`;
- Bridge and Portal are ingress adapters only and must delegate to one fiscal application execution path;
- S2S reuses `WorkloadAuthenticator + S2SAuthorizer`;
- Portal reuses existing session/RBAC/CSRF authority;
- provider/readiness/signing/vault/production authority reuse their existing certified boundaries;
- no concrete production `BridgeRequestExecutor` / `PortalOperationExecutor` is present yet;
- no real `FiscalProviderTransport` or concrete `ExternalSecretClient` is certified in CURRENT;
- P01-T02 must implement composition without enabling fiscal production automatically.

### Railway staging drift register — T03 snapshot

Authoritative drift evidence for this task is persisted in:

- `docs/NFCORE_V1_STAGING_DRIFT_2026-10-05.md`;
- `docs/checkpoints/NFV1_P00_T03_STAGING_DRIFT_2026-10-05.md`.

Current exact comparison:

- main: `eccb40058992023514eeaac5ecfecb7e551df763`;
- API: `f9b5b2c5b436045947159f1e76be9303f5a95d90` — 36 commits behind;
- Portal: `f9b5b2c5b436045947159f1e76be9303f5a95d90` — 36 commits behind;
- Worker: `1c34ba001935952f83ec0b065144e0b8311a5650` — 118 commits behind and 0/1 running;
- Postgres: PostgreSQL 18, 5000 MB persistent volume, migrations 1–12 with `cakto_schema=2`;
- all service `stagedChangeCount` values are 0; Railway `pendingWork` still exposes one empty `EnvironmentPatch` record with `changes=[]`, so there is no substantive staged configuration change to apply;
- tracing Railway remains disabled;
- no custom domains exist for API/Portal.

This records drift only. It does not authorize reconciliation deploy.

### Railway staging CURRENT — read-only verification

Project: `FM NFCORE Staging`.

The Railway environment is named `production`, but this is only the environment label inside the staging project and does **not** mean NFCore production is approved.

Verified live services:

- PostgreSQL: online, 1/1 replica, persistent volume present;
- `nfcore-api`: online, 1/1 replica, latest deployed commit `f9b5b2c5b436045947159f1e76be9303f5a95d90`;
- `nfcore-portal`: online, 1/1 replica, latest deployed commit `f9b5b2c5b436045947159f1e76be9303f5a95d90`;
- `nfcore-worker`: Railway service state online, latest deployed commit `1c34ba001935952f83ec0b065144e0b8311a5650`, but replica status is **0 running / 1 total**.

Version drift therefore remains between audited main and staging.

Additional verified runtime facts:

- Railway tracing is disabled for PostgreSQL, API, Portal and Worker;
- API and Portal use Railway service domains only; no custom domain is present;
- one Railway environment patch is reported as staged with an empty `changes` list;
- no active Railway warning or critical notification was reported in the 24-hour environment health read.

Detailed drift registration and closure belong to `NFV1-P00-T03` / P5 as defined by the schedule. This task records the observed CURRENT but does not claim those later tasks complete.

### Confirmed completion gaps carried into the schedule

The 2026-10-05 audit remains authoritative for the following gaps:

1. fiscal Bridge security/execution and Portal operation executors are not composed in the canonical runtime app;
2. Portal durable surfaces expose only a subset of the functionality represented in the frontend;
3. acquisition, trial and provider webhook ingress are implemented but not wired into the canonical runtime app;
4. continuous Worker execution lacks the explicit real handler composition required by the entrypoint;
5. a real fiscal transport provider and a concrete external Secret Manager adapter are not certified;
6. operational tracing/exporters are not active in Railway;
7. official fiscal homologation, controlled pilot, production infrastructure and commercial Go-Live remain unproven.

### Classification

- functional/domain foundation: strong but not end-to-end integrated;
- staging: **REAL / VERSION_DRIFT_PRESENT / NOT_CERTIFIED_AGAINST_CURRENT**;
- production: **NOT PROVEN / NOT APPROVED**;
- commercial status: **NO-GO**;
- `PRODUCTION_APPROVED`: **NO**;
- `COMMERCIAL_LIVE`: **NO**.



## 0A. CURRENT override — 2026-10-01

This subsection is authoritative over older Railway/status wording below. GitHub and Railway were re-audited read-only.

### GitHub

- NFCore main: `f2fd8a875bdf8ae5327d7f716209603f60d34570`;
- latest main CI: **FM NFCORE V1 CI #519 — SUCCESS**;
- repository remains **PUBLIC**;
- Site FM main: `26bfe05c2891bfc68f680587d0ae47ee36f105b1`;
- Site Validation #553 and Cloudflare Worker Validation #127: **SUCCESS**.

### Railway real state

The dedicated project `FM NFCORE Staging` now exists. Its Railway default environment is labeled
`production`; this label is inside the staging project and does **not** mean NFCore production is
approved.

Services:

- `nfcore-api`: **SUCCESS** on older SHA `11cec7991c5345e03ef54e58b1fa6b5fbcd51801`;
- `nfcore-worker`: **CRASHED** on the same older SHA;
- `nfcore-portal`: **SUCCESS** on older SHA `5201eaa663b029d304a89131c28d501e444f730d`.

The worker fails closed with `durable worker runtime requires PostgreSQL persistence`.

There is currently:

- no PostgreSQL service;
- no configured runtime variables/secrets on API/worker/portal;
- no public Railway domain attached to API or portal;
- no deployment of current main `f2fd8a875bdf8ae5327d7f716209603f60d34570`;
- no certified rollback rehearsal;
- no real staging commercial E2E.

Therefore:

- CL-15 = **IN_PROGRESS / BLOCKED_EXTERNAL**;
- `STAGING_DEPLOYED_AND_E2E_VALIDATED=false`;
- CL-16 = **NOT_STARTED_OPERATIONALLY**;
- CL-17 = **NOT_STARTED_OPERATIONALLY**;
- CL-18 = **NOT_STARTED**;
- `PRODUCTION_APPROVED=NO`.

### Activation delivery boundary

The existing API already exposes the injected provider-neutral `PasswordResetDelivery` port.
`SecureActivationEmailDelivery` is compatible with this contract. No new Core authority or
provider-specific domain code is required before choosing/configuring a real outbound delivery
provider.

See `docs/NFCORE_CL15_STAGING_CURRENT_AUDIT_2026-10-01.md`.

---

## 0. CURRENT reconciliation — 2026-09-30

This section is authoritative over stale status language below while preserving historical audit
records. GitHub CURRENT must be revalidated on every resume.

### Canonical phase state

- CL-12: `IMPLEMENTED / TESTED / MERGED / CERTIFIED`;
- CL-13: `IMPLEMENTED / TESTED / MERGED / CERTIFIED`;
- CL-14: `IMPLEMENTED / TESTED / MERGED / CERTIFIED`;
- CL-15: `IN_PROGRESS / BLOCKED_EXTERNAL`;
- CL-16: `NOT_STARTED_OPERATIONALLY`; internal harness only: `PREPARED_NOT_ACTIVE`;
- CL-17: `NOT_STARTED_OPERATIONALLY`; reusable historical authorities do not count as execution;
- CL-18: `NOT_STARTED`;
- `PRODUCTION_APPROVED`: **NO**;
- NFCore -> Kordena cutover: **NOT AUTHORIZED**.

### Railway capacity update — 2026-09-30

Railway Hobby capacity is now sufficient to create the dedicated NFCore project and the
secretless API/worker/portal service scaffold. The previous free-plan resource-limit blocker
is resolved.

The repository remains public by deliberate CI-continuity decision. No real database or
runtime/provider/fiscal secret is introduced while that public-repository guard remains in
force. The new truthful state is:

`RAILWAY_CAPACITY_RESOLVED / SECRETLESS_SCAFFOLD_PREPARED / REAL_STAGING_SECRET_BOUNDARY_DEFERRED`

This does not satisfy `STAGING_DEPLOYED_AND_E2E_VALIDATED`.

### CL-15 exact truth

Railway staging-provider contract preparation exists, but the dedicated NFCore staging project was
not provisioned because Railway rejected the creation attempt with a free-plan resource-limit
blocker. No real NFCore staging deploy, staging database, real provider secret, real activation
provider delivery, real staging E2E or rollback rehearsal is evidenced.

The activation-delivery adapter from PR #79 is implemented and unit-tested. It is not currently
imported, instantiated or exposed by the canonical `RuntimeComposition`. Therefore its correct
state is `IMPLEMENTED_AND_UNIT_TESTED`, not `INTEGRATED`.

The CL-15 gate `STAGING_DEPLOYED_AND_E2E_VALIDATED` remains **NOT MET**.

### CL-16 exact truth

PR #80 added a fail-closed internal validation/evidence harness. The harness requires the exact
CL-15 staging state before it can become ready for a real provider exercise. Its canonical state is
`INTERNAL_HARNESS_AVAILABLE / PREPARED_NOT_ACTIVE`.

This does not mean CL-16 started operationally and does not provide
`COMMERCIAL_CHANNEL_READY`.

### CL-17 / CL-18 boundary

Existing V2-15/POST-WEB-12 fiscal governance may be reused in the future to avoid duplicate
engineering. Reuse readiness is not phase execution. CL-17 remains
`NOT_STARTED_OPERATIONALLY` until predecessor gates and real official external prerequisites are
available. CL-18 remains `NOT_STARTED`.

No CI result, synthetic matrix, internal harness or documentation update is official
SEFAZ/prefeitura/provider homologation, a real controlled pilot or `PRODUCTION_APPROVED`.

### Cross-repository reconciliation

Site FM PR #24 is retained. It adds post-merge validation on `main` and updates the patched
`undici` dependency; its merge commit `26bfe05c2891bfc68f680587d0ae47ee36f105b1`
passed both Site Validation and Cloudflare Worker Validation.

Kordena is explicitly out of scope for writes in this reconciliation. Protected checkpoint:
`faabio3131/fm-ai-platform` / `staging/kordena-premium@57bbf18cacdc443d329308e6d9328c57aa55ed0a`.

See `docs/NFCORE_CONTEXT_INCIDENT_RECONCILIATION_2026-09-30.md`.

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
