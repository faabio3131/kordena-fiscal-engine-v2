# CL-11 — Post-Purchase Provisioning Bridge — System Design Candidate

**Status:** DESIGN CANDIDATE / HUMAN ARCHITECTURAL APPROVAL REQUIRED — no production code started
**Date:** 2026-09-27
**Repository:** `faabio3131/kordena-fiscal-engine-v2`
**Baseline main:** `08294a0d86ee865bd5aa6eb9868885ae121d55c1`

## 1. Reason for this block

CL-05, CL-06 and CL-10 are individually implemented and certified, but the CURRENT runtime does not yet prove one continuous customer journey from a paid Cakto order to the canonical NFCore organization and first human OWNER.

CURRENT facts:

- `CaktoCommercialProcessor` consumes approved commercial events, derives a commercial tenant from Cakto `customer.id` and activates entitlements.
- `CommercialCustomerProvisioningService` independently creates the canonical Control Plane organization, first OWNER account and activation password-reset grant.
- The Cakto processor does not call `CommercialCustomerProvisioningService`.
- The trusted provisioning service requires `tenant_id`, `legal_name`, `owner_email`, correlation and time.
- The Cakto inbox currently persists `external_customer_id`, but not an approved canonical business identity or acquisition correlation.
- Therefore a green Cakto payment does not yet prove automatic first-user provisioning.

This is an INTERNAL integration gap. Real Cakto credentials and a real event are still external certification dependencies, but the software bridge can and should be designed and tested before those credentials exist.

## 2. External contract evidence revalidated

Official Cakto documentation current on 2026-09-27 states:

- order webhooks, including `purchase_approved`, contain a top-level `customer` object with `id`, `name`, `email` and other customer fields;
- Cakto recommends acknowledging the webhook quickly and doing heavier processing asynchronously;
- checkout links may carry an opaque `callback` value;
- that same callback is returned in the order webhook and may also be used in the post-payment redirect;
- Cakto explicitly instructs integrations not to place PII in the callback;
- the callback is owned/interpreted by the merchant system;
- Cakto also exposes an authenticated customer lookup endpoint.

References:
- https://docs.cakto.com.br/conceitos/webhooks
- https://docs.cakto.com.br/conceitos/redirect-pos-pagamento
- https://docs.cakto.com.br/api-reference/customers/retrieve

These contracts support correlation, but they do not make Cakto the canonical authority for NFCore organization identity.

## 3. Architectural problem

Using `customer.name` from a payment webhook as NFCore `legal_name` would silently infer a business/legal identity from the buyer identity. That is not acceptable for a fiscal SaaS.

Persisting raw webhook PII in the durable Cakto inbox would also create unnecessary duplication of customer data.

Calling customer lookup from every worker attempt would add an external availability dependency to identity provisioning and would still not provide a trustworthy company legal name.

Therefore CL-11 must correlate a purchase to business onboarding data supplied to NFCore before checkout, without granting the browser tenant authority.

## 4. TARGET candidate

Introduce a narrow **Commercial Acquisition Intent** as transient pre-checkout orchestration state.

It is NOT:

- a second customer/CRM authority;
- a second tenant authority;
- a second billing authority;
- a second Cakto binding store;
- a fiscal-production authority.

It exists only to correlate a canonical commercial offer selection and buyer-provided onboarding identity with the later authenticated Cakto payment event.

Target flow:

