# FM NFCORE V1 — CL-15 CURRENT STAGING AUDIT — 2026-10-01

## Status

**CL-15: IN_PROGRESS / BLOCKED_EXTERNAL**

This checkpoint records the real state observed across GitHub and Railway before any further staging mutation.

## GitHub CURRENT

- canonical repository: `faabio3131/kordena-fiscal-engine-v2`;
- default branch: `main`;
- main HEAD: `f2fd8a875bdf8ae5327d7f716209603f60d34570`;
- repository visibility: **PUBLIC**;
- latest main CI observed: **FM NFCORE V1 CI #519 — SUCCESS**;
- latest merged block: PR #83 — CL-15 guarded Railway backup/deploy/worker verification preparation.

The repository must not receive real secrets while PUBLIC.

## Railway CURRENT — read-only audit

Railway project exists:

- project: `FM NFCORE Staging`;
- Railway environment label: `production` (Railway default label inside the staging project; this does **not** confer NFCore production authority);
- services present: `nfcore-api`, `nfcore-worker`, `nfcore-portal`;
- no PostgreSQL service is present;
- no service environment variables are currently configured;
- no public Railway service domains are currently attached to API or portal.

Observed deployments:

- `nfcore-api`: **SUCCESS**, deployed from NFCore main `11cec7991c5345e03ef54e58b1fa6b5fbcd51801`;
- `nfcore-worker`: **CRASHED**, deployed from `11cec7991c5345e03ef54e58b1fa6b5fbcd51801`;
- `nfcore-portal`: **SUCCESS**, deployed from `5201eaa663b029d304a89131c28d501e444f730d`.

Therefore the currently running Railway revisions are **not** the current GitHub main `f2fd8a875bdf8ae5327d7f716209603f60d34570`.

## Confirmed worker failure

The worker fails closed with:

`RuntimeConfigurationError: durable worker runtime requires PostgreSQL persistence`

This is consistent with the absence of a PostgreSQL service/configuration and is not evidence of a domain regression.

## Additional Railway state

A pending staged Railway change exists on `nfcore-portal`. It was not applied during this audit.

## Current → Target

### CURRENT

- staging project scaffold exists;
- API/portal can build and start on older revisions;
- worker correctly refuses durable execution without PostgreSQL;
- no PostgreSQL;
- no runtime variables/secrets;
- no public staging domains;
- current GitHub main is not deployed;
- rollback rehearsal has not been certified;
- staging commercial E2E has not been certified;
- `STAGING_DEPLOYED_AND_E2E_VALIDATED=false`.

### TARGET for CL-15

1. repository PRIVATE before any real secret injection;
2. provision governed staging PostgreSQL;
3. configure staging-only variables/secrets outside Git;
4. deploy one immutable certified NFCore revision to API + worker + portal;
5. apply migrations in staging under the approved process;
6. prove API health/readiness;
7. prove worker healthy against durable PostgreSQL;
8. prove portal smoke;
9. expose only the approved staging endpoints/domains with HTTPS;
10. validate activation delivery using a real approved provider/configuration;
11. execute backup/restore evidence;
12. execute rollback rehearsal;
13. execute commercial staging E2E;
14. persist evidence and only then set `STAGING_DEPLOYED_AND_E2E_VALIDATED=true`.

## Activation-delivery integration audit

The internal activation boundary does **not** require a new Core authority.

Confirmed in CURRENT code:

- `PasswordRecoveryService` remains the canonical reset/activation authority;
- `web.human_recovery.PasswordResetDelivery` is the existing injected external delivery port;
- `SecureActivationEmailDelivery` exposes the same `deliver(email, reset)` contract;
- `create_runtime_app(..., password_reset_delivery=...)` already uses that injected port for recovery/trial delivery and commercial delivery-path readiness;
- therefore no provider-specific delivery implementation should be added to the Core before a real outbound provider is selected.

The truthful state is:

`DELIVERY_PORT_READY / SECURE_ADAPTER_READY / CONCRETE_PROVIDER_NOT_SELECTED_OR_CONFIGURED`

This remains `BLOCKED_EXTERNAL`, not an internally missing domain redesign.

## Human / external approvals still required

The following are **not** authorized by this checkpoint:

