# WP-WEB-09 — Internal Certification

Status: **INTERNAL_READY / STAGING BLOCKED_EXTERNAL / PRODUCTION HUMAN_APPROVAL_REQUIRED**

## Scope certified

WP-WEB-09 establishes the repository-side CI/CD, software-supply-chain, governed migration, staging deployment contract and manual production-promotion contract for FM NFCORE V1 without inventing external infrastructure or credentials.

## Delivered internally

- CI on pull requests to `main`, pushes to `main`, WP web feature branches and manual dispatch;
- repository secret scanning without printing discovered secret material;
- governed migration policy with fail-closed rejection of new destructive SQL and an exact fingerprint allowance only for the already-certified historical migration;
- Ruff, Mypy and Pytest quality gates;
- Python dependency vulnerability audit;
- Node dependency vulnerability audit;
- frontend lint, strict typecheck, tests and production build;
- Playwright critical E2E;
- Docker Compose and operational-script validation;
- API, worker and portal image builds;
- non-root runtime validation and insecure production-profile rejection;
- API, worker and portal container smokes;
- image-history forbidden-secret inspection;
- CRITICAL container vulnerability policy;
- CycloneDX SBOM generation and safe CI evidence upload;
- PostgreSQL backup/restore rehearsal and application readiness against the restored database;
- provider-neutral staging deployment contract with fail-closed preflight, governed migrations, immutable revision deploy, post-deploy liveness/readiness smoke and application rollback on smoke failure;
- manual-only production promotion contract requiring an immutable source revision, explicit `PRODUCTION_APPROVED`, production environment boundary and rollback on failed post-deploy smoke;
- CI/CD and staging operations runbook.

## Final internal gate evidence

GitHub Actions run `35012137797` (`FM NFCORE V1 CI`), head `4c232634c16f28f5073c717e2828a7742f0e2042`, completed with conclusion **success**.

The final matrix passed:

- repository secret scan: PASS
- migration policy: PASS
- Ruff: PASS
- Mypy: PASS
- Pytest: PASS
- Python dependency audit: PASS
- Node dependency audit: PASS
- frontend lint/typecheck/tests/build: PASS
- Playwright critical E2E: PASS
- Docker Compose validation: PASS
- operational-script validation: PASS
- API/worker/portal image builds: PASS
- non-root validation: PASS
- insecure production-profile rejection: PASS
- API/worker/portal smoke: PASS
- image-history secret inspection: PASS
- CRITICAL container vulnerability scan: PASS
- CycloneDX SBOM generation/upload: PASS
- PostgreSQL backup/restore rehearsal: PASS
- readiness against restored PostgreSQL: PASS

No internal test or security gate is waived.

## Precise readiness state

### Repository/internal CI/CD

**INTERNAL_READY**

The internal implementation and certification requirements of WP-WEB-09 are satisfied.

### Real staging

**BLOCKED_EXTERNAL**

A real staging deployment has not been claimed or fabricated. The following external resources remain required before the state can become `STAGING_READY`:

- selected/provisioned hosting or cloud environment;
- provider-specific deploy driver implementation and authentication/IAM;
- real HTTPS staging URL;
- real staging PostgreSQL database and connection secret;
- real external secret backend and its access policy;
- any network/ingress configuration required by the selected provider.

When those resources exist, the repository already contains the governed path to migrate, deploy, smoke-test, produce safe evidence and rollback an application release on failed smoke.

### Real production promotion

**BLOCKED_EXTERNAL / HUMAN_APPROVAL_REQUIRED**

Production is never promoted by normal push. The workflow requires an exact certified source revision, explicit `PRODUCTION_APPROVED`, the `production` environment boundary and all real production infrastructure inputs. This technical promotion does not by itself authorize fiscal Go-Live.

## Safety / non-claims

WP-WEB-09 does not claim that a cloud account, staging/production host, DNS, TLS certificate, production database, production secret provider, Cakto account or real fiscal provider credentials have been provisioned.

Application rollback does not authorize automatic schema rollback or database restore. Any destructive production recovery/cutover remains governed by the WP-WEB-08 recovery rules and explicit human authority.

The next sequenced block is **WP-WEB-10 — Domain, TLS & Production Provisioning preparation**, where provider-neutral edge security and deployment requirements may be prepared internally while real domain/DNS/TLS/hosting remain external dependencies.
