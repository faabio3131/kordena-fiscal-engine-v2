# FM NFCORE — WP-WEB-08 Operability & Recovery Runbooks

Status: **technical operating baseline; not a commercial SLA**

## Technical recovery targets

These are internal engineering targets for future staging/production design and are **not customer-facing SLA commitments**.

- target RPO: **15 minutes** for PostgreSQL authoritative state once scheduled production backups/WAL policy is provisioned;
- target RTO: **60 minutes** for database restore plus application validation in the initial production architecture;
- backup retention baseline: **7 daily recovery points + 4 weekly recovery points** once external backup storage is provisioned;
- staging restore rehearsal: required before production Go-Live and after material schema/recovery changes.

The repository provides repeatable backup/restore procedures and CI restore rehearsal. WP-WEB-08 does not claim that an external production backup repository, scheduler or object store has been provisioned.

## Observability contract

Structured runtime events include service, environment, timestamp, level, event, correlation/request identifiers and safe operational fields. Secrets, authorization headers, cookies, tokens, certificate/private-key material, CSC and byte payloads are redacted centrally.

Metrics deliberately restrict label keys to low-cardinality dimensions. Tenant IDs, CNPJ/document IDs and arbitrary customer identifiers are prohibited as metric labels by the runtime registry.

Trace adapters receive correlation/causation context and redacted attributes. Trace-export failure is non-authoritative and must never change fiscal business outcomes.

## Runbook — API unavailable

Symptoms: failed liveness, connection failures or sustained 5xx.

Checks: process/container state; `/health/live`; `/health/ready`; recent structured errors; PostgreSQL connectivity; runtime profile.

Mitigation: restart only the affected API replica after dependency checks. Do not bypass readiness or fiscal fail-closed gates.

Recovery validation: liveness 200, readiness 200, authenticated smoke query, no elevated 5xx/error-rate signal.

Escalate: repeated crashes, corruption indicators, security events or unknown external-provider behavior.

## Runbook — PostgreSQL unavailable

Symptoms: readiness 503 with `database_unavailable`, DB connection failures, worker cycles failing.

Checks: database service health, network path, pool/connectivity, storage, credentials via approved secret channel, schema migration state.

Mitigation: restore DB availability; keep API/worker readiness blocked while authoritative persistence is unavailable. Never fall back to SQLite in staging/production.

Recovery validation: `SELECT 1`, schema/migration check, `/health/ready` 200, controlled fiscal read/reconciliation smoke.

Escalate: suspected data loss, storage corruption, failed recovery, or RPO/RTO risk.

## Runbook — worker stopped

Symptoms: no worker-cycle telemetry, growing due outbox, pending retries not advancing.

Checks: worker process/container, DB connectivity, recent worker failure logs, lease state, dead-letter count.

Mitigation: restart worker after dependency checks. Durable leases/outbox state provide crash recovery; do not manually rewrite job rows merely to clear a queue.

Recovery validation: new worker cycles, outbox drain resumes, no duplicate provider I/O evidence.

## Runbook — outbox backlog growing

Symptoms: claimed/succeeded throughput below creation rate, retry backlog or latency growth.

Checks: provider availability, worker capacity, retry causes, database latency, poison/dead-letter rate.

Mitigation: resolve dependency failure first; scale governed workers only within lease/idempotency guarantees. Never disable retries/idempotency to increase throughput.

Recovery validation: backlog trend decreases, retry rate normalizes, no duplicate fiscal actions.

## Runbook — dead-letter growing

Symptoms: increasing `dead_letter` worker outcomes.

Checks: operation type, permanent provider errors, unsupported/poison operations, payload/contract failures.

Mitigation: quarantine and diagnose. Requeue only after root cause is fixed and idempotency impact is assessed.

Recovery validation: no new poison jobs and corrected operation succeeds in controlled replay.

## Runbook — fiscal provider unavailable

Symptoms: transient provider failures, timeouts, retry growth.

Checks: official provider status, network/DNS, credential validity, certificate state, environment/homologation context.

Mitigation: retain durable jobs and governed retry/backoff. Do not fabricate authorization or switch environment/provider without approved configuration.

Recovery validation: controlled provider request succeeds, retry queue drains, reconciliation confirms authoritative outcome.

