# CL-11 — Provider-Neutral Commercial Acquisition & Provisioning

**Status:** DESIGN CANDIDATE / HUMAN ARCHITECTURAL APPROVAL REQUIRED / NO PRODUCTION CODE  
**Date:** 2026-09-27  
**Repository baseline:** `faabio3131/kordena-fiscal-engine-v2` @ `19f1102d64a956de3eefa6cb2d6f2f0ddefb0f09`  
**Site baseline:** `faabio3131/fm-tecnologia-web-platform` @ `8e25261a74b8dd4d7b5f335de76366bd24920d45`

## 1. Objective

Close the remaining internal commercial-journey gap without coupling NFCore to Cakto, Hotmart, Kax, the FM Site or any other external sales channel.

The target journey is:

`validated external commercial event -> canonical commercial subscription/entitlement -> canonical organization -> first OWNER -> activation delivery -> login -> unit onboarding`

Provider-specific checkout, webhook, marketplace and reconciliation mechanics remain inside adapters.

## 2. CURRENT confirmed

The integrated CURRENT already provides:

- provider-neutral pricing through generic `external_price_reference`;
- provider-neutral checkout projection through `CommercialCheckoutProjector`;
- human Commercial Release Authority;
- generic commercial billing domain contracts in `product/billing.py`;
- provider-specific Cakto webhook/inbox/reconciliation implementation;
- trusted `CommercialCustomerProvisioningService` that idempotently creates the canonical Control Plane organization and first OWNER;
- password-recovery/activation authority and one-time reset semantics;
- authenticated portal/login/RBAC/tenant/unit onboarding;
- Site FM fail-closed commercial-offer projection.

CL-10R is merged. Cakto is an optional adapter and is no longer canonical checkout authority.

## 3. Internal blockers proven by CURRENT

### B1 — paid commercial event is not connected to canonical provisioning

The Cakto adapter can authenticate/process commercial events and update its provider-specific commercial state, while `CommercialCustomerProvisioningService` independently creates the canonical organization/OWNER.

There is no provider-neutral orchestration connecting a validated paid acquisition to that provisioning service.

### B2 — `purchase_enabled` does not prove post-purchase operability

CURRENT `GET /v1/commercial/offer` enables purchase from:

- human commercial approval;
- configured checkout projection;
- non-empty checkout items;
- provider processing configured.

It does not currently require:

- canonical post-purchase orchestration readiness;
- canonical durable subscription/entitlement readiness;
- OWNER provisioning readiness;
- activation-delivery readiness.

Therefore a provider could be configured and the public purchase CTA enabled before the customer can automatically receive a usable NFCore account.

### B3 — generic billing domain exists, but durable canonical runtime authority is incomplete

`CommercialPlan`, `CommercialSubscription`, quotas and subscription states exist as provider-neutral domain contracts.

CURRENT repository structure does not contain a provider-neutral durable subscription/entitlement persistence/runtime layer equivalent to the provider-specific Cakto commercial persistence. CL-11 must extend the existing generic billing model rather than make any provider-specific entitlement table the canonical authority.

### B4 — provider-local customer identity cannot become NFCore tenant identity

The Cakto adapter currently derives a provider-local commercial tenant reference from `external_customer_id`.

That reference may remain adapter-local for reconciliation, but it must never become the canonical NFCore organization/tenant identity. The same rule applies to every future provider.

## 4. Constitutional invariants

These invariants are frozen for CL-11 design review.

1. **No external provider owns NFCore identity.**
   - Cakto/Hotmart/Kax/customer IDs are provider-local references.
   - Canonical organization and tenant identity belong to NFCore Control Plane.

2. **No browser creates commercial or tenant authority.**
   - The browser may submit minimum acquisition/onboarding facts.
   - It cannot submit authoritative tenant IDs, entitlements, payment status, commercial approval or fiscal production state.

3. **Adapters validate and translate; they do not become the commercial Core.**
   - Signature/authentication, provider payload parsing, event deduplication and provider reconciliation stay in adapters.
   - Adapters emit a validated canonical commercial fact to the application layer.

4. **One canonical commercial subscription/entitlement authority.**
   - Provider-specific state may be retained for inbox/reconciliation/audit.
   - NFCore access decisions must depend on provider-neutral canonical commercial state.

5. **Payment does not grant fiscal production authority.**
   - No commercial event may create `PRODUCTION_APPROVED`, fiscal homologation, certificate authority or provider fiscal readiness.

6. **Provisioning is idempotent and fail-closed.**
   - Replay/retry cannot create duplicate organizations, OWNER accounts, subscriptions or entitlements.

7. **Activation is part of the commercial journey.**
   - A paid journey is not considered operationally complete if the OWNER cannot receive and use the activation path.

8. **Same application, configuration-driven providers.**
   - Adding a new provider protocol may require one reusable adapter.
   - Accounts, offers, product IDs, endpoints and secrets are configuration, not customer-specific forks.

