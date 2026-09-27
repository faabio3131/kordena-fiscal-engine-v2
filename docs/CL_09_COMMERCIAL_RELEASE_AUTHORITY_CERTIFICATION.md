# CL-09 — Commercial Release Authority — Certification

**Status:** CERTIFICATION CANDIDATE — functional HEAD green; exact final documentary HEAD must pass the complete CI matrix.
**Date:** 2026-09-27
**Repository:** `faabio3131/kordena-fiscal-engine-v2`
**Base main:** `f9b94e0864301701c285e29117ddb9456ffcc3bf`
**PR:** #63
**Branch:** `feat/nfcore-cl09-commercial-release-authority`

## Objective

Close the internal authority gap between "pricing exists" and "the NFCore is allowed to be offered commercially".

The implementation keeps four authorities separate:

1. pricing catalog;
2. commercial release decision;
3. checkout/billing configuration;
4. fiscal production authority.

No state from CI, pricing, Cakto, staging, billing or fiscal readiness can infer or create `COMMERCIAL_APPROVED`.

## Implemented scope

- explicit `CommercialReleaseStatus` state machine vocabulary:
  - `unavailable`;
  - `internal_only`;
  - `waitlist`;
  - `ready_for_checkout_configuration`;
  - `ready_for_commercial_review`;
  - `commercial_approved`;
- immutable versioned `CommercialReleaseDecision`;
- `commercial_approved` requires an explicit human decision reference;
- append-only PostgreSQL history with actor, correlation id and timestamp;
- optimistic versioning under advisory lock;
- migration 8, governed by the existing migration policy;
- canonical global platform-admin + CSRF write boundary;
- premium portal workspace "Liberação comercial";
- backend projects that workspace only when the administration service is actually mounted;
- public `GET /v1/commercial/offer` combines pricing projection and release state without exposing private pricing overrides;
- checkout remains explicitly `unconfigured`;
- `purchase_enabled=false` and `trial_enabled=false` remain fail-closed even when pricing is published and a human decision is `commercial_approved`;
- release decisions are reversible by publishing a later fail-closed version.

## Functional CI evidence

Functional HEAD:
`923853e60be8a84c04a76f55c906f26bf13eff9e`

`FM NFCORE V1 CI` #425 / run `36346135103`: **SUCCESS**.

Pytest result: **945 passed, 1 warning**.

The complete matrix passed, including repository secret scan, migration policy, Ruff, Mypy, Pytest, Python/Node dependency audits, frontend lint/typecheck/tests/build, critical Playwright E2E, Compose validation, operational scripts, runtime image builds, non-root checks, insecure-production rejection, API/worker/portal smoke, secret-artifact inspection, container vulnerability policy, SBOM, PostgreSQL backup/restore and readiness against the restored database.

## Security and governance

- a tenant OWNER/ADMIN does not acquire platform commercial authority;
- browser-provided tenant/role claims remain non-authoritative;
- release mutation requires canonical human session + explicit persisted platform-admin authority + CSRF;
- pricing publication alone never enables purchase;
- commercial approval alone never enables purchase while checkout is unconfigured;
- commercial approval does not grant fiscal production authority;
- no real FM price, checkout URL, Cakto credential, secret or fiscal credential is introduced.

## External boundary

CL-09 is an internal governance primitive. It does not represent:

- approved real pricing;
- configured real checkout;
- configured real Cakto account;
- deployment;
- staging;
- official homologation;
- fiscal pilot;
- production activation;
- Go-Live.

Final internal certification requires the complete CI matrix to pass on the exact documentary HEAD of PR #63. That final SHA/run is recorded in the PR checkpoint so the document itself does not create an infinite self-reference loop.