## Runbook — secret backend unavailable

Symptoms: secret resolution fail-closed / backend unavailable.

Checks: selected external backend health, IAM/least privilege, network, reference validity and rotation state. Never print the secret while troubleshooting.

Mitigation: restore backend/IAM access. Do not substitute environment/plaintext secrets in staging/production.

Recovery validation: metadata-only resolution audit succeeds and application dependency check returns healthy where implemented.

## Runbook — certificate expired/revoked

Symptoms: explicit secret/certificate expiry or provider rejection.

Checks: approved certificate metadata and secret reference version; never dump PFX/PEM to logs.

Mitigation: perform governed rotation using the approved external secret backend; update opaque reference/version as designed.

Recovery validation: homologation request with the rotated credential succeeds and audit contains no raw material.

## Runbook — webhook failing

Symptoms: retry/backoff/dead-letter for webhook delivery.

Checks: destination availability, HTTP status class, signature/key reference, correlation/causation IDs.

Mitigation: correct endpoint/configuration or dependency; preserve signed delivery/idempotency semantics.

Recovery validation: controlled delivery succeeds and retries drain without duplicate business effect.

## Runbook — database restore

1. Declare incident and stop writers/workers for the target environment.
2. Select an approved recovery point and verify backup checksum/metadata.
3. Restore into a **clean isolated database first**.
4. Validate schema migrations, integrity checks and critical row counts.
5. Start the application against the restored isolated DB and run liveness/readiness plus controlled smoke tests.
6. Only a human-authorized cutover may replace a real production database.

Never execute destructive restore against real production under an automated repository workflow.

## Portal recovery compatibility and unknown fiscal outcome — P02-T07

New activation/recovery delivery uses `#token=`. Previously issued `?reset_token=`
links remain compatible; the Portal consumes the token in memory and immediately
removes it from browser history/URL before issuing API requests. Do not log, copy
or persist these links/tokens. Existing valid links must not be invalidated merely
to simplify the UI. Compatibility removal requires a separate approved migration
and proof that previously issued links no longer need support.

An interrupted fiscal response is not a confirmed failure or success. While the
page remains open, retry the same content/key and consult the scoped durable
state. Do not refresh, close the tab, change the content or create another intent
to bypass an unknown result. No official protocol is inferred from an HTTP status,
number reservation or outbox record.

After reload, automatic recovery of the original fiscal intent is not certified.
T07-B01 governs a proposed server-side receipt/recovery policy; no new browser
storage, fiscal receipt API or authorization policy is implemented by this partial
UX delivery. Preserve existing records and reconcile through the canonical fiscal
authority/provider. Real reconciliation/provider behavior remains P4/P7/P9/P10;
never edit queue rows or synthesize acceptance to clear uncertainty.

## Runbook — suspected credential leakage

Symptoms: secret-like material observed outside approved secret backend or unexpected authorization activity.

Immediate actions: stop propagation; preserve non-secret audit evidence; revoke/rotate affected credential through the approved provider; invalidate dependent sessions/keys where applicable.

Checks: Git history, CI logs, runtime logs/traces, artifact/image history, provider audit logs.

Recovery validation: old credential rejected, replacement works, no raw material remains in current logs/artifacts, incident reviewed by human authority.

## T07 — recuperação de pedido fiscal original (candidata PR #131)

Após reload/crash, abrir a superfície fiscal na mesma conta/unidade/ambiente.
Em Pedidos fiscais recentes, selecionar Retomar pedido original e preencher
exatamente o conteúdo original. O backend conserva a chave original; não copiar
keys/payloads para browser storage. Prepared pode despachar uma vez; executing
somente consulta evidência existente. Sem evidência exata, usar reconciliação
canônica: não criar novo intento para contornar erro, expiry ou revogação.
Recorded indica registro interno, nunca autorização fiscal/produção.
Janela de 24h não libera numeração ou apaga histórico. Troca de conta/epoch,
permissão/escopo inválido ou indisponibilidade de persistência falham fechado.
Retenção/purge continuam P9/P12. Rollback do código conserva schema e metadados;
não implica compensação de operação externa. Somente harness interno certificado
por PR/CI quando verdes; não há homologação oficial ou deploy nesta parcela.