## 5. Canonical target flow

```text
External sales channel
        |
        v
Provider-specific adapter
(authenticate / validate / deduplicate / map)
        |
        v
Validated Commercial Event
(provider-neutral application contract)
        |
        v
Commercial Acquisition Orchestrator
        |
        +--> Canonical pricing/plan validation
        |
        +--> Canonical durable subscription/entitlement
        |
        +--> Canonical customer identity resolution
        |
        +--> CommercialCustomerProvisioningService
        |       |
        |       +--> Control Plane organization
        |       +--> first OWNER
        |
        +--> activation delivery
        |
        v
Login -> tenant-scoped unit onboarding -> NFCore
```

Provider-specific event/state remains available for reconciliation but is not the canonical customer/billing authority.

## 6. Two acquisition modes that must be supported

### Mode A — acquisition initiated by an FM-controlled surface

Examples: FM Site or future first-party checkout.

Before redirecting to an external checkout, NFCore may receive the minimum customer facts required for later provisioning, such as:

- selected canonical plan/price;
- owner email;
- legal/organization name.

NFCore creates an internal acquisition reference. If a provider supports metadata/callback correlation, the adapter may attach an opaque, non-PII correlation value.

The correlation mechanism is provider-specific. The canonical acquisition identity is NFCore-owned.

### Mode B — acquisition initiated outside the FM Site

Examples: a marketplace or provider storefront where the buyer starts directly.

NFCore must not require every sale to pass through the FM Site.

After a validated paid event:

- if the provider supplies enough trustworthy identity to link an existing pending acquisition, NFCore may continue it;
- if required organization identity is incomplete, the acquisition enters a governed `IDENTITY_REQUIRED`/claim state;
- a secure activation/claim path collects the missing canonical organization facts before provisioning;
- provider display names must not be silently treated as company legal identity.

This preserves channel independence.

## 7. Candidate canonical acquisition lifecycle

The exact persistence schema requires implementation review, but the application lifecycle should preserve at least these semantic states:

- `PENDING_CHECKOUT` — optional for first-party initiated acquisitions;
- `PAYMENT_CONFIRMED`;
- `IDENTITY_REQUIRED` when canonical organization facts are incomplete;
- `READY_TO_PROVISION`;
- `PROVISIONED`;
- `ACTIVATION_PENDING`;
- `ACTIVE`;
- `CANCELED` / `REFUNDED` for commercial entitlement state;
- `MANUAL_REVIEW` for identity/conflict cases that cannot safely auto-resolve.

This state machine is a design candidate, not implementation evidence.

## 8. Canonical identity rule

The NFCore tenant/organization identifier must be generated from NFCore-owned identity state, not from a provider customer ID.

Permitted pattern:

`internal acquisition/customer identity -> canonical tenant_id`

Forbidden pattern:

`cakto_customer_id/hotmart_customer_id/kax_customer_id -> canonical tenant_id`

Provider customer IDs remain scoped mappings owned by the adapter/integration boundary.

## 9. Canonical commercial state

CL-11 must reuse `CommercialPlan`, `CommercialSubscription`, `SubscriptionStatus` and existing pricing/release authorities.

Required target:

- durable provider-neutral subscription/entitlement persistence;
- idempotent transition service;
- explicit provider event -> canonical subscription transition mapping;
- usage/quota authority remains provider-neutral;
- refund/chargeback/cancel affects commercial access according to canonical policy;
- existing fiscal history is preserved;
- no provider-specific table becomes the Core billing authority.

Existing Cakto commercial tables may remain for provider inbox, replay, reconciliation and external state evidence.

## 10. Purchase-readiness contract

After CL-11, `purchase_enabled` must remain false unless the end-to-end commercial path is operational.

Candidate required gates:

- commercial release = approved;
- pricing = published;
- selected checkout provider = configured;
- checkout projection = complete;
- provider event processing = configured;
- canonical commercial acquisition/subscription runtime = ready;
- commercial provisioning runtime = ready;
- activation delivery = configured and operationally eligible.

The exact readiness object/API shape is an implementation decision, but the fail-closed invariant is mandatory.

## 11. Activation and delivery

The existing password-recovery authority remains canonical.

Rules:

- raw activation/reset token is never logged or returned by the public reset-request endpoint;
- activation delivery is an injected external port;
- failed delivery does not reveal account existence;
- retry must not create duplicate OWNER accounts;
- activation remains one-time;
- successful password reset revokes previous sessions as already implemented;
- a real launch requires a configured delivery provider and evidence that delivery works.

No provider-specific checkout adapter may implement a second password or activation authority.

## 12. Data minimization

Provider adapters may persist the minimum external identifiers needed for:

- signature/replay validation;
- reconciliation;
- idempotency;
- external event audit.

Canonical acquisition/provisioning must not persist raw provider payloads unnecessarily.

Sensitive customer facts must:

