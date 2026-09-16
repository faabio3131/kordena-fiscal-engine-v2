# CL-03 — Production Secrets Certification

## Status

`CERTIFICATION CANDIDATE` — the functional implementation has passed the complete CI matrix; this documentary closure commit must also pass the complete matrix before the block is declared internally certified.

## Baseline

- Repository: `faabio3131/kordena-fiscal-engine-v2`
- Base: `main@6b6765449f6f6e659f540a93eb5b9cccf05fcaac`
- Branch: `feat/nfcore-cl03-production-secrets`
- PR: `#48`
- Functional implementation SHA: `01b8e8847936bde0a05128f041fcd434b3feedbd`
- Functional CI: `FM NFCORE V1 CI` run `35120138360` / CI `#387` — `completed / success`

## Certified scope candidate

CL-03 extends the existing provider-neutral `FiscalSecretVault` boundary without selecting a cloud vendor or placing secret material in NFCORE persistence:

- `ExternalFiscalSecretVault` consumes an injected cloud/Vault-specific `ExternalSecretClient`;
- Control Plane continues to persist only opaque `SecretReference` metadata;
- certificate, CSC and provider credential material remains process-ephemeral and redacted;
- no in-process secret cache is introduced, so provider-side rotation behind a stable reference is visible on the next resolution;
- expired, missing, unauthorized, unavailable or type-mismatched material fails closed;
- provider exception details are suppressed at the domain boundary;
- exact tenant/unit/environment/provider scope is revalidated before external material is accepted;
- runtime access audit contains only reference/scope/version/outcome metadata and cannot carry raw secret material.

## Evidence

The functional SHA passed the complete repository matrix: secret scan, migration governance, Ruff, Mypy, Pytest, dependency audits, frontend gates, critical E2E, Compose/scripts, images, non-root policy, insecure-production rejection, API/worker/portal smoke, secret artifact inspection, vulnerability policy, SBOM and PostgreSQL backup/restore/readiness.

Targeted tests cover successful external resolution, redacted representations, rotation without stale caching, expiry, missing material, permission denial, backend unavailability, scope mismatch and secret-kind mismatch.

## External boundary

No AWS Secrets Manager, Azure Key Vault, GCP Secret Manager, HashiCorp Vault or other paid/external provider has been selected, provisioned or accessed. The vendor-specific client implementation and account credentials therefore remain an explicit human/external dependency.

Expected truthful state after final documentary CI: `INTERNALLY_CERTIFIED / READY_FOR_EXTERNAL_CONFIGURATION / BLOCKED_EXTERNAL`.

## Governance

- Merge performed: **NO**
- Deploy performed: **NO**
- Cloud resources created: **NO**
- Real secrets committed or logged: **NO**
- DNS altered: **NO**
- Production fiscal activation: **NO**
- Cutover: **NO**

No merge, provider selection or external provisioning is authorized by this document.
