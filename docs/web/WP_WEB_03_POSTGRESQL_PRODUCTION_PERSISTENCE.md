# WP-WEB-03 — PostgreSQL Production Persistence

Status: internally certified for the web-productionization program.

## Purpose

Add a production PostgreSQL persistence profile to FM NFCORE without coupling the fiscal core to PostgreSQL and without changing the already-certified fiscal persistence semantics.

## Architecture

- PostgreSQL uses psycopg 3 and `psycopg_pool` as optional runtime dependencies.
- Mandatory core dependencies remain unchanged.
- The PostgreSQL adapter provides a narrow DB-API compatibility boundary for the certified repositories, translating qmark placeholders and integrity conflicts instead of duplicating fiscal persistence business rules.
- A single PostgreSQL unit of work spans idempotency, numbering, inbox, outbox, ordering, delivery audit, archive, bindings, lifecycle, reconciliation, Control Plane and commercial configuration.
- Transaction-scoped PostgreSQL advisory locks serialize only the affected idempotency key, fiscal sequence, inbox identity or outbox identity, preserving horizontal concurrency without a global lock.
- Production selection is fail-closed: `NFCORE_PERSISTENCE_BACKEND=postgres` and `NFCORE_DATABASE_URL` are required. There is no silent production fallback to SQLite.
- SQLite remains available as a reference/development/test adapter.

## Migrations

PostgreSQL applies the existing fiscal schema migrations 1–5 through a deterministic compatibility translation and adds migration 6 for:

- human accounts;
- opaque web sessions (digest only);
- one-time password reset records (digest only).

Migration execution is serialized with a PostgreSQL transaction-scoped advisory lock and is idempotent on repeated initialization.

## Human identity persistence

The production adapter persists:

- account role, tenant and optional unit scope;
- password hash only;
- session token SHA-256 only;
- CSRF token SHA-256 only;
- session epoch and revocation state;
- password reset token SHA-256 only, expiry and used state.

Raw session, CSRF and reset tokens are never persisted by this layer.

## Real PostgreSQL certification

CI provisions `postgres:16-alpine` and executes the full suite against a live PostgreSQL service.

Final certification:

- GitHub Actions run: `34878747816`
- job: `104092402236`
- Ruff: PASS
- Mypy: PASS — 135 source files
- Pytest: PASS — 804 tests
- real PostgreSQL migration fresh database: PASS
- repeated migration/idempotency: PASS
- commit/rollback: PASS
- tenant partition: PASS
- sequence concurrency: PASS
- idempotency concurrency: PASS
- archive/reconciliation/outbox persistence parity: PASS
- human account/session/password reset persistence: PASS

The earlier internal PostgreSQL transaction warning was corrected before certification. Remaining test warnings are upstream FastAPI/Starlette/httpx/anyio deprecations; the GitHub Actions runner also reports upstream Node action deprecations. No known PostgreSQL application warning remains in the final certified run.

## Explicit limits

This WP does not deploy a production database and does not contain real credentials. It does not authorize production or external fiscal homologation. Background-worker concurrent claim behavior is intentionally deferred to WP-WEB-05, where worker leasing, crash recovery and dead-letter behavior are certified as one coherent subsystem.
