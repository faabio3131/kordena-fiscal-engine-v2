# FM NFCORE V1 — Commercial Launch CURRENT

**Canonical status date:** 2026-09-27
**Canonical repository:** `faabio3131/kordena-fiscal-engine-v2`
**Canonical main baseline before CL-08:** `57812960ae09013a4540cfb01730facf47c37235`

This document supersedes the execution-state assumptions of PR #45. Historical plans remain evidence of prior decisions but do not override CURRENT Git/GitHub state.

## Confirmed integrated baseline

PR #55 was human-authorized and merged into `main`.

The canonical main baseline above contains the integrated lineage:

- CL-01 Production Composition Root;
- CL-02 Production Worker Runtime;
- CL-03 Production External Secret Boundary;
- CL-04 Staging Infrastructure Contract;
- CL-05 Cakto Commercial Runtime/E2E;
- CL-06 Commercial Onboarding and Customer Recovery E2E;
- Pricing Governance;
- CL-07 Premium Product Experience.

Post-merge `FM NFCORE V1 CI` #414 passed on the exact main merge commit.

## Current internal closure block

CL-08 — Durable Pricing Administration Runtime is implemented in PR #62.

Functional candidate HEAD `32f6993f3d5e06a729a5388bc8406eb808fa2968` passed the complete `FM NFCORE V1 CI` #417.

CL-08 closes the internal gap previously documented by Pricing Governance: durable catalog versions, actor/time/correlation audit, explicit platform-admin authority, zero-code price publication, public active-catalog read surface and premium portal administration.

No real FM price has been introduced.

## Commercial readiness classification

### A — Functional readiness

Core V1, Web runtime, human auth/session/RBAC, tenant/unit authority, worker runtime, PostgreSQL persistence, Cakto internal boundary, customer onboarding/recovery, premium portal and pricing administration are implemented/certified internally, subject to final CL-08 documentary CI and authorized merge.

### B — Commercial surface parity

Premium NFCORE portal exists. The commercial website/public purchase surface remains an external repository/integration workstream and must consume the canonical pricing/checkout contracts rather than duplicate prices or billing logic.

### C — Production technical readiness

Internal provider-neutral contracts exist for secrets, staging/deploy, observability, backup/recovery and runtime profiles.

Real provider-specific staging/production infrastructure is not yet evidenced.

### D — Operational readiness

Internal runbooks/gates and backup/restore evidence exist. Real external incident/monitoring endpoints, production credentials, provider driver and operational cutover have not yet been evidenced.

### E — Commercial readiness

NOT YET COMMERCIAL LIVE.

The following facts remain external or human-governed and cannot be fabricated:

1. choose/provision the real Secret Manager/Vault and install secret material there;
2. choose/provision real staging/production hosting, PostgreSQL, ingress and HTTPS;
3. materialize and execute the real provider deploy driver;
4. configure real Cakto account/product/offer identifiers, credentials and webhook callback;
5. connect the FM commercial website/post-purchase flow to NFCORE provisioning;
6. configure real password-reset email/SMS delivery;
7. define final plans/prices/promotions through the governed pricing interface after management approval;
8. install real fiscal certificate/CSC/provider credentials through the secret boundary;
9. establish the exact launch fiscal cells by document × operation × jurisdiction × provider;
10. obtain official homologation evidence for each sold cell;
11. execute the controlled real pilot;
12. complete legal/LGPD operational validation where required;
13. obtain explicit human Go/No-Go / `PRODUCTION_APPROVED`;
14. authorize deployment, DNS/cutover and production smoke.

## Security/governance risk

GitHub repository visibility is CURRENTLY **PUBLIC**. The repository secret scan and CI security gates are green, but public source visibility is a separate governance decision. If public visibility was temporary, it must be restored to PRIVATE through an authorized GitHub repository setting before commercial launch.

## Next execution order

1. Finish CL-08 documentary certification and authorized integration.
2. Audit the canonical FM Tecnologia commercial-site repository CURRENT and connect it to canonical NFCORE pricing/provisioning contracts.
3. Select the real external infrastructure/secret provider under explicit human decision.
4. Provision staging and execute real staging gates.
5. Configure/test real Cakto and reset delivery.
6. Execute fiscal homologation matrix and controlled pilot with real credentials/evidence.
7. Perform final production readiness audit.
8. Human Go/No-Go.
9. Authorized production cutover and hypercare.

No later block may convert `BLOCKED_EXTERNAL` into READY without reproducible external evidence.
