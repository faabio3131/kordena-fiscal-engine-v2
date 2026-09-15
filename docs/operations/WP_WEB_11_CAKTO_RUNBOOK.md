# WP-WEB-11 — Cakto Commercial Activation Runbook

Status: **INTERNAL_CAKTO_READY / BLOCKED_EXTERNAL** after final branch CI passes.

This runbook governs the commercial boundary only. It does not grant fiscal production authority.

## Official contract baseline

Revalidated on 2026-09-15 against the current official Cakto documentation:

- API base: `https://api.cakto.com.br`;
- OAuth2 token endpoint: `/public_api/token/` using `client_id` + `client_secret` and Bearer access token;
- webhook management: `/public_api/webhook/`;
- incoming delivery: `POST application/json`;
- `X-Cakto-Timestamp`: Unix seconds;
- `X-Cakto-Signature`: `v1=<hmac-sha256>` computed over `{timestamp}.{raw request body}` with the webhook secret;
- body envelope: `secret`, `event`, `data`;
- Cakto documents a five-minute replay tolerance example and requires validation over the exact raw body;
- successful delivery is any `2xx`; the receiver must acknowledge quickly and process durable work asynchronously;
- automatic retries are documented for network/timeout failures, not for an application response that is non-2xx;
- duplicate deliveries are expected and the integration must be idempotent.

References:

- https://docs.cakto.com.br/authentication
- https://docs.cakto.com.br/conceitos/webhooks
- https://docs.cakto.com.br/api-reference/webhooks/create
- https://docs.cakto.com.br/api-reference/webhooks/event-history
- https://docs.cakto.com.br/api-reference/webhooks/resend-event
- https://docs.cakto.com.br/api-reference/subscriptions/states

The conceptual webhook guide currently documents subscription lifecycle events including created, renewed, renewal refused, paused, resumed, late, late recovered and canceled. The create-webhook API schema may expose a narrower selectable list. Real activation must therefore verify the exact events available in the connected account/UI/API before registration; the repository must not invent subscriptions to unsupported events.

## Secret and credential rules

Real Cakto values are external inputs and must never be committed:

- `client_id`;
- `client_secret`;
- Bearer access tokens;
- webhook secret;
- real product IDs;
- real offer IDs.

The webhook receiver is composed only when an externally sourced secret has been resolved and explicitly injected. The default runtime does not fabricate or auto-enable the Cakto route.

## Activation sequence

1. Provision an official HTTPS callback endpoint from WP-WEB-10 infrastructure.
2. Create least-privilege Cakto API credentials in the Cakto account and store them in the production secret backend.
3. Resolve the real product and offer IDs and create explicit internal `product + offer -> plan + entitlements` bindings.
4. Register the HTTPS webhook in Cakto only for documented/available events.
5. Resolve the real webhook secret from the secret backend and inject a `CaktoWebhookReceiver` into the runtime composition root.
6. Verify HMAC signature, timestamp tolerance and raw-body handling with the Cakto test event before any real sale.
7. Confirm that the HTTP adapter returns quickly after durable inbox acceptance.
8. Run the asynchronous processor and observe inbox, retry, dead-letter and entitlement metrics.
9. Execute a real controlled commercial event and reconcile it against the Cakto subscription/order API.
10. Record sanitized evidence before promoting readiness to `CAKTO_COMMERCIAL_READY`.

## Durable processing rules

- authenticate before mutation;
- persist a sanitized durable inbox record before business processing;
- deduplicate by documented provider identity and payload fingerprint;
- reject an event identity replayed with conflicting immutable content;
- preserve out-of-order safety by comparing provider occurrence time against the current entitlement event time;
- retry transient local dependencies with bounded backoff;
- move permanent/retry-exhausted failures to governed dead-letter state;
- require explicit administrative reprocessing for dead-letter entries;
- use reconciliation against the remote Cakto state to repair missed/late webhook effects;
- never persist raw webhook body, webhook secret, API credential or bearer token.

## Commercial state effects

Commercial billing is allowed to grant or revoke internal commercial entitlement only.

Supported internal outcomes include activation, grace/suspension, cancellation and reactivation according to confirmed documented events/reconciliation. Unknown product/offer mappings remain fail-closed.

## Fiscal boundary — non-negotiable

No Cakto event, API response, entitlement or billing state may:

- install or replace A1 certificates;
- install or replace CSC/token material;
- bind fiscal provider credentials;
- mark a UF, municipality, document or operation as homologated;
- enable a production fiscal transport;
- set `fiscal_production_activated=true`;
- promote `PRODUCTION_APPROVED`.

Fiscal production activation belongs to WP-WEB-12 and requires separate real fiscal evidence plus explicit human authorization.

## Failure handling

### Invalid signature / replay timestamp
Return `401`; do not create or mutate inbox/business state.

### Invalid/unsupported payload
Return `400`; do not guess fields or event semantics.

### Conflicting duplicate
Return `409`; preserve existing durable state and escalate for inspection.

### Durable inbox unavailable
Do not acknowledge an event as accepted if it was not durably persisted. Recovery may use Cakto event history/manual resend once infrastructure is healthy.

### Processing dependency unavailable after durable acceptance
Keep the accepted inbox entry and schedule bounded internal retry. Do not rely on Cakto re-delivery for an application-side processing failure after acknowledgement.

### Dead letter
Require governed operator review/reprocessing. Never silently discard.

## Readiness states

- `INTERNAL_CAKTO_READY / BLOCKED_EXTERNAL`: code, tests and contracts are complete; real account/event evidence absent.
- `CAKTO_COMMERCIAL_READY`: requires real registered webhook, real authenticated event, durable processing, mapped entitlement and successful reconciliation evidence.
- None of these states imply fiscal production readiness.