- be minimized;
- never enter logs;
- use explicit retention rules;
- remain tenant-isolated;
- not become fiscal taxpayer truth merely because they came from a checkout provider.

Legal/LGPD validation remains a human/legal review dependency.

## 13. Failure and retry cases

CL-11 must test at least:

- duplicated paid event;
- out-of-order subscription event;
- unknown plan/price mapping;
- disabled provider mapping;
- payment event without enough identity;
- cross-provider customer collision;
- owner email already bound to another tenant;
- organization legal-name conflict;
- provisioning retry after partial failure;
- activation delivery failure and retry;
- refund/chargeback after provisioning;
- stale provider event;
- replay after canonical subscription already transitioned;
- provider-local tenant reference attempting to override canonical tenant identity.

Every unsafe ambiguity fails closed or moves to `MANUAL_REVIEW`; it never manufactures authority.

## 14. Site FM impact

The Site remains a consumer of NFCore commercial authority.

For first-party initiated purchase, the future Site flow may need a same-origin BFF that submits minimum acquisition facts to NFCore and receives the governed checkout result.

The Site must never:

- mint tenant IDs;
- decide that payment succeeded;
- assign entitlements;
- grant OWNER;
- store provider secrets;
- infer commercial approval;
- grant fiscal production authority.

Marketplace-originated sales must work without the Site.

## 15. Portal/admin UX

The existing provider-specific `Checkout Cakto` surface is acceptable only as an adapter administration surface and is shown only when that adapter is composed.

Future UX should present the capability as a provider-neutral commercial integration area, for example:

`Canais de Venda / Checkout -> configured provider adapters`

This is a UI/admin refinement, not a reason to rebuild the portal.

## 16. Branding finding kept outside CL-11 functional scope

The Site FM currently uses newer approved NFCore image assets while the NFCore portal/login still uses `portal/assets/fm-nfcore-mark.svg`, and the Brand Kit still declares that SVG canonical.

This is a confirmed visual/documentation drift to be reconciled on the same application, but it is not part of CL-11 commercial-domain implementation.

## 17. CI/governance finding kept outside CL-11 functional scope

Site FM PR gates are green, but CURRENT Site workflows do not run on `push: main`.

A separate small governance correction should add main-push validation so future merge commits receive direct post-merge evidence.

This is not a reason to change NFCore commercial-domain contracts.

## 18. CL-11 implementation impact map

Expected areas after human approval:

- product/application commercial acquisition contracts;
- durable provider-neutral subscription/acquisition persistence;
- explicit forward migrations;
- runtime composition;
- commercial readiness projection;
- adapter -> canonical event bridge;
- `CommercialCustomerProvisioningService` integration;
- activation delivery readiness/retry;
- Site BFF/UX for first-party initiated purchase;
- E2E tests and observability;
- documentation/runbooks.

Protected authorities that must not be replaced:

- Control Plane tenant/unit authority;
- human identity/session/RBAC;
- pricing administration;
- Commercial Release Authority;
- fiscal provider/configuration authority;
- password recovery;
- existing provider adapter security boundaries.

## 19. Acceptance gates

Before CL-11 can be certified internally:

1. approved architecture/ADR;
2. canonical acquisition identity is provider-independent;
3. durable generic subscription/acquisition migrations pass fresh + upgrade tests;
4. provider event replay cannot duplicate subscription, org or OWNER;
5. at least one provider adapter proves validated event -> canonical transition without becoming authority;
6. first-party initiated acquisition E2E passes;
7. marketplace-originated/identity-required flow is covered by deterministic tests;
8. purchase remains fail-closed when provisioning or activation delivery is unavailable;
9. refund/cancel preserves fiscal history and affects only commercial access;
10. cross-tenant/cross-provider identity collisions fail closed;
11. Ruff, Mypy, full Pytest;
12. frontend lint/typecheck/tests/build where affected;
13. critical E2E;
14. secret/dependency/container/vulnerability/SBOM gates;
15. PostgreSQL migration, backup/restore and restored-DB readiness;
16. exact-head remote CI success.

## 20. Explicitly outside CL-11

CL-11 does not authorize or fabricate:

- real Cakto/Hotmart/Kax accounts or credentials;
- real product/offer configuration;
- production email/SMS credentials;
- deploy, DNS or TLS;
- staging/production infrastructure;
- real fiscal certificates/CSC/provider credentials;
- fiscal homologation;
- controlled fiscal pilot;
- `PRODUCTION_APPROVED`;
- Go-Live.

## 21. Human decision required

Before implementation begins, approve or change this architectural decision:

> NFCore owns the canonical commercial acquisition, subscription/entitlement and organization identity. External sales providers remain authenticated adapters that translate external events into canonical NFCore commercial facts. A paid event cannot expose a usable purchase path unless provisioning and activation are operationally ready.

Until that decision is approved, this document is a design candidate and CL-11 production implementation must not start.
