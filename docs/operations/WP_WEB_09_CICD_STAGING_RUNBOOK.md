# FM NFCORE — WP-WEB-09 CI/CD & Staging Runbook

Status: **INTERNAL DELIVERY CONTRACT — EXTERNAL STAGING/PRODUCTION PROVISIONING IS SEPARATE**

## Purpose

This runbook defines the governed path from repository change to certified build, staging deployment and an explicitly approved production promotion. It does not provision a cloud account, DNS, TLS, database, secret backend or fiscal credentials.

## CI contract

The canonical CI workflow runs on pull requests to `main`, pushes to `main`, WP web feature branches and manual dispatch. The quality gate covers:

- repository secret scanning;
- migration-policy validation;
- Ruff, Mypy and Pytest;
- Python dependency audit;
- Node dependency audit;
- frontend lint, typecheck, tests and build;
- Playwright critical E2E;
- Compose and operational-script validation;
- API/worker/portal image builds and non-root validation;
- insecure production-profile rejection;
- container smoke/readiness checks;
- image-history secret inspection;
- CRITICAL container vulnerability policy;
- CycloneDX image SBOM generation and evidence upload;
- PostgreSQL backup/restore rehearsal;
- application readiness against the restored database.

A failed gate must be fixed at the cause. It must not be waived solely to obtain a green workflow.

## Migration governance

`migration_guard.py` requires contiguous versions and blocks new destructive SQL. One destructive statement that predates WP-WEB-09 is fingerprint-pinned as a certified historical migration; changing it or introducing a new destructive statement fails closed.

Applying schema migrations requires `NFCORE_SCHEMA_MIGRATION_APPROVED=true`. Production additionally requires `NFCORE_PRODUCTION_APPROVAL=PRODUCTION_APPROVED`.

Production migrations must remain backward-compatible with the currently deployed application while a rollout is in progress. Schema rollback is not automated. A rollback after failed smoke restores the application revision through the provider driver; any database recovery remains a separate human-authorized recovery procedure.

## Provider-neutral deploy-driver contract

Real deployment is delegated to a provider-specific script under `scripts/deploy/drivers/`. The repository deliberately does not choose AWS, GCP, Azure or another hosting provider in WP-WEB-09.

A provisioned driver must support:

- `deploy <immutable-revision>` — deploy the requested revision;
- `rollback <failed-revision>` — restore the last known-good application release after a failed post-deploy smoke.

The driver must not print credentials, tokens, connection strings, certificates or secret payloads.

## Staging procedure

The `FM NFCORE V1 Staging` workflow is manual. With `execute_deploy=false`, it validates the internal contract and records `BLOCKED_EXTERNAL`; this is not a failed deployment and not a fake staging success.

A real staging deployment requires externally provisioned values:

- `NFCORE_STAGING_BASE_URL` — HTTPS URL;
- `NFCORE_STAGING_DEPLOY_DRIVER` — provider driver path;
- `NFCORE_STAGING_DATABASE_URL` — GitHub environment secret;
- provider authentication/IAM required by the selected driver;
- external secret backend and real staging infrastructure.

When `execute_deploy=true`, the flow is: fail-closed preflight -> governed migration -> deploy immutable revision -> liveness/readiness smoke -> safe deployment evidence. If post-deploy smoke fails, the provider rollback command is invoked and the workflow fails.

The status may become `STAGING_READY` only after a real deployed environment passes this flow. Before that, the correct external state is `BLOCKED_EXTERNAL`.

## Production promotion procedure

Production is never triggered by a normal push. `FM NFCORE V1 Production Promotion` is `workflow_dispatch` only and requires:

1. an immutable `source_revision` that has already passed certification;
2. the explicit string `PRODUCTION_APPROVED`;
3. approval controls configured on the GitHub `production` environment when available;
4. production URL, database secret, provider driver and provider authentication provisioned externally.

The workflow checks out the exact source revision, validates migration policy, applies only approved migrations, deploys the exact revision and performs liveness/readiness smoke. Failed post-deploy smoke invokes application rollback and leaves the workflow red.

Production promotion does not authorize fiscal Go-Live by itself. Real fiscal provider readiness, certificates/CSC and homologation remain governed by later work packages.

## Rollback rules

Application rollback is allowed after a failed staging/production smoke through the selected provider driver. It must restore a known-good immutable application revision. It must not:

- drop or rewrite production schemas automatically;
- restore a database automatically;
- bypass readiness or fiscal fail-closed checks;
- switch fiscal environments/providers without approved configuration;
- turn synthetic credentials into production authority.

Database restore/cutover follows the WP-WEB-08 recovery runbook and remains human-authorized.

## Evidence and secrets

Only non-secret evidence may be uploaded as CI artifacts. Current artifacts include image SBOMs and safe deployment/promotion metadata such as revision and workflow-run ID. URLs with embedded credentials, database DSNs, raw headers and secret values must never be written to artifacts.

## Current external blockers

Until a hosting/provider decision and real staging resources are supplied, no provider driver, public staging URL, staging database secret or provider IAM is expected to exist. Therefore the repository can be internally certified while real staging remains `BLOCKED_EXTERNAL`.
