# FM Fiscal — Public Bridge API Reference

This human-readable reference complements the machine-readable contracts under `contracts/v1/`.
Those contracts remain canonical for field-level schema validation.

## Core resources

### `POST /v1/capabilities/query`

Queries the exact fiscal capability/readiness for a governed scope. A positive commercial
entitlement does not substitute for this response.

### `POST /v1/issuances`

Submits a governed issuance mutation after capability/readiness, authenticated scope and fiscal
binding have been validated. Requires a stable `Idempotency-Key`.

### `POST /v1/queries`

Queries fiscal lifecycle/provider state through the provider-neutral Bridge boundary.

### `POST /v1/reconciliations`

Starts or continues governed reconciliation when state is pending, divergent or the external
authorization outcome is unknown.

Additional cancel/inutilization/archive contracts remain defined by the versioned OpenAPI/JSON
Schemas and must be invoked only when the corresponding action capability exists.

## Scope headers

- `X-FM-Host-Namespace`
- `X-FM-Tenant-Id`
- `X-FM-Unit-Id`
- `X-FM-Environment`
- `X-Correlation-Id`
- optional `X-Causation-Id`
- `Idempotency-Key` for mutations

These values are claims, not self-authorizing credentials. They must match authenticated workload
identity and governed bindings.

## Authentication boundary

The Bridge S2S contract uses workload identity and an opaque credential reference/secret mechanism.
Do not store bearer secrets in client source code. Do not send a host/tenant/unit header as a
substitute for authenticated identity.

## Mutation semantics

A mutation is accepted only when all required gates are satisfied:

1. authenticated caller;
2. host binding;
3. tenant/unit grant;
4. fiscal account binding;
5. requested action capability;
6. environment/jurisdiction readiness;
7. idempotency contract.

Failure is fail-closed. Retry of the same logical request uses the same idempotency key.

## Canonical errors

The public error surface is provider-neutral. Clients should handle semantic categories rather than
private SEFAZ/provider payloads. Unknown authorization outcomes are not equivalent to a rejection
and require query/reconciliation before a blind retry.

## Events

Outbound fiscal events use the public AsyncAPI envelope and preserve correlation/causation.
Webhook delivery is signed and may be repeated; consumers must verify signature and deduplicate.

## Environments

Homologation and production are distinct execution partitions. Homologation evidence never promotes
production automatically.

## Examples

All documentation examples intentionally use synthetic identifiers. Real certificate material,
CSC, bearer tokens, provider credentials and customer fiscal payloads are excluded.
