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