- changing repository visibility to PRIVATE;
- provisioning paid Railway/PostgreSQL infrastructure;
- inserting real secrets or credentials;
- accepting/deploying staged Railway changes;
- creating/altering external domains or DNS;
- performing real staging deployment/cutover;
- activating real billing or fiscal credentials;
- any production action.

## Next engineering action

Internal preparation is complete enough to identify the real boundary. The next irreversible/external gate is to obtain explicit human authorization for:

1. repository visibility change to PRIVATE;
2. Railway staging infrastructure provisioning/configuration, including PostgreSQL and any associated cost;
3. staging-only secret injection and immutable deploy.

Until that authorization exists, CL-16 remains `NOT_STARTED_OPERATIONALLY` even though its validation harness is already prepared.

## Authorized execution update — 2026-10-01

The previous read-only checkpoint above is preserved as historical evidence. After explicit
human authorization, the external boundary changed as follows:

- GitHub repository visibility is now **PRIVATE**;
- post-merge canonical main remains
  `ccc8def88b77c70aaff7c729e9d17c35a37ad937` with CI #522 `SUCCESS`;
- Railway managed PostgreSQL is now provisioned as service
  `Postgres` / `71691da6-8d32-4c95-9475-d63d9da1cb0c`;
- PostgreSQL has persistent volume
  `c36ea345-b082-4379-9407-c94e9918a01c` at
  `/var/lib/postgresql/data`;
- no public PostgreSQL domain/TCP proxy is attached;
- API and worker runtime variables are not yet activated;
- public API/portal staging domains are not yet attached;
- commercial activation delivery still has no selected/configured concrete outbound provider;
- `STAGING_DEPLOYED_AND_E2E_VALIDATED=false` remains unchanged.

### Railway reconciliation finding

Provisioning PostgreSQL caused Railway to commit the pre-existing staged environment patch.
The portal configuration is consequently pinned to the historical commit
`5201eaa663b029d304a89131c28d501e444f730d`. The portal is still online, but this pin is
configuration drift and must be replaced by the same immutable certified revision used by the
API and worker before CL-15 can be certified.

### New internal CL-15 candidate work

Branch `feat/nfcore-cl15-railway-runtime-gates` prepares:

- the governed `migration_guard.py` inside the API runtime image for private-network
  pre-deploy migration;
- capture of successful API/worker/portal deployment baselines before a rollout;
- Railway rollback through the official GraphQL `deploymentRollback` mutation;
- fail-closed refusal to deploy when a successful rollback baseline is missing;
- secret-safe tests for the rollback helper.

This branch is a **candidate**, not CURRENT main, until its CI passes and merge is separately
authorized.

### Worker staging classification

The current worker deliberately fails closed without an explicit external handler factory.
For CL-15, `NFCORE_WORKER_ONESHOT=true` may be used only as the already-certified durable
PostgreSQL dependency/readiness probe. It must not be represented as continuous fiscal
processing. Real continuous handler composition remains dependent on the later governed
fiscal/provider activation path.

## Real staging execution evidence — 2026-10-01

### FATO CONFIRMADO — canonical revision and CI

- repository visibility: **PRIVATE**;
- canonical main revision deployed to staging:
  `1c34ba001935952f83ec0b065144e0b8311a5650`;
- post-merge GitHub Actions workflow:
  `FM NFCORE V1 CI #524` — **SUCCESS**;
- portal, API and worker probe were deployed from the same canonical revision.

### FATO CONFIRMADO — Railway staging runtime

Project: `FM NFCORE Staging`.

Railway's environment label is `production`, but the NFCore runtime profile and project
purpose remain **staging**. This label does not promote the environment to NFCore production.

Current certified runtime evidence:

- PostgreSQL service: online, persistent, private network only;
- portal deployment: **SUCCESS** on canonical revision;
- API deployment: **SUCCESS** on canonical revision;
- API governed pre-deploy migration: **PASS**;
- schema migration state: before `()`, applied `1..12`, after `1..12`;
- worker staging probe: **SUCCESS** with `NFCORE_WORKER_ONESHOT=true`;
- Railway HTTPS service domains active for API and portal;
- external HTTPS `/health/live`: `live`;
- external HTTPS `/health/ready`: `ready`;
- runtime profile confirms:
  - `environment=staging`;
  - `persistence_backend=postgres`;
  - `secret_backend_profile=external`;
  - HTTPS required;
  - exactly one trusted proxy network configured;
