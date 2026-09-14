# FM Fiscal — Developer Documentation

Status: **Release Candidate documentation — internal certification only**.

FM Fiscal is the independent fiscal product of FM Tecnologia. This documentation describes the
public Bridge contracts and integration model without exposing private product domains or secrets.

## Start here

- [Developer Guide](DEVELOPER_GUIDE.md) — authentication, quickstart, NF-e, NFC-e, NFS-e,
  idempotency, webhooks, sandbox, migration, SDKs, security, readiness and versioning.
- [API Reference](API_REFERENCE.md) — public resources, required headers, errors and mutation
  semantics.

## Contract sources

The canonical machine-readable contracts remain versioned under `contracts/v1/`:

- OpenAPI;
- JSON Schema;
- AsyncAPI.

Documentation never grants fiscal readiness. A client must query Capability & Readiness and must
not infer `PRODUCTION_APPROVED` from successful authentication, plan entitlement, sandbox tests or
documentation examples.

## Safe examples

All examples are synthetic. Never copy a private certificate, CSC, production credential, real
customer payload or private endpoint into source control, documentation or support tickets.
