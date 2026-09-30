# CL-15B — Activation Delivery Core

**Status:** RECONCILED — ADAPTER IMPLEMENTED/UNIT-TESTED / NOT RUNTIME-INTEGRATED  
**Date:** 2026-09-29  
**Repository:** `faabio3131/kordena-fiscal-engine-v2`  
**Base:** `28f722744a1fd23bb09db829996026fecbb7d978`

## Reconciliation note — 2026-09-30

The secure adapter and its unit tests are preserved. However, the canonical
`RuntimeComposition` does not import, instantiate or expose
`SecureActivationEmailDelivery`. Therefore the canonical readiness state is:

`ACTIVATION_DELIVERY_ADAPTER_IMPLEMENTED_AND_TESTED / NOT_OPERATIONALLY_INTEGRATED`

This document must not be used as evidence that real activation delivery is integrated or that
CL-15 is complete.

## Objective

Advance the non-infrastructure portion of CL-15 while real Railway staging remains
`RAILWAY_RESOURCE_LIMIT_BLOCKED`.

The canonical password/reset authority remains `PasswordRecoveryService`. This block
adds only a provider-neutral outbound activation adapter.

## Architecture

```text
PasswordRecoveryService
        |
        v
IssuedPasswordReset (one-time)
        |
        v
SecureActivationEmailDelivery
        |
        v
ActivationMessageTransport
        |
        +--> future provider adapter (SMTP/API/etc.)
```

The transport is an edge adapter. It cannot issue passwords, mint reset grants, create
tenants, assign OWNER, alter subscription state or grant fiscal authority.

## Security invariants

- activation links require HTTPS;
- URL credentials, query strings and pre-existing fragments are rejected;
- the raw reset token is placed in the URL fragment, not the initial HTTP request query;
- message `repr` redacts recipient and body;
- transport/provider exceptions are replaced by a generic delivery error;
- email header injection is rejected;
- no credential, token or message body is persisted by this module;
- no real email/provider secret is introduced into the public repository.

## Retry behavior

Delivery errors propagate as `ActivationDeliveryError` to trusted orchestration.
The existing canonical activation retry path remains responsible for issuing a fresh
one-time reset, which invalidates older unused grants through the existing
`PasswordRecoveryService` authority.

## External boundary still pending

CL-15 remains open until all of the following have real evidence:

- staging hosting/DB/HTTPS/secret backend;
- selected outbound message provider;
- provider credential resolved outside Git;
- real activation message delivery;
- OWNER completes password activation;
- login/onboarding E2E;
- rollback rehearsal.

No `STAGING_DEPLOYED_AND_E2E_VALIDATED` claim is made by CL-15B.


## Certification evidence

Implementation HEAD `42f9dac8c0437a9bfd12c6965b697c3ced5eb5a1` passed the complete
`FM NFCORE V1 CI` matrix in run `36656955383` with conclusion `SUCCESS`.

The green matrix included repository secret scan, migration governance, Ruff, Mypy,
full Pytest, Python/Node dependency audits, frontend lint/typecheck/tests/build,
Playwright critical E2E, Compose/operational validation, API/worker/portal container
builds and smokes, non-root enforcement, insecure-production rejection, forbidden-secret
inspection, CRITICAL vulnerability policy, SBOM generation, PostgreSQL backup/restore
rehearsal and readiness against the restored database.

## Certified internal state

`ACTIVATION_DELIVERY_ADAPTER_IMPLEMENTED_AND_TESTED / NOT_OPERATIONALLY_INTEGRATED / REAL_PROVIDER_DELIVERY_BLOCKED_EXTERNAL`

This state means the canonical activation grant can now be safely adapted to an outbound
message transport without duplicating credential authority. A real launch still requires
a selected delivery provider, externally resolved credentials and real delivery evidence.
