# FM NFCORE V1 — Commercial Launch CURRENT

**Canonical status date:** 2026-09-27
**Canonical NFCore repository:** `faabio3131/kordena-fiscal-engine-v2`
**Canonical NFCore main:** `f9b94e0864301701c285e29117ddb9456ffcc3bf`
**Canonical FM commercial-site repository:** `faabio3131/fm-tecnologia-web-platform`
**Canonical site main:** `2dc20eb12bb3cd57d24dc5a36af4521bbdbcb7ef`

This document is a CURRENT tracker, not authority over GitHub. Every resume must revalidate the repositories before work.

## Confirmed integrated NFCore baseline

The canonical NFCore main contains:

- CL-01 Production Composition Root;
- CL-02 Production Worker Runtime;
- CL-03 Production External Secret Boundary;
- CL-04 Staging Infrastructure Contract;
- CL-05 Cakto Commercial Runtime/E2E;
- CL-06 Commercial Onboarding and Customer Recovery E2E;
- Pricing Governance;
- CL-07 Premium Product Experience;
- CL-08 Durable Pricing Administration Runtime.

CL-08 was human-authorized through PR #62 and merged at `f9b94e0864301701c285e29117ddb9456ffcc3bf`.
Post-merge `FM NFCORE V1 CI` #422 passed on that exact main commit.

## Confirmed integrated FM commercial-site baseline

The FM commercial site was reconciled from its previously cumulative branch chain:

`DEV-001 -> Premium UX/UI -> Approved FM Hero/Site`

and promoted through PR #19.

Current site main:
`2dc20eb12bb3cd57d24dc5a36af4521bbdbcb7ef`.

The exact integrated content passed Site Validation and Cloudflare Worker Validation before promotion. Git compare from the validated integration HEAD to the main merge commit showed zero file changes.

No Cloudflare deploy, DNS change or production publication was performed by that integration.

## Current internal closure block

CL-09 — Commercial Release Authority is implemented in PR #63.

Functional candidate HEAD:
`923853e60be8a84c04a76f55c906f26bf13eff9e`

`FM NFCORE V1 CI` #425 / run `36346135103`: **SUCCESS**.

CL-09 closes the authority gap between a published pricing catalog and authorization to offer NFCore commercially.

The NFCore now models pricing and commercial release separately. It also keeps checkout/billing and fiscal production authority separate. The public commercial offer remains fail-closed: purchase and trial stay disabled while checkout is unconfigured, even when pricing exists and the human release state is `commercial_approved`.

## Commercial readiness classification

### A — Functional readiness

Internally strong/certified through CL-08 on main. CL-09 is a certification candidate pending exact final documentary-head CI and authorized merge.

The Core, Web runtime, human auth/session/RBAC, tenant/unit authority, worker runtime, PostgreSQL persistence, Cakto internal boundary, customer onboarding/recovery, premium portal, durable pricing administration and commercial release authority exist in the canonical product line.

### B — Commercial surface parity

The FM commercial site is now consolidated in its canonical `main`.

NFCore remains fail-closed on the site. The next integration block must consume the canonical NFCore `GET /v1/commercial/offer` contract without copying prices or release state into the site repository.

### C — Production technical readiness

Internal provider-neutral contracts exist for secrets, staging/deploy, observability, backup/recovery and runtime profiles.

Real provider-specific staging/production infrastructure is not yet evidenced.

### D — Operational readiness

Internal runbooks/gates and backup/restore evidence exist. Real external incident/monitoring endpoints, production credentials, provider driver and operational cutover have not yet been evidenced.

### E — Commercial readiness

**NOT COMMERCIAL LIVE.**

Current external/human dependencies include:

1. final human approval/merge of CL-09 after final CI;
2. Site FM consumer integration for the canonical NFCore commercial offer contract;
3. final real plans/prices/promotions approved through governed pricing;
4. real checkout/billing configuration and Cakto account/product/offer references;
5. real Cakto credentials/webhook/callback/reconciliation;
6. real password-reset email/SMS delivery;
7. real Secret Manager/Vault provider and secret material;
8. real staging/production hosting, PostgreSQL, ingress and HTTPS;
9. real provider deploy driver and staging certification;
10. real fiscal certificates/CSC/provider credentials through the approved secret boundary;
11. exact launch fiscal cells by document × operation × jurisdiction × provider;
12. official homologation evidence for every sold fiscal cell;
13. controlled real pilot with external evidence;
14. legal/LGPD operational review where required;
15. explicit human Go/No-Go / `PRODUCTION_APPROVED`;
16. authorized deploy, DNS/cutover and production smoke.

## Repository visibility

NFCore and the FM commercial-site repositories are intentionally **PUBLIC temporarily** because the private GitHub Actions monthly quota was exhausted and CI runners were blocked.

While public:

- no real secrets, certificates, CSC, passwords, Cakto tokens, cloud credentials or webhook secrets may enter source/history;
- secret/dependency/vulnerability scanning must remain enabled in every relevant CI;
- before commercial launch, once the heavy internal CI cycle ends, the operator must be told explicitly that the repositories can return to PRIVATE.

## Next execution order

1. Finish CL-09 documentary certification and human-authorized integration into NFCore main.
2. Implement Site FM -> NFCore commercial-offer consumption with fail-closed fallback and no duplicated pricing.
3. Implement/verify real checkout authority when Cakto configuration exists; only then can `purchase_enabled` become eligible for a future true state.
4. Select/provision external infrastructure and secret provider under explicit human decision.
5. Provision staging and execute real staging gates.
6. Configure/test real Cakto and password-reset delivery.
7. Execute exact fiscal homologation matrix and controlled pilot with real evidence.
8. Perform final production readiness audit.
9. Human Go/No-Go.
10. Authorized production cutover and hypercare.

No later block may convert `BLOCKED_EXTERNAL` into READY without reproducible external evidence.
