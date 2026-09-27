# CL-10 — Governed Cakto Checkout Authority — Certification

**Status:** CERTIFICATION CANDIDATE — functional HEAD green; exact final documentary HEAD must pass the complete CI matrix.
**Date:** 2026-09-27
**Repository:** `faabio3131/kordena-fiscal-engine-v2`
**Base main:** `f679a8a25012235a314ccef1cd78f67abc88ccfb`
**PR:** #64
**Branch:** `feat/nfcore-cl10-cakto-checkout-authority`

## Objective

Close the internal checkout-authority gap without introducing a second checkout or billing persistence model.

CL-10 composes existing canonical authorities:

1. durable commercial pricing catalog;
2. pricing `external_price_reference`;
3. durable `CaktoPlanBinding`;
4. CL-09 commercial release decision;
5. Cakto webhook processing composition.

## Canonical mapping

A Cakto-backed published price references its external offer using:

`cakto://<external_product_id>/<external_offer_id>`

The reference contains identifiers only. It contains no Cakto API credential, client secret, bearer token or webhook secret.

The referenced product+offer pair must resolve to the pre-existing durable `CaktoPlanBinding`, and the binding `plan_id` must match the published NFCore plan.

Checkout URL remains derived by the canonical Cakto binding:

`https://pay.cakto.com.br/<external_offer_id>`

No checkout URL is copied into the pricing catalog or hardcoded in the site.

## Implemented scope

- enumeration of existing durable Cakto plan bindings;
- platform-admin + CSRF governed GET/POST administration at `/v1/admin/checkout/cakto`;
- premium portal workspace `Checkout Cakto`;
- strict parser for `cakto://product/offer`;
- checkout projection states:
  - `unconfigured`;
  - `partial`;
  - `configured`;
- disabled/missing/mismatched bindings fail closed;
- runtime composition initializes/reuses the existing certified Cakto commercial schema even when the webhook secret is not yet available;
- `GET /v1/commercial/offer` now projects Cakto checkout configuration separately from release and pricing;
- checkout URLs remain hidden from the public projection until every purchase gate passes;
- `purchase_enabled` requires simultaneously:
  - explicit human `commercial_approved`;
  - published pricing;
  - complete enabled Cakto mapping for every active public plan/price pair;
  - Cakto webhook processing actually composed in runtime;
- `trial_enabled` remains false because trial release is a separate authority and is never inferred from `trial_days`;
- Cakto/billing continues to grant commercial entitlements only and cannot activate fiscal production.

## Functional evidence

Functional HEAD:
`d5423cd2e74dba19f129a84e259fd609d1fdcb3a`

`FM NFCORE V1 CI` #429 / run `36352614997`: **SUCCESS**.

Pytest result: **953 passed, 1 warning**.

The complete matrix passed, including repository secret scan, migration policy, Ruff, Mypy, Pytest, Python/Node dependency audits, frontend lint/typecheck/tests/build, critical Playwright E2E, Compose validation, operational scripts, runtime image builds, non-root checks, insecure-production rejection, API/worker/portal smoke, forbidden-secret artifact inspection, container vulnerability policy, SBOM, PostgreSQL backup/restore and application readiness against the restored database.

## Security and governance

- tenant OWNER/ADMIN never gains platform checkout authority;
- browser never supplies tenant/role authority;
- checkout mutations require canonical human session, persisted `platform_admin` and CSRF;
- Cakto identifiers are runtime business configuration, not secrets;
- Cakto API/webhook secrets remain outside this surface;
- a mapped checkout does not imply commercial approval;
- commercial approval does not imply webhook processing readiness;
- pricing does not imply checkout readiness;
- checkout/billing does not imply fiscal production authority;
- public checkout URL exposure is fail-closed until all purchase gates pass.

## External boundary

CL-10 does not configure a real Cakto account and does not prove `CAKTO_COMMERCIAL_READY`.

Real activation remains dependent on externally supplied and validated facts:

- actual Cakto account;
- real product and offer IDs;
- real API credentials in the approved secret manager;
- real webhook secret;
- public HTTPS callback;
- controlled authenticated Cakto event delivery;
- durable processing;
- successful reconciliation against the real Cakto account.

No deploy, DNS change, real price publication, real checkout activation, fiscal activation, homologation or Go-Live is performed by this block.

Final internal certification requires the complete CI matrix to pass on the exact documentary HEAD of PR #64. The final exact SHA/run is recorded in the PR checkpoint to avoid a self-referential documentation loop.
