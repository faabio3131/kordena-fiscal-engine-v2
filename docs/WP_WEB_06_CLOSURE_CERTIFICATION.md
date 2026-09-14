# WP-WEB-06 — Closure Certification

Status: **IMPLEMENTED AND INTERNALLY CERTIFIED**

## Scope

WP-WEB-06 introduces a vendor-neutral production secret boundary without choosing or inventing a cloud provider. Normal application state stores opaque secret references and metadata only; raw secret material remains outside normal persistence and browser contracts.

## Delivered

- `SecretBackend` protocol and `SecretResolver` authority boundary;
- opaque, validated `SecretReference` values protected against path/URL traversal;
- tenant/unit/purpose-scoped authorization;
- development/test `InMemorySecretBackend` explicitly rejected in staging/production;
- vendor-neutral `CallableProductionSecretBackend` integration boundary for the future selected provider;
- versioned rotation and revocation semantics;
- explicit expired/revoked/missing fail-closed behavior;
- metadata-only resolution audit events;
- redacted `repr()` for secret material and stored secret records;
- short-lived `SecretMaterial` with best-effort memory zeroization;
- provider exceptions normalized so secret-bearing error details are not propagated.

No AWS, Azure, GCP, Vault, KMS or other external provider is claimed as configured by this WP.

## Regression found and corrected

The stricter certification run exposed a real pre-existing PostgreSQL worker race: two concurrent worker transactions could select the same due outbox row before either lease commit, causing the losing transaction to collide on the delivery-attempt audit primary key.

The worker now treats that durable audit conflict as the claim fence: the losing transaction rolls back the complete claim and performs no provider I/O. The existing stale-worker and crash-recovery semantics remain intact.

## Certification

GitHub Actions run `34905170774` / job `104180046904`:

- Ruff: PASS
- Mypy: PASS — 138 source files
- Pytest: **830 PASS**, 0 FAIL
- real PostgreSQL 16 service: PASS
- frontend lint: PASS
- frontend strict typecheck: PASS
- frontend tests: 4 PASS
- frontend build: PASS
- Playwright critical E2E: 2 PASS

Remaining warnings are upstream test/action deprecations and are not product failures: Starlette/FastAPI test-client deprecations and GitHub Actions Node runtime deprecation notices.

## Safety / non-claims

- no real secret, certificate, CSC or fiscal credential was added;
- no production secret provider was selected;
- no secret is intentionally exposed through browser, logs, exception messages or normal database state;
- production fiscal activation remains fail-closed;
- external provider selection and credentials remain human-controlled later-stage dependencies.
