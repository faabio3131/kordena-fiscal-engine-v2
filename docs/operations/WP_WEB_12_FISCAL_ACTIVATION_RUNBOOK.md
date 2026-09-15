# WP-WEB-12 — Fiscal Homologation, Pilot & Production Activation Runbook

Status while no official external evidence is present: **INTERNAL_FISCAL_ACTIVATION_READY / BLOCKED_EXTERNAL** after final CI certification.

This runbook governs the transition from technical readiness to real fiscal homologation, controlled pilot and, only after explicit human authorization, narrowly scoped fiscal production activation.

## Constitutional boundary

Commercial billing and fiscal authority are separate.

Cakto may grant, suspend, cancel or restore a commercial entitlement. Cakto cannot:

- install or select an A1 certificate;
- install or select CSC/token material;
- install fiscal provider credentials;
- mark any homologation cell as official;
- authorize a fiscal pilot;
- create a production activation record;
- set `fiscal_production_activated=true`;
- promote `PRODUCTION_APPROVED`.

Fiscal production is fail-closed unless an exact production authority is explicitly injected into the governed gateway.

## Exact production cell

A production grant is scoped to all of:

- tenant;
- unit;
- provider;
- document family;
- jurisdiction;
- operation.

For NFS-e, jurisdiction includes the exact municipality IBGE code. No grant falls back across tenant, unit, provider, UF, municipality, document or operation.

## Required evidence chain

Production activation may only be assembled after this chain is complete for the exact cell:

1. real secret material is stored outside Git in the approved secret backend;
2. the Core resolves only opaque `SecretReference` values until runtime;
3. the official homologation endpoint is used with the authorized tenant/unit;
4. the operation succeeds or reaches its documented official outcome;
5. sanitized evidence is recorded with provider, environment, jurisdiction, operation, timestamp, correlation/causation identifiers and official external identifier;
6. the durable homologation evidence record has `external_official=true` and a real `external_evidence_id`;
7. an authorized human issues an explicit `PRODUCTION_APPROVED` decision/change-control reference for that exact cell;
8. the activation service validates that human approval and official proof target the same exact cell;
9. an immutable activation record is loaded from the trusted administrative boundary and injected as `ProductionExecutionAuthority`;
10. production execution uses `GovernedProviderGatewayService` and an explicit provider identity.

Missing any item keeps execution blocked.

## Activation API boundary

`FiscalProductionActivationService` creates an activation record only when:

- the actor has `capability.write`;
- the actor may access the target tenant;
- the official proof came from a HOMOLOGATION evidence record;
- `external_official` is true;
- `external_evidence_id` and timestamp exist;
- all required technical evidence flags are complete;
- signer evidence exists when the operation requires signing;
- CSC evidence exists when the operation requires CSC;
- the human decision is exactly `PRODUCTION_APPROVED`;
- human approval and official proof have identical exact keys.

The service never derives approval from environment variables, billing state, mocks, synthetic transports or technical readiness alone.

## Execution gate

`ProductionExecutionAuthority` resolves only exact active grants. The latest record for one exact key wins. A later `REVOKED` record functions as a kill switch.

`GovernedProviderGatewayService` behaves as follows:

- HOMOLOGATION requests continue through the existing governed gateway without requiring production authority;
- PRODUCTION requests require an explicit provider ID;
- PRODUCTION requests require an explicitly injected authority;
- the authority must contain an ACTIVE record for the exact request cell;
- otherwise the provider delegate is never called.

The runtime profile remains fail-closed. Without an injected authority it reports zero active grants and `fiscal_production_activated=false`. It can report true only from an injected authority containing at least one active exact grant; that status alone does not create any grant.

## Real homologation procedure

For each required cell, independently execute and capture sanitized evidence for the applicable operations:

- NF-e: authorize, query, cancel and inutilize where applicable;
- NFC-e: authorize, query, cancel and inutilize where applicable, including real CSC rules;
- NFS-e: exact municipality + provider operations supported by that municipality/provider;
- callbacks/webhooks where the provider uses them;
- controlled retry/idempotency failure cases;
- reconciliation after ambiguous delivery;
- recovery proving no duplicate fiscal issuance.

One successful cell does not certify another.

## Controlled pilot

A pilot may start only when all cells required by that pilot are officially homologated and the tenant/unit is explicitly authorized by the controlled-pilot allowlist.

The pilot must retain:

- kill switch;
- explicit tenant/unit scope;
- S2S/authenticated request boundary;
- reconciliation monitoring;
- duplicate prevention;
- provider health/latency/rejection monitoring;
- rollback/stop conditions;
- sanitized evidence package.

The pilot Go/No-Go package may recommend `GO_INTERNAL`, `NO_GO` or `BLOCKED_EXTERNAL`, but it may not create `PRODUCTION_APPROVED` automatically.

## Emergency revocation

If production was explicitly activated and a safety condition occurs:

1. issue a governed REVOKED activation record for each affected exact cell;
2. inject/reload the latest trusted authority state;
3. verify production gateway rejection before further fiscal traffic;
4. reconcile all ambiguous/in-flight operations;
5. preserve audit and provider evidence;
6. require a new explicit human approval before any later reactivation.

## Current external blockers

At the time of this internal implementation, the repository contains no real evidence for:

- A1 private certificate material;
- CSC/token material;
- provider/SEFAZ/prefeitura production or homologation credentials;
- official external responses proving homologation;
- authorized real pilot tenant/unit;
- real production approval decision.

None may be substituted with synthetic fixtures.

## Readiness terminology

- `INTERNAL_FISCAL_ACTIVATION_READY / BLOCKED_EXTERNAL`: activation and safety boundary is coded/tested, but official external homologation/pilot evidence is absent.
- `HOMOLOGATED`: only an exact external cell with official evidence may use this term.
- `PILOT_READY`: only when every cell required by the explicitly authorized pilot is officially homologated.
- `PRODUCTION_APPROVED`: explicit human decision only, never a software-generated promotion.
