# CL-05 — Cakto Commercial E2E Certification

## Scope

CL-05 closes the internal production composition of the existing Cakto commercial boundary without creating a second billing system and without granting any fiscal authority.

The canonical runtime now composes one durable Cakto commercial database, authenticated webhook receiver and asynchronous commercial processor. Webhook secret bytes are accepted only by explicit injection after resolution by the governed external secret boundary; this runtime does not read secret material from environment variables, persist it, cache it or write it to logs.

## Internal evidence

The CL-05 test surface verifies the complete internal path:

- authenticated Cakto webhook ingestion;
- durable inbox persistence;
- plan/offer binding;
- asynchronous event processing;
- commercial tenant derivation;
- entitlement activation;
- invalid-signature rejection before persistence;
- fail-closed missing webhook secret;
- absence of fiscal authority surfaces from the composed commercial runtime.

The pre-existing WEB-11 suite remains authoritative for duplicate delivery, replay tolerance, stale/out-of-order events, cancellation/refund/chargeback, retry/dead-letter, cross-tenant conflicts, reconciliation and the invariant that commercial events never create fiscal production authority.

## Dependency boundaries

CL-05 deliberately does not duplicate:

- CL-02 worker/runtime architecture;
- CL-03 secret resolution/Vault architecture;
- fiscal homologation or production activation;
- customer-facing website checkout implementation.

A production deployment must resolve the Cakto webhook secret through the approved external secret provider and inject the resulting bytes into this composition. The CL-02 worker may invoke `CaktoCommercialProcessor.process_due` after the corresponding blocks are integrated; this PR does not copy or fork the worker architecture while CL-02 remains unmerged.

## External blockers

Real Cakto validation still requires external facts that are not stored or invented in this repository:

- authorized Cakto account/API credentials;
- real product and offer identifiers/bindings;
- real webhook secret stored in the selected external secret manager;
- publicly reachable HTTPS callback;
- controlled real event delivery;
- reconciliation against the real Cakto account.

Until those inputs exist and the controlled external test is completed, the correct external state is:

`INTERNAL_CAKTO_READY / BLOCKED_EXTERNAL`

This is not `DEPLOYED`, `LIVE`, `PRODUCTION_READY`, fiscal `HOMOLOGATED` or `PRODUCTION_APPROVED`.

## Certification rule

The exact certification SHA is the PR HEAD containing this document and must have the complete `FM NFCORE V1 CI` matrix in `completed/success`. The exact SHA and workflow run are recorded in the execution report after CI completion rather than hard-coded into this self-referential file.

No merge, deploy, DNS change, cutover, real fiscal emission or fiscal production activation is authorized by this certification.