```text
Site FM
  -> same-origin Site BFF
  -> NFCore POST commercial acquisition
       - validate current canonical offer
       - validate exact plan/price pair
       - require purchase_enabled=true
       - accept onboarding identity claims only:
           legal_name
           owner_email
       - server generates opaque callback token
       - persist acquisition intent with bounded TTL
       - return canonical Cakto checkout URL + ?callback=<opaque>

Browser
  -> Cakto checkout

Cakto
  -> authenticated purchase_approved webhook
       - durable sanitized inbox
       - persist callback digest, not raw customer PII
       - persist buyer-email digest only if required for mismatch detection
  -> async commercial worker
       - resolve existing Cakto plan binding
       - resolve acquisition by callback digest
       - verify acquisition is pending/not expired
       - verify exact plan/price/provider correlation
       - verify webhook buyer email matches acquisition owner email by digest
       - preserve current commercial tenant/entitlement semantics
       - call canonical CommercialCustomerProvisioningService
       - create/reuse Control Plane organization + first OWNER idempotently
       - record acquisition outcome
       - schedule/deliver activation through the existing password-recovery delivery boundary

Owner
  -> activation/recovery
  -> first login
  -> canonical self-service unit onboarding
  -> portal
```

## 5. Authority map

### NFCore pricing authority
Existing Pricing Governance / durable pricing catalog.

### Commercial release authority
Existing CL-09 `CommercialReleaseAdministrationService`.

### Checkout mapping authority
Existing CL-10 `CaktoCheckoutAdministrationService` + durable `CaktoPlanBinding`.

### Payment/event authority
Authenticated Cakto webhook + durable Cakto inbox.

### Commercial entitlement authority
Existing Cakto commercial tenant/entitlement store.

### Organization and tenant authority
Existing Control Plane organization.

### Human identity authority
Existing human account repository / `HumanIdentityService`.

### Password recovery authority
Existing `PasswordRecoveryService` and `PasswordResetDelivery` port.

### Commercial Acquisition Intent
New transient orchestration record only. It cannot independently authorize billing, tenant access, fiscal production, pricing, plan or entitlement.

## 6. Data minimization

The Cakto inbox must remain sanitized.

Do not persist:

- Cakto webhook raw body;
- customer name;
- customer email in clear;
- phone;
- CPF/CNPJ;
- address;
- card data;
- webhook secret.

Permitted additions to the inbox, if required by implementation:

- `callback_sha256`;
- `customer_email_sha256`.

The acquisition intent may contain the minimum onboarding PII explicitly supplied for the NFCore account journey:

- normalized `owner_email`;
- `legal_name`.

Rules:

- never log these values;
- bounded TTL while pending;
- after successful provisioning, retain only the minimum audit reference necessary and purge or redact transient PII under the approved retention policy;
- do not use acquisition data as fiscal taxpayer authority.

## 7. Callback rules

The callback must be:

- generated server-side;
- cryptographically random;
- opaque;
- free of PII;
- bounded in length and charset compatible with Cakto;
- stored as a digest when used as a lookup credential;
- single-purpose and bounded by acquisition TTL;
- never accepted as proof of payment.

Only the authenticated `purchase_approved` event confirms payment. Browser redirect is UX only.

## 8. Public acquisition API candidate

Candidate endpoint:

`POST /v1/commercial/acquisitions`

Request candidate:

```json
{
  "plan_id": "canonical-plan",
  "price_id": "canonical-price",
  "legal_name": "Empresa Exemplo Ltda",
  "owner_email": "owner@example.com"
}
```

The client MUST NOT supply:

- tenant_id;
- entitlement_ids;
- provider IDs;
- external product/offer IDs;
- price amount;
- purchase_enabled;
- commercial approval;
- fiscal environment/authority.

The service resolves all authoritative commercial data from current NFCore state.

Response candidate:

```json
{
  "acquisition_id": "opaque-public-reference",
  "checkout_url": "https://pay.cakto.com.br/<offer>?callback=<opaque>"
}
```

No secret or fiscal authority is returned.

## 9. Fail-closed conditions

Checkout initiation must fail closed when:

- commercial release is not approved;
- pricing is not published;
- exact plan/price is absent or disabled;
- checkout mapping is partial/unconfigured;
- processing readiness required by policy is not configured;
- Cakto URL/provider binding is inconsistent;
- acquisition identity input is invalid;
- persistence fails.

Provisioning must fail/retry or enter governed dead-letter when:

