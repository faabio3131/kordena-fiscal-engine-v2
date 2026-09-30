# CL-15B — Activation Delivery Core

**Status:** IMPLEMENTATION CANDIDATE — NO REAL PROVIDER CREDENTIALS  
**Date:** 2026-09-29  
**Repository:** `faabio3131/kordena-fiscal-engine-v2`  
**Base:** `28f722744a1fd23bb09db829996026fecbb7d978`

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
