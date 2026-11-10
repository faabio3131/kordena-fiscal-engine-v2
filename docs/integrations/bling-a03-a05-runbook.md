# Bling multi-tenant Worker — A-03 / A-04 / A-05

Status: internal candidate pending code certification. Owner: agent A.
Baseline: main 2133ecf7b15a555e2635ab0d906945e76ef8d6d0.
Scope: one canonical fiscal outbox and OAuth installation authority. No second API, registry, engine, queue or authentication.

## Deployment safety
- New `deploy/contabo/compose.bling.worker.opt-in.yml` is OPT-IN and not referenced by `deploy.sh`, `compose.prod.yml` or automatic cron.
- No worker starts unless `NFCORE_WORKER_CONNECTOR=bling-multi`, `NFCORE_BLING_INSTALLATIONS_ENABLED=true`, production/external/postgres and required secret files are valid.
- Migration 21 (worker policy) is additive and MUST be applied by the existing migration guard only after separate production migration approval, verified backup and rehearsal. Do not enable the API multi mode before schema 21 is certified on the target database. Do not automatically apply DDL from startup.
- The Worker reads connected installation metadata from `fm_bling_installations` and each cycle re-resolves `FiscalApplicationService.resolve_scope`; tenant/unit/company NEVER originate from the process .env or an untrusted event.
- A unique partial index prevents concurrent active companies within one canonical outbox partition (host namespace bling, tenant/unit/environment). Multiple installations for the same company/unit can exist only when inactive; multi-company same fiscal unit is NOT supported by current outbox selection and must not be silently claimed.
- OAuth access/refresh/webhook secrets remain AES-GCM encrypted, with keys supplied from deployment-owned secret mounts. TLS provider fixed origin. Automatic refresh uses DB lease/CAS; invalid-grant sets needs_reauth; no fallback to unscoped token.
- Bling writeback status IDs are per installation and validated; incomplete mapping blocks dispatch, never uses one provider's status IDs for another client. Workers only issue in fiscal HOMOLOGATION, never production.
- Reuses `DurableFiscalOutboxWorker`, lease, retry/backoff, delivery audit and dead-letter. Interval uses process stop Event; signals trigger graceful drain.
- Health uses the existing worker health publisher; the overlay includes no open inbound port, all caps dropped, read-only root, bounded PID and memory-independent queues.
- Existing legacy single-company mode remains separate only for existing explicitly configured test/pilot setups; never set legacy company/tenant/unit keys with multi mode.

## Approval-dependent enablement (NOT DONE by merging to main)
1. Obtain separate authorization for real credentials, server-side secret mounts, governed migration and worker activation.
2. Backup production DB and verify the dump; validate migration 21 policy, apply only with approved guard.
3. Compare installed compose/runbook to repository; prepare production-owned permissions for `.env.bling.worker` and the three secret files.
4. Confirm API and Worker use same schema and no legacy vars; run read-only `require_current_schema(require_bling=True)`.
5. Dry-run Docker config with opt-in overlay **without** launching; launch only when authorized.
6. Smoke: two tenants/two units, signed webhook, order review, retry idempotency, auth expired, worker restart, DLQ alert. A1 external and live provider approvals remain separate.
7. Rollback: stop only `nfcore-bling-worker`; do not drop schema or delete credentials; preserve canonical outbox for controlled replay; investigate failed work without erasing durable audit.
8. Verify deployed SHA and readiness, track worker crash/queue health; do not claim live homologation without A1/provedor.

## Acceptance
A-03: exact-scope job claims; install status/provider token revalidated before work; OAuth refresh; status mapping per installation; retries/DLQ via canonical path; cancellation safe.
A-04: compose opt-in, secrets fail-closed, no port, schema gate, smoke/probe and non-activation default.
A-05: Ruff, Mypy, SQLite/Postgres, focused tests, complete GitHub CI/governance, PR review, post-merge CI/governance and checkpoint. No merge if gates failed; no production release until separately approved.
