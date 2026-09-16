# CL-02 — Production Worker Runtime Certification

## Status

`CERTIFICATION CANDIDATE` — the functional implementation has passed the complete CI matrix; this documentary closure commit must also pass the complete matrix before the block is declared `INTERNALLY CERTIFIED / 100% GREEN`.

## Baseline

- Repository: `faabio3131/kordena-fiscal-engine-v2`
- Base: `main@6b6765449f6f6e659f540a93eb5b9cccf05fcaac`
- Branch: `feat/nfcore-cl02-production-worker-runtime`
- PR: `#47`
- Functional implementation SHA: `306c119ea02a85e48cbc4e84efe0df8449277fc2`
- Functional CI: `FM NFCORE V1 CI` run `35119685012` / CI `#386` — `completed / success`

## Certified scope candidate

CL-02 composes the existing canonical background-processing primitives instead of creating a parallel queue/worker system:

- `BackgroundWorkerRuntime` over the durable `DurableFiscalOutboxWorker`;
- explicit operation routing through `RoutedOutboxHandler`;
- canonical durable outbox leases, retry/backoff, dead-letter and delivery audit;
- PostgreSQL remains the durable worker state in production-like environments;
- unknown operations remain fail-closed;
- continuous worker refuses to start without an explicitly configured handler factory;
- `NFCORE_WORKER_ONESHOT=true` remains a readiness/dependency probe and never dispatches jobs;
- graceful stop and crash/lease recovery continue to use the previously certified runtime semantics;
- `WorkerObservability` emits bounded metrics and structured redacted logs;
- unexpected handler exception text is no longer persisted in retry/dead-letter/audit state; only the exception class is retained. Purpose-built handlers may return already-sanitized diagnostic errors.

## Evidence exercised by the full matrix

The functional SHA passed Ruff, Mypy, Pytest, Python/Node dependency audits, frontend lint/typecheck/tests/build, critical E2E, Compose validation, operational-script validation, runtime image build, non-root checks, insecure-production rejection, API readiness, worker container governed exit, portal smoke, secret-artifact inspection, container vulnerability policy, SBOM generation/upload, PostgreSQL backup/restore rehearsal and application readiness against the restored database.

Targeted tests also cover production-worker composition, explicit handler registration, runtime metrics, secret-safe unexpected exceptions and fail-closed continuous startup without a handler factory. Existing canonical tests continue to cover retry, dead-letter, duplicate delivery, concurrent leasing, restart/expired-lease recovery and graceful shutdown.

## External/configuration boundary

CL-02 does not invent provider/webhook handlers that require credentials or real external endpoints. Those handlers must be composed only when their existing canonical dependencies are available through CL-03/CL-04/CL-05. Therefore the worker engine is internally ready, while external handler configuration remains an explicit downstream dependency.

## Governance

- Merge performed: **NO**
- Deploy performed: **NO**
- DNS altered: **NO**
- Production fiscal activation: **NO**
- Real fiscal emission: **NO**
- Cutover: **NO**
- Tests weakened/skipped to hide failure: **NO**

No merge or external promotion is authorized by this document.