- Railway edge proxy trust is restricted to `100.64.0.0/10`, not `0.0.0.0/0`.

Migration approval was returned to fail-closed state after the successful migration:
`NFCORE_SCHEMA_MIGRATION_APPROVED=false`.

### FATO CONFIRMADO — logical backup/restore rehearsal

Railway native volume backup/PITR is unavailable on the current plan and the dashboard
states that creation of new backups/PITR requires the **Pro** plan.

To avoid a new recurring subscription before commercial-launch readiness, CL-15 executed a
provider-portable logical recovery rehearsal using a temporary private one-shot utility
inside the same Railway project:

- `pg_dump` custom-format backup created from the canonical staging database;
- SHA-256 checksum created and verified;
- isolated temporary database `nfcore_restore_rehearsal` created;
- `pg_restore --exit-on-error` completed;
- source/restored migration counts matched;
- source/restored public table counts matched;
- temporary restore database cleaned up after the rehearsal.

Final safe evidence from deployment
`6a7fbadf-225d-4bb9-8097-43eb2f12ff71`:

```text
logical_backup=PASS
checksum=PASS
restore_rehearsal=PASS
source_migrations=12
restored_migrations=12
source_tables=34
restored_tables=34
```

This certifies **portable logical backup/restore rehearsal for staging**. It does **not**
certify provider-native PITR, production disaster recovery, production RPO/RTO, or durable
off-provider backup retention.

### DECISÃO APROVADA — cost control before commercial launch

During pre-launch construction and certification, avoid new recurring subscriptions where a
technically sound no-new-subscription path exists. Paid capabilities, server upgrades and
other commercial subscriptions are deferred until they are required to make the product
commercially ready.

This decision must never be used to waive production requirements. Before production Go/No-Go,
the project must explicitly re-evaluate and fund, where required:

- durable scheduled backups;
- provider-native PITR or an approved equivalent;
- off-provider retention;
- restore automation and RPO/RTO;
- observability/alerting capacity;
- production compute/database sizing;
- external providers needed for activation, billing, fiscal homologation and delivery.

### CURRENT commercial-readiness truth

The API runtime profile still reports commercial dependencies that are not ready:

- commercial activation delivery: not configured;
- password-reset delivery: not configured;
- pricing catalog: not published;
- commercial release: unavailable;
- checkout provider: unconfigured;
- commercial delivery path: not ready;
- first-party acquisition: not configured;
- trial: not configured;
- Cakto webhook/checkout: unconfigured;
- fiscal production activation: false.

Therefore **CL-15 is not commercially complete** and no production claim is authorized.

### Cleanup pending human 2FA

Two temporary DR-rehearsal utility services are staged for deletion:

- `nfcore-dr-rehearsal-temp-MiP6`
  (`80abd7c8-a664-4d0e-8923-fd690382e840`);
- `nfcore-dr-rehearsal-temp`
  (`6109ffe5-ea47-40f9-9374-0a775d465b27`).

Railway requires interactive 2FA to apply service deletion, so final cleanup remains a human
dashboard action. These services must not remain as permanent infrastructure.

### Próxima ação

1. Human applies the two staged service deletions with Railway 2FA.
2. Re-audit Railway and confirm only API, worker, portal and PostgreSQL remain.
3. Persist cleanup evidence.
4. Continue CL-15/CL-16 only from the remaining real blockers; do not treat the logical
   recovery rehearsal as production DR certification.

## Cleanup reconciliation — 2026-10-01

Human destructive-change confirmation was completed in the Railway dashboard.

Post-cleanup read-back confirms exactly four canonical services remain in
`FM NFCORE Staging`:

- `Postgres` — **SUCCESS**;
- `nfcore-api` — **SUCCESS**;
- `nfcore-worker` — **SUCCESS** / governed one-shot completion;
- `nfcore-portal` — **SUCCESS**.

The two temporary DR rehearsal services are no longer present:

- `nfcore-dr-rehearsal-temp-MiP6` — removed;
- `nfcore-dr-rehearsal-temp` — removed.

Railway reports no unmerged/staged environment changes after cleanup.

GitHub CI for this evidence PR before the cleanup addendum:
`FM NFCORE V1 CI #525` — **SUCCESS** on
`f9ad22f724ed99880924a8f9b769b8f6311052b4`.

The remaining CL-15 infrastructure gate is the application deployment rollback rehearsal.
