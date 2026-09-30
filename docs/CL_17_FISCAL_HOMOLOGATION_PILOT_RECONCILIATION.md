# CL-17 — Fiscal Homologation + Controlled Pilot — CURRENT Reconciliation

**Status:** CERTIFICATION CANDIDATE — INTERNAL GOVERNANCE RECONCILED / REAL HOMOLOGATION AND PILOT BLOCKED EXTERNAL  
**Date:** 2026-09-29  
**Repository:** `faabio3131/kordena-fiscal-engine-v2`  
**Reconciled main:** `62150240bef42918e9f04a6d5ab955ac7f9cdecb`

## Purpose

Reconcile the Commercial Launch CL-17 work package with the fiscal homologation and
controlled-pilot authorities that already exist in the integrated NFCore CURRENT.

This is not a second homologation engine, a second pilot authority or a replacement for
historical V2-15 evidence.

## CURRENT integration fact

The historical V2-15 certification documents correctly describe their state at the time
they were produced, including the then-open/draft V2-15 PR. They remain historical audit
evidence and must not be rewritten to manufacture a different history.

After that historical checkpoint, the production-readiness governance package was
integrated into `main` through PR #44 with merge commit:

`da3c927c2cd2fac6559f4c178f715fad9db0a14d`

The current main therefore already contains the reusable readiness, controlled-pilot and
Go/No-Go governance required by CL-17.

## CL-17 requirement mapping

| CL-17 requirement | Canonical CURRENT authority/evidence |
|---|---|
| exact launch matrix | V2-15 NF-e, NFC-e and NFS-e homologation matrices |
| provider/jurisdiction/operation readiness | durable provider bindings + homologation readiness |
| certificate/CSC/provider credentials | opaque SecretReference / external secret boundary |
| official external evidence | explicit external-official evidence model; absent evidence remains blocked |
| controlled pilot | Controlled Pilot Governance with exact scope and operation allowlist |
| kill switch | durable pilot/module/provider bindings |
| S2S authorization | canonical authorized fiscal request/security boundary |
| unknown authorization outcome | reconciliation required; no blind retry |
| incident/rollback | controlled-pilot and POST-WEB-12 operational runbooks |
| Go/No-Go | read-only package distinguishing NO_GO, BLOCKED_EXTERNAL and READY_FOR_HUMAN_GO_NO_GO |
| production approval | separate human authority; never emitted by homologation/pilot code |

## Internal state already certified

The integrated architecture already proves, with synthetic/internal evidence:

- NF-e HOMOLOGATION-only technical matrix;
- NFC-e HOMOLOGATION-only technical matrix including provider-scoped CSC;
- NFS-e municipality + provider exact resolution without municipality/UF/provider fallback;
- exact tenant/unit/environment/provider/document/jurisdiction/operation bindings;
- runtime timeout/retry/circuit configuration;
- safe handling of ambiguous authorization outcomes;
- controlled pilot scope with explicit operation allowlist;
- durable kill switches;
- append-only sanitized audit trail;
- deterministic `GO_INTERNAL`, `NO_GO` and `BLOCKED_EXTERNAL` decisions;
- full-scope external-pilot readiness checks;
- Go/No-Go packaging that cannot create `PRODUCTION_APPROVED`.

## What internal evidence does NOT mean

None of the following may be inferred from a green CI, synthetic provider or internal
matrix:

- official SEFAZ homologation;
- official prefeitura homologation;
- official provider homologation;
- valid production A1 certificate;
- valid real CSC;
- valid real provider credential;
- successful external fiscal issuance;
- completed real controlled pilot;
- `PRODUCTION_APPROVED`;
- fiscal Go-Live.

The historical matrices deliberately keep external official evidence absent unless a real
authorized external exercise produced it.

## Remaining CL-17 external inputs

Real execution requires, for the exact launch cells selected later:

1. official homologation environment access;
2. real certificate material through the governed secret boundary;
3. real CSC when the selected NFC-e cell requires it;
4. real provider credentials where applicable;
5. exact UF/municipality/provider/document/operation launch matrix;
6. authorized real pilot tenant/unit;
7. official external responses/evidence;
8. reconciliation evidence;
9. incident/rollback/kill-switch exercise evidence;
10. sanitized evidence references persisted outside source code/secrets.

## Dependency relationship with CL-15 and CL-16

CL-15 real staging and CL-16 real commercial-channel validation remain externally blocked.
This reconciliation does not bypass those predecessor gates and does not start a real
fiscal pilot.

It only eliminates duplicated engineering work and makes the future CL-17 execution path
explicit.

## Current classification

`CL17_INTERNAL_GOVERNANCE_READY / REAL_HOMOLOGATION_AND_PILOT_BLOCKED_EXTERNAL`

This is the maximum truthful CL-17 state until real official external evidence exists.

## Next executable work while external dependencies remain blocked

Internal work may continue only where it does not manufacture external evidence or bypass
the Master Schedule. The next safe activity is CL-18 internal readiness reconciliation:
reuse the already integrated Go/No-Go authority to enumerate remaining blockers without
issuing `PRODUCTION_APPROVED`.

Real CL-17 execution resumes only after its external prerequisites and predecessor external
gates are available.


## Certification evidence

Reconciliation HEAD `6db47c1783037d3e458a7f183c96a3d49558a57c` passed the complete
`FM NFCORE V1 CI` matrix in run `36659247465` with conclusion `SUCCESS`.

The matrix remained green across repository secret scanning, migration governance, Ruff,
Mypy, full Pytest, Python/Node dependency audits, frontend lint/typecheck/tests/build,
Playwright E2E, Compose/operational validation, API/worker/portal image builds and smokes,
non-root enforcement, insecure-production rejection, forbidden-secret inspection,
CRITICAL vulnerability policy, SBOM generation, PostgreSQL backup/restore and readiness
against the restored database.

This CI evidence certifies only the reconciliation and existing internal governance. It is
not official fiscal homologation and is not evidence of a real controlled pilot.
