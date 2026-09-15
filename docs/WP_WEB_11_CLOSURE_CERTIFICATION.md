# WP-WEB-11 — Closure Certification

Status: **INTERNAL_CAKTO_READY / BLOCKED_EXTERNAL**

Branch: `feat/nfcore-web-11-cakto-commercial-activation`

PR: `#42`

Implementation gate already observed: commit `6e12c02caaf09d34613ab144e1b563c7dcb38b81`, GitHub Actions run `35018594572`, conclusion `success` with the complete quality/security/runtime/recovery matrix. This documentation changes the branch HEAD, therefore the final certified HEAD is only the later documentation HEAD after its own CI completes successfully.

## Scope delivered internally

WP-WEB-11 now contains a provider-specific Cakto commercial boundary that remains structurally separate from fiscal authority.

Delivered repository-controlled capabilities:

- official Cakto API/webhook contract modeled without embedding real credentials;
- checkout URL derivation from an explicitly configured real offer identifier;
- timestamped HMAC-SHA256 webhook origin validation over the exact raw body;
- replay-window protection;
- documented webhook V1 object and V2 list envelope handling;
- durable sanitized webhook inbox;
- duplicate/idempotent reception;
- conflicting replay detection;
- product + offer to internal plan/entitlement mapping;
- tenant provisioning only after a confirmed entitlement-bearing commercial event;
- activation, payment-failure/grace/suspension, cancellation and reactivation state handling;
- out-of-order/stale-event protection;
- bounded retry state and governed dead-letter state;
- reconciliation primitives for remote Cakto subscription state versus local entitlement state;
- PostgreSQL/SQLite commercial persistence isolated from fiscal authority state;
- HTTP callback adapter exposed only by explicit receiver injection;
- commercial metrics with low-cardinality labels;
- negative tests for invalid signature, stale/replayed delivery, duplicate event, conflicting duplicate, unsupported event/payload, missing mapping, out-of-order event and cross-tenant identity conflict;
- PostgreSQL persistence certification in CI;
- operational runbook for activation, failures, reconciliation and external blockers.

## Official contract revalidation

On 2026-09-15 the implementation was rechecked against current official Cakto documentation. The documented contract confirms OAuth2/Bearer API authentication, webhook secret, `X-Cakto-Timestamp`, `X-Cakto-Signature` using `v1=<hmac-sha256>`, exact raw-body signing, webhook envelope `secret/event/data`, retry/replay/idempotency guidance, event history/resend support and subscription lifecycle documentation.

The conceptual webhook guide documents more subscription lifecycle event names than the create-webhook API schema currently enumerates. No production registration may assume an event is selectable until the connected real Cakto account/API/UI confirms it.

## Billing authority versus fiscal authority

The implementation intentionally has no capability through which Cakto can:

- install fiscal certificates;
- install CSC/tokens;
- install provider credentials;
- mark any fiscal homologation cell as successful;
- enable production fiscal transport;
- set fiscal production activation;
- promote `PRODUCTION_APPROVED`.

`/runtime/profile` remains `fiscal_production_activated=false` independently of Cakto state. Billing can grant/revoke commercial entitlement only.

## Test/security evidence

The implementation HEAD run `35018594572` completed successfully with:

- repository secret scan;
- migration policy;
- Ruff;
- Mypy;
- Pytest including real PostgreSQL tests;
- Python dependency audit;
- Node dependency audit;
- frontend lint/typecheck/tests/build;
- Chromium install and critical E2E;
- Compose validation;
- operational script validation;
- runtime image builds;
- non-root validation;
- insecure production profile rejection;
- API/worker/portal smokes;
- forbidden secret artifact inspection;
- container vulnerability policy;
- image SBOM generation/upload;
- PostgreSQL backup/restore rehearsal;
- application readiness against restored database.

Final PR merge remains prohibited until the final documentation HEAD repeats the required CI successfully.

## Real external evidence

None is claimed. This execution did not receive or invent:

- an authenticated real Cakto account/session;
- real Cakto `client_id` / `client_secret`;
- a real webhook secret;
- real Kordena product/offer IDs in Cakto;
- a real registered public HTTPS callback;
- a real signed delivery from Cakto;
- a real commercial subscription/order reconciliation result.

## External blockers

To promote from `INTERNAL_CAKTO_READY / BLOCKED_EXTERNAL` to `CAKTO_COMMERCIAL_READY`, objective evidence is required for:

1. real Cakto API credentials stored in the external secret backend;
2. real product/offer identifiers and approved internal pricing/entitlement mapping;
3. public HTTPS callback endpoint;
4. real webhook registration and provider-generated secret;
5. a real signed event accepted into the durable inbox;
6. successful asynchronous entitlement processing;
7. remote API reconciliation proving local commercial state matches Cakto.

## Residual risks

- provider contract drift must be monitored before activation;
- create-webhook selectable event schema and conceptual lifecycle catalog must be reconciled against the real account at activation time;
- operational retry/latency characteristics must be validated using real Cakto deliveries;
- real external Secret Manager/KMS, domain/TLS and production network remain WP-WEB-10 external blockers.

## Decision

Internal software decision: **READY_FOR_MERGE when final HEAD CI is 100% green**.

Readiness after merge: **INTERNAL_CAKTO_READY / BLOCKED_EXTERNAL**.

`CAKTO_COMMERCIAL_READY`, fiscal homologation, pilot authorization and `PRODUCTION_APPROVED` are explicitly not claimed.
