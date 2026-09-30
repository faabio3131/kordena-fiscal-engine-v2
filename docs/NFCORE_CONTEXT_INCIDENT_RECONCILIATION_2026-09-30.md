# NFCORE — Context Incident Surgical Reconciliation

**Date:** 2026-09-30  
**Mode:** governed reconciliation; no production, no fiscal cutover, no real secrets  
**NFCore main at reconciliation start:** `62150240bef42918e9f04a6d5ab955ac7f9cdecb`  
**Kordena protected checkpoint:** `faabio3131/fm-ai-platform` / `staging/kordena-premium@57bbf18cacdc443d329308e6d9328c57aa55ed0a`

## Purpose

Restore agreement between code, CURRENT, Master Schedule and evidence after a context-continuity incident. This reconciliation preserves technically useful work and corrects schedule semantics. It is not a rollback campaign and does not authorize NFCore -> Kordena integration.

## Incident boundary

The incident was a project-context/governance error: an NFCore handoff was treated as continuation of an active Kordena workstream. No evidence was found here of Kordena data corruption, NFCore fiscal cutover, production fiscal activation, secret exposure, or a real NFCore staging deployment.

Kordena is out of scope for writes in this reconciliation.

## PR classification

| PR | Technical result | Canonical classification | Action |
|---|---|---|---|
| #75 — CL-12 governed trial | merged; post-merge CI green | CL-12 IMPLEMENTED / TESTED / MERGED / CERTIFIED | KEEP |
| #76 — CL-13 security/privacy/observability | merged; post-merge CI green | CL-13 IMPLEMENTED / TESTED / MERGED / CERTIFIED | KEEP |
| #77 — CL-14 portal/brand/site CI governance | merged; post-merge CI green | CL-14 IMPLEMENTED / TESTED / MERGED / CERTIFIED | KEEP |
| #78 — CL-15A Railway readiness | provider contract only; real operations deliberately blocked | CL-15 preparatory capability; REAL STAGING BLOCKED | KEEP + RECLASSIFY |
| #79 — CL-15B activation delivery | secure provider-neutral adapter exists and tests pass; it is not wired into RuntimeComposition | IMPLEMENTED_AND_UNIT_TESTED; not operationally integrated | KEEP + RECLASSIFY |
| #80 — CL-16A channel harness | fail-closed harness exists and tests pass; requires real validated staging | INTERNAL_HARNESS_AVAILABLE; CL-16 NOT_STARTED_OPERATIONALLY | KEEP + RECLASSIFY |
| #81 | previous draft attempted to advance CL-17 semantics before predecessor real gates | reconciliation vehicle only | RETRACK AS RECONCILIATION |

No automatic revert is justified by the incident alone.

## Evidence

Post-merge CI on the merge commits:

- #75: run `36647911981` — SUCCESS
- #76: run `36649059227` — SUCCESS
- #77: run `36650848169` — SUCCESS
- #78: run `36653044053` — SUCCESS
- #79: run `36657544411` — SUCCESS
- #80: run `36658622689` — SUCCESS

Site FM PR #24 is retained: its main-push CI governance and patched `undici` dependency are technically independent of the context error; post-merge Site Validation and Cloudflare Worker Validation are green.

## Canonical schedule state after reconciliation

- CL-12: `DONE`
- CL-13: `DONE`
- CL-14: `DONE`
- CL-15: `IN_PROGRESS / BLOCKED_EXTERNAL`
  - Railway provider contract: prepared
  - activation delivery adapter: implemented/unit-tested, not runtime-integrated
  - real NFCore staging: absent
  - real activation provider/credential/delivery evidence: absent
  - real E2E and rollback evidence: absent
  - gate `STAGING_DEPLOYED_AND_E2E_VALIDATED`: **NOT MET**
- CL-16: `NOT_STARTED_OPERATIONALLY`
  - internal validation harness: `PREPARED_NOT_ACTIVE`
  - `COMMERCIAL_CHANNEL_READY`: **NOT MET**
- CL-17: `NOT_STARTED_OPERATIONALLY`
  - historical fiscal/homologation/pilot authorities may be reused later
  - no official homologation or real controlled pilot is claimed
- CL-18: `NOT_STARTED`
- `PRODUCTION_APPROVED`: **NO**
- NFCore -> Kordena: **FORBIDDEN IN THIS PHASE**

## Why #79 is not integrated

`src/kordena_fiscal/application/activation_delivery.py` defines the provider-neutral delivery adapter, but the canonical `RuntimeComposition` does not import, instantiate or expose `SecureActivationEmailDelivery`. Therefore the correct readiness state is implementation/unit-test readiness only.

## Why #80 does not start CL-16

The CL-16 harness itself requires `NFCORE_STAGING_STATE=STAGING_DEPLOYED_AND_E2E_VALIDATED`. That predecessor gate is not met. The harness is reusable preparation, not evidence that real commercial-channel validation began or completed.

## Protected Kordena boundary

During this reconciliation, no write is permitted to:

- `faabio3131/fm-ai-platform`;
- `staging/kordena-premium`;
- Gemini/Maps/Gerente IA;
- Kordena Fiscal V1;
- Kordena Railway/PostgreSQL;
- Kordena tenants/users/subscriptions.

The Kordena checkpoint was revalidated at `57bbf18cacdc443d329308e6d9328c57aa55ed0a`.

## ACTIVE WORK CONTEXT after reconciliation

```text
PROJECT: Kordena
REPOSITORY: faabio3131/fm-ai-platform
BRANCH: staging/kordena-premium
HEAD: 57bbf18cacdc443d329308e6d9328c57aa55ed0a
OPEN PR: none at reconciliation start
MASTER SCHEDULE: Kordena canonical execution/workstream
CURRENT PHASE: final integration/configuration validation
LAST CERTIFIED GATE: repository/deployment checkpoint preserved before NFCore incident
CURRENT BLOCKER: resume exact Gemini/Maps/Control Plane validation context; do not infer NFCore readiness
NEXT ALLOWED ACTION: revalidate Kordena CURRENT, then resume Maps healthcheck/evidence and Gerente IA E2E from the preserved checkpoint
FORBIDDEN CROSS-PROJECT ACTIONS: NFCore cutover, Fiscal Bridge activation, Fiscal V1 writer freeze, NFCore production/staging substitution
```

## Permanent continuation rule

Automatic execution authority is scoped to the **same project + same repository + same Master Schedule + same active context**. It never authorizes a silent switch to another product or repository.

If handoff/memory conflicts with repository evidence, GitHub CURRENT plus the canonical project documentation win.

## Exit criteria

This reconciliation is complete only after the exact reconciliation HEAD passes the canonical CI matrix, the PR is merged, the merge commit passes post-merge CI, NFCore remains frozen at truthful schedule state, and Kordena remains untouched.
