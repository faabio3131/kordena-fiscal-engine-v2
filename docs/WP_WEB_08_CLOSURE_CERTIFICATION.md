# WP-WEB-08 — Closure Certification

Status: **IMPLEMENTED AND INTERNALLY CERTIFIED**

## Objective

WP-WEB-08 productionizes observability and technical recovery for the FM NFCORE V1 web runtime without turning observability, backup tooling or recovery automation into fiscal authority.

## Delivered

- structured JSON runtime logging with centralized recursive redaction of authorization, password, secret, token, cookie, private-key, certificate, CSC and binary material;
- request/correlation propagation and safe request telemetry;
- low-cardinality runtime metrics with an internal metrics endpoint and explicit rejection of tenant/customer identifiers as metric labels;
- vendor-neutral tracing adapter with correlation/causation context, secret redaction and fail-safe behavior so exporter failures cannot change fiscal outcomes;
- worker telemetry for claimed, succeeded, retry-wait and dead-letter outcomes plus cycle duration/failure signals;
- preservation of the existing operational/compliance alert contracts for certificate expiry/unavailability, queue backlog, dead-letter, rejection rate, sequence gap, prolonged contingency and unknown provider outcome;
- PostgreSQL backup and restore scripts suitable for governed scheduling;
- CI restore rehearsal with checksum validation, clean-schema restore, migration validation and application readiness against the restored database;
- technical recovery targets: initial RPO 15 minutes, RTO 60 minutes, 7 daily + 4 weekly recovery-point baseline after external storage/scheduling is provisioned;
- incident runbooks for API, PostgreSQL, worker, outbox, dead-letter, fiscal provider, secret backend, certificate, webhook, database restore and suspected credential leakage;
- explicit human-authorized cutover rule for any real production restore.

## Certification evidence

Implementation head `37adda9ed2e6e73bf5b799faa16294db0e95cae4` was certified by GitHub Actions run `34915127835` (`FM NFCORE V1 CI`), job `104210998466`, with conclusion **success**.

The same head also passed diagnostic run `34915127846` (`WP08 pytest diagnostic`) with conclusion **success**.

Required gates passed:

- Ruff: PASS
- Mypy: PASS
- Pytest: PASS
- frontend lint: PASS
- frontend strict typecheck: PASS
- frontend tests: PASS
- frontend build: PASS
- Playwright critical E2E: PASS
- Docker Compose validation: PASS
- recovery shell-script syntax validation: PASS
- API/worker/portal image builds: PASS
- non-root image validation: PASS
- insecure production profile rejection: PASS
- API smoke/liveness/readiness: PASS
- safe metrics endpoint smoke: PASS
- worker governed startup/exit: PASS
- portal smoke: PASS
- forbidden-secret image-history inspection: PASS
- PostgreSQL backup/restore rehearsal: PASS
- application readiness against restored database: PASS

No internal gate failure is waived.

## Recovery posture

The repository now contains repeatable technical recovery procedures and a CI restore rehearsal. The RPO/RTO and retention values are engineering targets for the initial production design, not customer-facing SLA commitments.

A real scheduled backup service, external backup repository/object storage, retention enforcement and production restore drill require the real staging/production infrastructure introduced by later work packages. Their absence is therefore an external provisioning dependency, not an invented success claim in WP-WEB-08.

## Safety / non-claims

WP-WEB-08 does **not** claim that cloud infrastructure, an external metrics/tracing vendor, alert notification channels, production backup storage, DNS/TLS, Cakto, real fiscal certificates/CSC/credentials or SEFAZ/prefeitura/provider homologation have been provisioned.

No automated repository workflow is authorized to overwrite a real production database. A destructive/cutover recovery action remains subject to explicit human authorization.

The FM NFCORE must continue using precise readiness states and must not be declared `100% commercial web` until the remaining WP-WEB-09 through WP-WEB-12 dependencies and gates are satisfied.
