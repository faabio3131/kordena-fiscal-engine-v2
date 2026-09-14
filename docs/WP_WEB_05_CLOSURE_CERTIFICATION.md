# WP-WEB-05 — Closure Certification

Status: **IMPLEMENTED AND INTERNALLY CERTIFIED**

## Objective

WP-WEB-05 productionizes the asynchronous execution boundary required by the FM NFCORE V1 web product without promoting any external fiscal dependency to production readiness.

Scope from the Web Productionization Master Plan:

- durable outbox worker suitable for a separate process;
- webhook delivery worker routing;
- reconciliation job routing;
- governed retry and dead-letter behavior;
- lease/locking semantics preventing duplicate live processing;
- graceful shutdown;
- recovery after worker crash / expired lease.

## Delivered architecture

The runtime is layered over the already durable transactional outbox. Authoritative job state never lives only in process memory.

`BackgroundWorkerRuntime` owns bounded polling, lifecycle and failure isolation. `RoutedOutboxHandler` dispatches durable operations to specialized handlers and classifies unknown operations fail-closed as permanent poison jobs. `DurableFiscalOutboxWorker` remains responsible for claim leases, retry scheduling, stale-worker fencing, completion and dead-letter transitions.

Webhook delivery propagates correlation and causation identifiers in addition to the signed payload, outbox-entry identity and attempt number. Reconciliation can run through the same governed operation router without coupling the fiscal core to a queue vendor.

## Recovery and concurrency evidence

New certification tests cover:

- webhook and reconciliation routing in a bounded cycle;
- poison/unknown operations moved to dead-letter instead of infinite retry;
- graceful shutdown during idle wait;
- cycle/database failure isolation with bounded failure backoff;
- two real PostgreSQL workers competing for the same live lease without duplicate dispatch;
- expired PostgreSQL lease recovery after simulated worker crash;
- existing durable retry, restart, stale-worker fencing and SQLite concurrency regression suite.

## Certification result

GitHub Actions run `34900664479` certified the implementation against a real PostgreSQL 16 service container.

- Ruff: PASS
- Mypy: PASS — 137 source files
- Pytest: **820 PASS**, 0 FAIL
- Frontend lint: PASS
- Frontend strict typecheck: PASS
- Frontend tests: 4 PASS
- Frontend build: PASS
- Playwright E2E: 2 PASS

The two test-suite warnings are upstream deprecation warnings from Starlette/FastAPI test tooling and are not functional failures.

## Safety / non-claims

WP-WEB-05 does **not** assert production fiscal activation. It introduces no real certificate, CSC, SEFAZ, municipal/provider credential or commercial secret. Production secret backend, container/runtime packaging, observability/recovery operations, staging, cloud provisioning and real fiscal homologation remain governed by later WPs.

`PROD BLOQUEADA`, `BLOCKED_EXTERNAL` and human approval requirements remain unchanged.
