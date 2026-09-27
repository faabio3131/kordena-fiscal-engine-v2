# CL-08 — Durable Pricing Administration Runtime — Certification

**Status:** CERTIFICATION CANDIDATE — functional HEAD green; final documentary HEAD must pass the complete CI matrix.
**Date:** 2026-09-27
**Repository:** `faabio3131/kordena-fiscal-engine-v2`
**Base:** `main@57812960ae09013a4540cfb01730facf47c37235`
**PR:** #62
**Branch:** `feat/nfcore-cl08-pricing-admin-runtime`

## Objective

Close the internal operational gap left by Pricing Governance without introducing a second billing, authentication, tenant, persistence or fiscal-authority architecture.

Commercial prices remain configuration data. This block does not define or invent any real FM Tecnologia price.

## Implemented scope

- canonical `CommercialPricingAdministrationService` now operates over a persistence-neutral catalog contract;
- append-only PostgreSQL pricing catalog with immutable version history;
- optimistic version concurrency protected by a PostgreSQL advisory lock;
- publication audit preserves actor, correlation id and timestamp;
- PostgreSQL migration 7 creates durable pricing history and the explicit `platform_admin` authority field;
- the existing canonical `HumanAccount` is extended with explicit platform administration authority;
- tenant OWNER/ADMIN roles do not imply platform administration;
- governed bootstrap script toggles `platform_admin` only on an existing canonical account and requires `NFCORE_PLATFORM_ADMIN_CHANGE_APPROVED=true`;
- public `GET /v1/commercial/pricing` exposes only the active sellable catalog projection and supports an intentional `unpriced` state;
- private tenant overrides and external price references are excluded from the public projection;
- admin GET/POST pricing routes reuse the canonical human session and CSRF boundary;
- the premium portal exposes the commercial catalog workspace only when the backend projects explicit platform-admin authority;
- no browser-provided tenant/role/authority becomes authoritative;
- no real price is hardcoded in backend, frontend or tests.

## Security and authority

Pricing administration is commercial configuration only. It does not grant fiscal homologation, production authority, certificate access, Cakto authority, deployment authority or tenant authority.

Mutation requires:

1. valid canonical human session;
2. explicit persisted `platform_admin=true`;
3. CSRF proof;
4. global commercial-write application authority;
5. optimistic version match.

## Functional CI evidence

Functional HEAD before documentary closure:
`32f6993f3d5e06a729a5388bc8406eb808fa2968`

`FM NFCORE V1 CI` run #417 / run id `36341449997`: **completed / success**.

The complete matrix passed, including repository secret scan, migration policy, Ruff, Mypy, Pytest, Python/Node dependency audits, frontend lint/typecheck/tests/build, Playwright critical E2E, Compose validation, runtime image builds, non-root checks, insecure-production rejection, API/worker/portal smoke, secret-artifact inspection, container vulnerability policy, SBOM generation, PostgreSQL backup/restore and readiness against the restored database.

## External boundary

This certification does not mean a real commercial price is approved or published. Final plans, prices, promotions and external checkout identifiers remain a management/commercial decision and later external configuration.

## Governance

- merge to main: NOT authorized by this document;
- deploy: NOT performed;
- DNS/cutover: NOT performed;
- Cakto production configuration: NOT performed;
- fiscal production activation: NOT performed;
- external homologation/pilot: NOT performed.

Final internal certification requires the complete CI matrix to pass again on the exact documentary HEAD of PR #62.
