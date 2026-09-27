# NFCORE V1 — CL-02 → CL-06 Consolidated Internal Certification

## Baseline and governance

All five blocks were developed as independent Draft PRs from the certified CL-01 main baseline:

`6b6765449f6f6e659f540a93eb5b9cccf05fcaac`

Individual branch certification proves each block against that baseline. It does **not** mean the five Draft PRs have already been integrated into `main`. Before commercial launch, authorized merges must be reconciled in dependency order and the complete CI matrix must pass again on every resulting definitive integration HEAD.

No statement in this document authorizes merge, deploy, DNS, paid infrastructure, cutover, real fiscal emission or `PRODUCTION_APPROVED`.

## Block matrix

| Block | Draft PR | Individual evidence | Internal state | External state |
|---|---:|---|---|---|
| CL-02 Worker Runtime | #47 | HEAD `7b9e1feaa671d19708f02ba802903938b63cbb19`, CI #388 / run `35120309507` success | `INTERNALLY_CERTIFIED` | real production handlers/integrated deployment still governed |
| CL-03 Secret Manager/Vault | #48 | HEAD `44716e05f9310ca7d07dfb6f077eb5aee7d7f9f8`, CI #390 / run `35121017894` success | `INTERNALLY_CERTIFIED` | `READY_FOR_EXTERNAL_CONFIGURATION / BLOCKED_EXTERNAL` |
| CL-04 Staging Infrastructure | #49 | HEAD `9e36c79d14dad483853ef8ec4b9f7b1dc0bf4e6f`, CI #389 / run `35120779197` success | `INTERNAL_READY` | `STAGING_READY_FOR_PROVISIONING / BLOCKED_EXTERNAL` |
| CL-05 Cakto Commercial E2E | #50 | HEAD `7c280a51928a9b3111ad13784fcb0676ce4d751b`, CI #391 / run `35124924169` success | `INTERNALLY_CERTIFIED` | `INTERNAL_CAKTO_READY / BLOCKED_EXTERNAL` |
| CL-06 Commercial Onboarding E2E | #51 | final exact HEAD/run is recorded by the final execution report after the CI containing this document completes | certification candidate | `INTERNAL_COMMERCIAL_ONBOARDING_READY / BLOCKED_EXTERNAL` only after final CI success |

## What is internally assembled

The V1 now has implementation candidates covering the production composition root, asynchronous worker runtime, provider-neutral external secret boundary, fail-closed staging/deployment contract, Cakto commercial event processing, commercial entitlement projection, trusted organization/owner provisioning, human authentication/session recovery, basic tenant-scoped customer onboarding and a portal constrained to actually supported durable surfaces.

The architecture keeps the following authorities separate:

- browser session authority;
- commercial/billing entitlement authority;
- Control Plane administrative authority;
- secret-material authority;
- fiscal homologation authority;
- fiscal production activation authority.

No commercial payment or browser action can manufacture fiscal production approval.

## External dependencies still required for a real commercial launch

1. select/provision the actual external Secret Manager/Vault provider and store only real secret material there;
2. provision real staging/production infrastructure, public HTTPS endpoints and provider driver under explicit authorization;
3. configure the real Cakto account, product/offer identifiers, API/webhook credentials, callback and controlled reconciliation;
4. connect the FM website/post-purchase flow to the trusted customer-provisioning ingress;
5. configure a real email/SMS delivery provider for account activation/password recovery;
6. define and evidence the exact initial fiscal production cells (document × operation × jurisdiction × provider);
7. install real fiscal references/credentials through the approved secret boundary;
8. execute official homologation and the controlled real pilot;
9. obtain explicit human Go/No-Go and exact `PRODUCTION_APPROVED` evidence;
10. separately authorize deployment, DNS/cutover and production launch.

These external facts must never be replaced by synthetic evidence.

## Remaining product work after functional assembly

After authorized integration and closure of the functional/external launch gates, the planned product sequence remains:

1. complete premium visual/UX pass;
2. perform fresh market/pricing research;
3. configure final plans, limits, promotions and prices;
4. publish the NFCORE commercial page in the FM Tecnologia website and connect the real checkout/trial journey.

NFCORE V2 cognitive architecture remains outside this V1 closure.

## Final certification rule

CL-06 and this consolidated document become internally certified only when their exact final PR HEAD receives a complete `FM NFCORE V1 CI` result of `completed/success`. The final execution report records that immutable SHA and workflow run.

Individual success remains branch-scoped until explicit human authorization integrates the Draft PRs and a new complete matrix certifies the integrated HEAD.
