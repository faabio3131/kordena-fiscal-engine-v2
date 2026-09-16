# CL-01 — Production Composition Root — Certification

Status: **INTERNALLY CERTIFIED / 100% GREEN**

Date: 2026-09-16
Repository: `faabio3131/kordena-fiscal-engine-v2`
Branch: `feat/nfcore-cl01-production-composition-root`
Pull Request: `#46`
Certified implementation HEAD before this documentary closure: `e6b5d8cad09ac612821032058a54bc0dd1847e2e`
Base: `main@da3c927c2cd2fac6559f4c178f715fad9db0a14d`

## Scope certified

CL-01 closes the production/commercial composition gap identified in the V1 Commercial Launch audit without replacing canonical subsystems.

The runtime composition now reuses the existing PostgreSQL persistence and canonical domain/security boundaries to compose:

- human identity;
- web sessions;
- password recovery;
- durable portal projections through the canonical Control Plane;
- runtime readiness/profile reporting for the composed services;
- fail-closed behavior for portal surfaces whose production executor is not yet configured;
- continued separation between commercial/runtime composition and fiscal production authority.

No parallel authentication, tenant, authority, fiscal execution, or persistence architecture was introduced.

## Certification evidence

GitHub Actions workflow: `FM NFCORE V1 CI`
Run: `35114399321` / CI #359
Certified SHA: `e6b5d8cad09ac612821032058a54bc0dd1847e2e`
Result: **completed / success**

All quality gates completed successfully, including:

- repository secret scan;
- migration policy;
- Ruff;
- Mypy;
- Pytest;
- Python dependency audit;
- Node dependency audit;
- frontend lint;
- frontend typecheck;
- frontend tests;
- frontend build;
- E2E critical;
- compose validation;
- operational script validation;
- runtime image build;
- non-root image validation;
- insecure production profile rejection;
- API smoke/readiness;
- worker startup/governed exit;
- portal smoke;
- forbidden secret artifact inspection;
- container vulnerability policy;
- image SBOM generation/upload;
- PostgreSQL backup and restore rehearsal;
- application readiness against restored database.

## Failure and correction history

The first CL-01 CI run failed only on Ruff rule `UP035` in the new test file because `Iterator` was imported from `typing`. The test import was corrected to `collections.abc`. No test, assertion, security gate, or quality policy was weakened. The subsequent full CI run was 100% green.

## Governance

This certification means CL-01 is internally complete and technically ready to be merged when explicitly authorized.

It does **not** mean:

- PR #46 is merged;
- V1 is deployed;
- production infrastructure is provisioned;
- external fiscal credentials are installed;
- external homologation is complete;
- fiscal production is approved;
- commercial launch is complete.

PR #46 must remain unmerged until explicit merge authorization. No deploy, cutover, DNS change, production activation, or fiscal production authority is granted by this certification.

## Next block

After merge authorization and integration of CL-01 into the V1 line, the next internal assembly block is CL-02 — productive worker/runtime activation, preserving fail-closed behavior and canonical architecture.
