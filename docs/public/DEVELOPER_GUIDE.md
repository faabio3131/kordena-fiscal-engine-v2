# FM Fiscal — Developer Guide

## 1. Integration model

A product remains authority for its own customers, payments and business operations. FM Fiscal is
the fiscal authority. Integrations cross the FM Fiscal Bridge using versioned public contracts;
consumer applications must not import private fiscal persistence or provider internals.

## 2. Authentication

Use the workload identity assigned to the caller and its governed host binding. The public Bridge
requires the caller to present its workload credential identifier and bearer secret through the
configured transport. Do not encode tenant, unit or host authority solely from arbitrary request
headers: those scope claims must match the authenticated identity and Fiscal Account Binding.

Never log bearer material, certificates, CSC values or provider credentials.

## 3. Required scope and trace headers

A normal request carries:

- `X-FM-Host-Namespace`;
- `X-FM-Tenant-Id`;
- `X-FM-Unit-Id`;
- `X-FM-Environment`;
- `X-Correlation-Id`;
- optional `X-Causation-Id` where one operation was caused by another;
- `Idempotency-Key` for mutations.

The exact authenticated scope is validated fail-closed.

## 4. Quickstart

1. Onboard the organization/company and fiscal units in the Control Plane.
2. Configure homologation before production.
3. Register fiscal profiles and provider bindings using references, never raw secrets.
4. Configure the caller workload identity and allowed tenant/unit scope.
5. Query `/v1/capabilities/query` for the exact document, jurisdiction, operation and environment.
6. Submit a mutation only when the required capability/readiness is returned.
7. Reuse the same idempotency key for safe retries of the same logical mutation.
8. Track the returned lifecycle and correlation identifiers.
9. Consume signed webhooks through an idempotent inbox consumer.
10. Reconcile unknown/pending outcomes before attempting a new fiscal side effect.

Synthetic example identifiers:

```text
host: fm.example-saas
tenant: tenant-demo
unit: unit-demo
correlation: corr-demo-0001
idempotency: demo:operation:0001:v1
```

## 5. NF-e guide

NF-e is never selected merely because a sale exists. The consumer supplies the canonical business
facts it owns and asks FM Fiscal for capability/readiness. Recipient fiscal data, jurisdiction,
operation and product fiscal profile must be sufficient for the requested flow. Provider choice,
signing and tax/fiscal rules stay inside governed FM Fiscal boundaries.

## 6. NFC-e guide

NFC-e capability is scoped by environment, jurisdiction, fiscal account/unit, operation and
provider readiness. CSC is a reference-managed secret and must never appear in application source,
fixtures or logs. A consumer must not assume NFC-e based on UI channel or payment method alone.

## 7. NFS-e guide

NFS-e is municipality/provider-specific. Municipality IBGE context and supported provider operation
must be explicit. A service or SaaS billing fact in a consumer application does not itself prove
that a municipality/provider is homologated. Query readiness for the exact scope before mutation.

## 8. Idempotency

Every fiscal mutation has a stable logical idempotency key. Retries of the same logical operation
reuse that key. Do not generate a fresh key after a timeout if the authorization outcome is
unknown; query/reconcile first. Cross-host, cross-tenant and cross-unit keys are isolated by the
fiscal execution partition.

## 9. Webhooks

Webhook deliveries are signed. Verify the signature before accepting/persisting the inbound event,
apply anti-replay rules and deduplicate through the inbox. Consumers should process business effects
and mark the event processed atomically when possible. Duplicate delivery must not duplicate the
business effect.

## 10. Error catalog

Errors are provider-neutral at the Bridge boundary. Clients should distinguish at least:

- authentication failure;
- authorization/scope failure;
- capability/readiness failure;
- validation failure;
- conflict/idempotency failure;
- provider temporary failure;
- unknown authorization outcome requiring reconciliation;
- rate limit/backpressure;
- not found / unsupported operation.

Do not branch consumer code on private provider error structures.

## 11. Sandbox and homologation

Homologation/sandbox is isolated from production. Successful internal/synthetic tests are not
`PRODUCTION_APPROVED`. Official evidence required by a provider, SEFAZ or municipality must be
recorded independently. Production is fail-closed until its own readiness evidence exists.

## 12. Migration guide

When migrating from another authority, preserve sequence floor, idempotency history, lifecycle,
provider references, archive integrity, bindings, reconciliation state, correlation/causation and
audit provenance. Use dry-run/checksum/reconciliation before authority transfer. Never run legacy
and FM Fiscal as silent dual writers after cutover.

## 13. SDK guide

SDKs are thin clients around public Bridge contracts. They may provide request construction,
authentication headers, correlation/idempotency handling, safe retry helpers, capability queries and
webhook verification. They must not embed fiscal rules, provider selection or private database
access.

## 14. Security guide

- store credentials in the approved secret manager/vault;
- grant least-privilege workload scopes;
- reject cross-tenant/unit/host mismatches;
- verify webhook signatures before persistence;
- sanitize logs/traces;
- use HTTPS endpoints;
- rotate workload/webhook credentials under governed overlap;
- do not expose secret material in support diagnostics;
- do not infer readiness from authentication or commercial entitlements.

## 15. Status and readiness

Readiness is queried from FM Fiscal. Relevant levels include contract-only, homologation-ready and
production-approved states. Commercial plan entitlement and fiscal readiness are separate
authorities: being commercially entitled never promotes a jurisdiction/document to production.

## 16. Versioning and changelog policy

Public contracts are versioned. Backward-incompatible changes require a new public contract version
or an explicit migration/deprecation path. SDKs identify which Bridge contract they target.
Regulatory rule changes retain provenance and effective-dating. Release Candidate documentation is
not a promise that external homologation or production cutover has occurred.

## 17. Support diagnostics

When requesting support, provide synthetic-safe identifiers such as correlation id, fiscal document
reference, environment, host namespace and sanitized timestamps/status. Never send raw private keys,
PFX passwords, CSC values, bearer tokens or full sensitive fiscal payloads through ordinary support
channels.
