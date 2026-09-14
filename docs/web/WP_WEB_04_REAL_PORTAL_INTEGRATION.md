# WP-WEB-04 — Portal Web Real + Product/API Integration

## Status

CERTIFIED INTERNAL / READY FOR MERGE.

This work package converts the FM NFCORE V1 portal from a synthetic presentation surface into an authenticated web control center that consumes server-authorized product projections and operations.

It does **not** approve production fiscal operation. External credentials, certificates, homologation evidence, provider connectivity and human go-live approval remain explicit blockers.

## Delivered

- authenticated browser session integration through `/v1/auth/*`;
- session-derived tenant authority; browser tenant/unit headers are not accepted as authority;
- RBAC mapping for portal surfaces and fiscal operations;
- unit scope validation on the server;
- CSRF protection for browser mutations;
- mandatory idempotency key for issue/cancel/inutilize/reconcile mutations;
- anti-mass-assignment rejection for tenant, role, permissions and other server-owned authority fields;
- fail-closed `503 PORTAL_RUNTIME_NOT_READY` when a real server-side product executor is absent;
- secret-output boundary that rejects password/token/secret/private-key/certificate/CSC material from portal projections;
- real portal fetch integration for bootstrap, surfaces and operations;
- login/logout UI and governed fiscal-operation dialog;
- preservation of `PROD BLOQUEADA`, `BLOCKED_EXTERNAL` and `HUMAN_APPROVAL_REQUIRED` safety states;
- V1 scope remains NF-e, NFC-e and NFS-e;
- responsive premium FM NFCORE visual system preserved;
- frontend lint, strict JS typecheck, contract tests, deterministic build and Playwright critical E2E gates added to CI.

## Security model

The browser is an interface, never an authority. Tenant, role, permissions and allowed units are reconstructed from the opaque authenticated session. Product execution remains server-side. The portal has no synthetic runtime fallback.

## Certification

Certification run: GitHub Actions `34898182681`.

Validated gates:

- Ruff: PASS
- Mypy: PASS — 136 source files
- Pytest: PASS — 814 tests
- Frontend ESLint: PASS
- Frontend TypeScript checkJs/strict: PASS
- Frontend contract tests: PASS — 4 tests
- Frontend build: PASS
- Playwright critical E2E: PASS — 2 tests
- PostgreSQL 16 CI service: healthy

Warnings observed are upstream/runtime-environment deprecations from FastAPI/Starlette/AnyIO and GitHub Actions internals; no application regression or security warning is left unresolved by this work package.

## Remaining production blockers

- production product executor wiring to real fiscal providers;
- real secret backend and credentials;
- official SEFAZ/municipality/provider homologation evidence;
- real certificates/CSC where applicable;
- production deployment, DNS/TLS and operational infrastructure;
- controlled pilot and human go-live approval.

These blockers must not be inferred away by portal configuration or UI state.
