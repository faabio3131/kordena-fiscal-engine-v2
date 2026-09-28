# CL-11.6 — Purchase Readiness Gate — Certification

**Status:** CERTIFICATION CANDIDATE — implementation complete; exact documentary HEAD must pass the complete CI matrix.  
**Date:** 2026-09-28  
**Repository:** `faabio3131/kordena-fiscal-engine-v2`  
**Base main:** `c46d1ad450e6ba71e004c9c6a78eabaabe49a395`  
**PR:** #72  
**Branch:** `feat/nfcore-cl11-purchase-readiness-gate`  
**Implementation HEAD certified before this document:** `a9c98e73ff38685179bb5262cee204492bf5e4fa`  
**Implementation CI:** `FM NFCORE V1 CI #471` — SUCCESS

## Objective

Close CL-11.6 with the fail-closed gate `NO_CHARGE_WITHOUT_DELIVERY_PATH`.

A real public purchase must never be exposed merely because a price and checkout URL exist. The canonical public offer can expose a charge path only when the paid customer can traverse the complete delivery path to an activated NFCore account.

## Current -> Target

Before CL-11.6, `GET /v1/commercial/offer` required:

- explicit human commercial approval;
- configured checkout projection;
- checkout items;
- provider processing configured.

It did not explicitly require readiness of:

- canonical commercial persistence;
- fulfillment;
- provisioning;
- activation delivery.

After CL-11.6, `purchase_enabled=true` requires all of the following:

1. human commercial release approved;
2. published pricing sufficient for a configured checkout projection;
3. checkout mapping configured;
4. provider event receiver / processing configured;
5. canonical commercial persistence composed;
6. canonical fulfillment composed;
7. canonical provisioning composed;
8. activation delivery configured.

Any missing dependency keeps `purchase_enabled=false` and public checkout URLs hidden.

## Architecture

CL-11.6 does not create a second commercial authority.

The new `CommercialDeliveryPathReadiness` is an immutable deterministic projection of capabilities already composed by the runtime. It cannot:

- approve commercial release;
- publish pricing;
- choose a checkout provider;
- create purchases/subscriptions;
- provision tenants/users;
- grant fiscal production authority.

The existing authorities remain canonical.

Provider processing readiness remains the existing checkout/receiver boundary. For the current Cakto adapter this is derived from the composed receiver; future adapters may supply the same neutral readiness signal without changing the Core gate.

## Runtime projection

The runtime derives delivery-path readiness from the existing canonical composition:

- PostgreSQL runtime database -> canonical commercial persistence;
- `RuntimeComposition.commercial_fulfillment` -> fulfillment;
- `RuntimeComposition.commercial_provisioning` -> provisioning;
- injected `PasswordResetDelivery` -> activation delivery.

The runtime profile exposes these states for operability and audit, without turning the profile/UI into authority.

## Fail-closed tests

The CL-11.6 matrix proves independently that purchase remains disabled when any one of these is absent:

- pricing;
- human release approval;
- checkout mapping;
- provider event receiver / processing;
- canonical commercial persistence;
- fulfillment;
- provisioning;
- activation delivery.

When checkout exists but the gate is blocked, checkout URLs remain redacted from the public offer.

A fully-ready synthetic path proves that purchase can become enabled only when all required conditions are true.

## Provider independence

The existing architecture fitness test remains provider-neutral.

A synthetic non-Cakto checkout provider can satisfy the public commercial offer when all canonical readiness conditions are true. This is not evidence of a real Hotmart implementation or homologation; it proves only that the readiness gate does not introduce provider lock-in.

## Security invariants

- fail closed on every missing delivery dependency;
- no browser-originated payment success authority;
- no provider customer/order ID becomes NFCore tenant identity;
- no new auth/RBAC/tenant authority;
- no checkout URL exposed while delivery is incomplete;
- payment never grants fiscal production authority;
- no secret or credential introduced;
- no real external provider activation performed.

## CI evidence

Implementation HEAD `a9c98e73ff38685179bb5262cee204492bf5e4fa` passed `FM NFCORE V1 CI #471` with the complete quality matrix green:

- repository secret scan;
- migration policy;
- Ruff;
- Mypy;
- Pytest;
- Python dependency audit;
- frontend dependency audit;
- frontend lint;
- frontend typecheck;
- frontend tests;
- frontend build;
- Chromium installation;
- critical E2E;
- compose validation;
- operational scripts;
- runtime image builds;
- non-root image validation;
- insecure production profile rejection;
- API smoke/readiness;
- worker startup/governed exit;
- portal smoke;
- forbidden secret artifact inspection;
- container vulnerability policy;
- SBOM generation/upload;
- PostgreSQL backup/restore rehearsal;
- application readiness against restored database.

## Scope not performed

CL-11.6 does not:

- configure a real checkout/provider account;
- configure real webhook credentials;
- configure real activation email/SMS credentials;
- deploy staging or production;
- change DNS;
- activate fiscal production;
- perform fiscal homologation;
- authorize Go-Live.

The real activation delivery adapter remains an external dependency for later staging/commercial-channel phases. Until it is configured, the runtime correctly projects the paid charge path as blocked.

## Exit gate

Candidate gate: `NO_CHARGE_WITHOUT_DELIVERY_PATH`.

The exact documentary HEAD of PR #72 must pass the complete `FM NFCORE V1 CI` matrix before promotion. The final exact SHA/run is recorded in the PR checkpoint to avoid a self-referential documentation loop.
