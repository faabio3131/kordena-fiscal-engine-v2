# CL-15A — Railway Staging Provider Readiness

**Status:** CERTIFICATION CANDIDATE — PUBLIC-CI SAFE / NO REAL SECRETS  
**Date:** 2026-09-29  
**Repository:** `faabio3131/kordena-fiscal-engine-v2`  
**Base:** `0939e668e029ae6ad4f08fe0c28cdc5fb7ee15f9`

## Decision

Railway is the selected staging hosting provider for CL-15.

This sub-block deliberately separates provider readiness from real staging execution because
the repository is currently public so the remaining CI matrix can continue using public
GitHub-hosted runners after the private monthly Actions quota was exhausted.

No real Railway token, database DSN, secret-backend credential, fiscal credential, certificate,
CSC or provider secret may be introduced into GitHub while this guard remains active.

## CL-15A scope

CL-15A may:

- select Railway as the staging provider;
- define the provider contract;
- define required non-secret Railway object identifiers;
- validate fail-closed behavior in public CI;
- document the exact boundary for the later real staging activation.

CL-15A may not:

- deploy NFCore to real staging;
- provision or expose real secrets through GitHub;
- claim `STAGING_DEPLOYED_AND_E2E_VALIDATED`;
- run production fiscal credentials;
- bypass backup or rollback requirements.

## Provider contract

`scripts/deploy/drivers/railway.sh` implements the canonical
`nfcore-staging-driver-v1` identity and declares provider `railway`.

Required external identifiers for the future real-execution boundary:

- `NFCORE_RAILWAY_PROJECT_ID`;
- `NFCORE_RAILWAY_ENVIRONMENT_ID`;
- `NFCORE_RAILWAY_API_SERVICE`;
- `NFCORE_RAILWAY_WORKER_SERVICE`;
- `NFCORE_RAILWAY_PORTAL_SERVICE`.

Real execution additionally requires:

- `NFCORE_RAILWAY_REAL_EXECUTION_ENABLED=true`;
- an externally supplied `RAILWAY_API_TOKEN`;
- real staging database and secret backend;
- certified backup mechanism;
- exact rollback mechanism.

The CL-15A driver refuses backup/deploy/worker verification/rollback with
`BLOCKED_EXTERNAL`. This is intentional: a partial deploy path without a proven backup and
rollback mechanism would violate CL-15.

## Public repository guard

The repository remains public only to preserve the full GitHub Actions test matrix while the
private Actions quota is unavailable.

Security consequence:

1. CI receives no real staging secrets.
2. Real staging is not executed from the public repository.
3. The provider adapter contains identifiers/contracts only, never credentials.
4. Real-execution enablement must be a separate certified change after the secret-execution
   boundary is safe (private repository with working CI or an approved equivalent runner path).

## Exit state

Successful CL-15A evidence changes CL-15 from:

`HOSTING_PROVIDER_UNSELECTED`

to:

`RAILWAY_SELECTED / REAL_STAGING_BLOCKED_EXTERNAL`

It does **not** close CL-15.


## Certification evidence

Implementation HEAD `1582470023bfc671ab93d727b4bc87b897d9eaa3` passed the complete
`FM NFCORE V1 CI` matrix in run `36652385276` with conclusion `SUCCESS`.

The green matrix included repository secret scan, migration policy, Ruff, Mypy, full
Pytest, Python/Node dependency audits, frontend lint/typecheck/tests/build, Playwright
critical E2E, Compose and operational-script validation, API/worker/portal image builds,
non-root validation, insecure-production rejection, container smokes, image secret
inspection, CRITICAL vulnerability policy, SBOM generation, PostgreSQL backup/restore
rehearsal and application readiness against the restored database.

## Railway provisioning attempt

A real dedicated Railway project named `FM NFCORE Staging` was requested through the
authenticated Railway control plane without supplying any application secret.

Railway rejected resource creation with:

`Free plan resource provision limit exceeded. Please upgrade to provision more resources!`

Therefore the external staging blocker is now concrete and provider-confirmed:

`RAILWAY_RESOURCE_LIMIT_BLOCKED`

No existing Kordena or IRON resource was repurposed, mutated or deleted to bypass this
limit. No real secret was introduced.

## Final CL-15A state

`RAILWAY_SELECTED / PROVIDER_CONTRACT_CERTIFIED / REAL_STAGING_BLOCKED_EXTERNAL`

CL-15 remains open. The next executable boundary is provision of Railway capacity (or an
explicitly approved alternative resource arrangement), followed by the real API/worker/
portal/PostgreSQL/HTTPS/secret-backend staging path.