- callback is missing or unknown for a site-originated purchase;
- acquisition expired;
- plan/price/provider mismatch;
- buyer email digest mismatch;
- owner email collides cross-tenant;
- organization identity conflicts;
- provisioning dependency fails;
- activation delivery fails.

No failure may create fiscal `PRODUCTION_APPROVED`.

## 10. Idempotency and replay

Required invariants:

1. one acquisition callback identifies at most one acquisition intent;
2. one Cakto order/event remains deduplicated by existing event identity;
3. repeated webhook delivery cannot create a second organization or OWNER;
4. repeated worker processing cannot duplicate entitlement;
5. provisioning correlation must be deterministic;
6. stale subscription events cannot recreate or overwrite onboarding identity;
7. refund/chargeback/cancel continue to affect commercial entitlement only and never delete fiscal history.

## 11. Persistence / migration impact

CURRENT Cakto schema is version 1 and the initializer is append-once by schema version.

CL-11 implementation must not mutate the meaning of schema version 1 silently.

If inbox correlation columns and/or acquisition persistence are added:

- introduce an explicit forward schema version / migration step;
- prove fresh install and upgrade from CL-10 schema;
- preserve existing inbox, bindings, commercial tenants and entitlements;
- prove migration idempotency;
- test SQLite and PostgreSQL paths used by CI/runtime;
- do not rewrite historical schema evidence.

## 12. Activation-delivery requirement

A payment must not be considered a completed onboarding journey merely because organization/account rows exist.

CL-11 must define retry-safe activation delivery using the existing password-recovery authority.

The implementation gate must prove:

- raw activation token never enters logs/inbox/audit;
- failed delivery cannot expose account existence publicly;
- retry can safely issue/deliver a usable activation path;
- successful activation is one-time;
- password change revokes prior sessions;
- no customer requires manual database editing.

Real email/SMS delivery remains `BLOCKED_EXTERNAL` until a provider and credentials are selected and tested.

## 13. Site impact

The current Site FM CTA links directly to the canonical Cakto URL only when NFCore returns `purchase_enabled=true`.

Under CL-11 target, the site should not construct callback tokens itself.

Instead, the purchase action becomes a same-origin initiation flow that asks only for the minimum onboarding identity, calls the NFCore acquisition endpoint through the existing BFF and redirects to the URL returned by NFCore.

The Site remains presentation/BFF, never commercial authority.

## 14. Acceptance gates for implementation

Before CL-11 can be certified:

- design/ADR approved;
- acquisition authority and retention policy fixed;
- no second customer/tenant authority;
- Cakto callback parser covered;
- sanitized inbox covered;
- schema forward migration covered fresh + upgrade;
- exact plan/price mapping enforced;
- callback/email mismatch fail-closed;
- purchase-approved -> entitlement -> organization -> OWNER journey tested;
- replay/idempotency tested;
- refund/chargeback regression tested;
- activation delivery retry semantics tested with fake provider;
- tenant isolation and cross-tenant collision tests;
- API/BFF tests;
- Ruff;
- Mypy;
- full Pytest;
- frontend lint/typecheck/tests/build;
- E2E;
- container/runtime gates;
- secret scan;
- dependency/vulnerability gates;
- PostgreSQL backup/restore;
- full CI green on exact PR HEAD.

## 15. Explicitly outside CL-11

- real Cakto account credentials;
- real product/offer IDs;
- real webhook secret;
- real public callback URL;
- Cakto post-payment redirect compliance approval;
- real email/SMS provider;
- deploy;
- DNS;
- production PostgreSQL provisioning;
- fiscal certificates/CSC/provider credentials;
- official fiscal homologation;
- fiscal pilot;
- `PRODUCTION_APPROVED`;
- Go-Live.

## 16. Decision gate

No implementation should begin until the architectural owner accepts or changes this TARGET.

The key decision is:

**Use an NFCore-owned transient acquisition intent plus opaque Cakto callback correlation, rather than inferring organization identity from Cakto buyer data or persisting raw webhook PII.**
