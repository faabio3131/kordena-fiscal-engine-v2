# WP-WEB-12 — Closure Certification

Intended repository readiness after a successful final-HEAD CI and merge: **INTERNAL_FISCAL_ACTIVATION_READY / BLOCKED_EXTERNAL**.

Branch: `feat/nfcore-web-12-fiscal-production-activation`

The exact final certified HEAD/run is recorded in the WP-WEB-12 pull request and merge evidence. Merge is prohibited unless the final PR HEAD completes the full CI matrix successfully.

## Preflight reality audit

WP-WEB-12 started from `main` after WP-WEB-11 was merged at `852a3e2be44051ab9e482149ee4d203e1f0c052b` and its post-merge CI completed successfully.

The existing fiscal repository already certified substantial internal HOMOLOGATION-only foundations:

- exact provider/context technical homologation gates;
- NF-e synthetic matrix;
- NFC-e synthetic matrix with provider-scoped CSC;
- NFS-e municipality + provider matrix;
- controlled pilot allowlist and kill switch;
- SecretReference/Vault boundaries;
- provider routing, retry/reconciliation and signing boundaries.

Those historical matrices explicitly state that official external homologation was not executed. They remain internal evidence and are not reclassified by this WP.

## Gap found and closed internally

The audit found a real architectural gap: central readiness required `PRODUCTION_APPROVED` for production, but there was no separate exact tenant/unit/provider/document/jurisdiction/operation activation boundary that had to be explicitly injected at the provider execution edge.

WP-WEB-12 adds that missing boundary without enabling real production.

Delivered repository-controlled capabilities:

- exact `ProductionActivationKey` scoped by tenant, unit, provider, document, jurisdiction and operation;
- municipality required for NFS-e activation;
- `OfficialHomologationProof` accepted only from `HOMOLOGATION` records carrying `external_official=true`, a real external evidence identifier, timestamp and complete required technical evidence;
- immutable `HumanProductionApproval` requiring the literal decision `PRODUCTION_APPROVED`;
- activation service requiring `capability.write`, tenant scope and exact approval/proof match;
- immutable ACTIVE/REVOKED activation records with correlation and provenance references but no secret material;
- `ProductionExecutionAuthority` with exact matching and latest-record revocation kill switch;
- `GovernedProviderGatewayService` that never calls the production delegate without explicit provider identity plus an injected exact active authority;
- HOMOLOGATION execution remains independent from production authority;
- runtime profile reports production active only from an explicitly injected authority and otherwise remains false/zero;
- negative tests for non-official evidence, missing RBAC, cross-tenant, cross-unit, cross-provider, cross-jurisdiction, invalid human decision, absent authority, absent provider and revocation;
- activation/runbook documentation preserving billing/fiscal separation.

## Billing/fiscal separation

WP-WEB-11 Cakto state has no input into the production activation service. Commercial entitlement cannot generate official fiscal proof, human production approval or activation authority.

There is no automatic path from checkout, payment, subscription, environment variable, mock, synthetic transport or technical readiness to fiscal production.

## Existing external homologation status preserved

The historical matrices remain exactly what their evidence proves:

- NF-e internal/synthetic certification only;
- NFC-e internal/synthetic certification only;
- NFS-e internal/synthetic certification only;
- no provider/UF/municipality/operation is newly labeled externally `HOMOLOGATED` by this WP;
- no controlled real pilot was executed;
- no production fiscal transaction was executed.

## Required full gate

The final PR HEAD must pass the existing complete matrix before merge:

- repository secret scan;
- migration policy;
- Ruff;
- Mypy;
- Pytest including PostgreSQL integration tests and new WP-WEB-12 tests;
- Python dependency audit;
- Node dependency audit;
- frontend lint/typecheck/tests/build;
- critical E2E;
- Docker/Compose validation and image builds;
- non-root validation;
- insecure production profile rejection;
- API/worker/portal runtime smokes;
- forbidden secret artifact inspection;
- container vulnerability policy;
- SBOM generation;
- PostgreSQL backup/restore rehearsal;
- readiness against the restored database.

## Real external evidence

None is claimed by this internal closure. No real A1 private material, CSC, provider credential, SEFAZ/prefeitura/provider official response, pilot traffic or production fiscal traffic was supplied or fabricated.

## External blockers

Real progression now requires objective external inputs/evidence, as applicable to each target cell:

1. authorized tenant/unit for homologation and pilot;
2. real A1 certificate through the production secret backend;
3. real CSC where required;
4. real provider/SEFAZ/prefeitura credentials;
5. official homologation environment connectivity;
6. exact successful evidence per document × operation × UF/municipality × provider;
7. controlled pilot evidence and Go/No-Go package;
8. explicit human `PRODUCTION_APPROVED` decision for exact cells before any production authority is injected.

## Residual risks

- external provider/municipal contract behavior remains unverified until real homologation;
- certificate/CSC lifecycle and external credential rotation require real secret-backend operations;
- production infrastructure from WP-WEB-10 remains externally blocked until real domain/DNS/TLS/cloud/network resources exist;
- GitHub branch/environment administrative protection must be configured independently of repository code where organizational policy requires it;
- no software test can substitute for the explicit human approval required before real fiscal production.

## Decision

If and only if the final PR HEAD is fully green, the repository-controlled WP-WEB-12 preparation is eligible to merge as:

**INTERNAL_FISCAL_ACTIVATION_READY / BLOCKED_EXTERNAL**.

This is not `HOMOLOGATED`, not `PILOT_READY`, not real fiscal production and not `PRODUCTION_APPROVED`.
