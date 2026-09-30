# CL-16A — Real Commercial Channel Validation Harness

**Status:** RECONCILED — INTERNAL HARNESS PREPARED / CL-16 NOT STARTED OPERATIONALLY  
**Date:** 2026-09-29  
**Repository:** `faabio3131/kordena-fiscal-engine-v2`  
**Base:** `6c6f37145656c238f6dacba3d2a7361d58a0f075`

## Reconciliation note — 2026-09-30

The harness is preserved as safe preparatory code. It does not constitute operational start of
CL-16 because the predecessor CL-15 gate `STAGING_DEPLOYED_AND_E2E_VALIDATED` is not met.

Canonical classification:

`INTERNAL_HARNESS_AVAILABLE / PREPARED_NOT_ACTIVE / CL16_NOT_STARTED_OPERATIONALLY`

## Objective

Prepare the deterministic validation/evidence contract for CL-16 while CL-15 real staging
remains externally blocked.

This block does not simulate or invent a real provider validation. It makes the later
external validation fail closed and auditable.

## Contract

`scripts/ci/commercial_channel_validation.py` exposes:

`nfcore-commercial-channel-validation-v1`

The preflight requires:

- exact staging state `STAGING_DEPLOYED_AND_E2E_VALIDATED`;
- explicit `NFCORE_COMMERCIAL_CHANNEL_REAL_VALIDATION_ENABLED=true`;
- provider identifier;
- HTTPS callback URL without embedded credentials;
- HTTPS checkout URL without embedded credentials.

Passing preflight means only:

`READY_FOR_REAL_VALIDATION`

It never means `COMMERCIAL_CHANNEL_READY`.

## Evidence set

After the real external exercise, a sanitized evidence manifest must contain opaque
`evidence:...` references for:

1. real account/KYC;
2. real product/plan configuration;
3. checkout;
4. webhook registration;
5. authenticated event;
6. controlled purchase;
7. refund or cancellation;
8. reconciliation.

The manifest intentionally stores references/hashes only. It must not contain webhook
secrets, client secrets, bearer tokens, raw payloads, customer PII or payment-card data.

A syntactically complete manifest returns:

`EVIDENCE_SET_COMPLETE`

This still does not autonomously grant fiscal production authority or
`PRODUCTION_APPROVED`.

## Current Cakto readiness

The existing Cakto adapter already provides authenticated HMAC ingress, durable inbox,
deduplication, asynchronous processing, canonical commercial translation, lifecycle
handling, refund/chargeback semantics and provider-vs-Core reconciliation.

CL-16 real evidence still depends on:

- real staging;
- real Cakto account/KYC;
- real product/offer configuration;
- real webhook secret stored outside Git;
- real HTTPS callback;
- controlled purchase;
- refund/cancel where permitted;
- reconciliation evidence.

## Safety

This harness cannot:

- accept a browser assertion that payment succeeded;
- create tenant or OWNER authority;
- grant entitlement directly;
- install fiscal secrets;
- promote fiscal homologation;
- set `PRODUCTION_APPROVED`.

## Exit state

Successful internal certification of this block yields:

`INTERNAL_HARNESS_AVAILABLE / PREPARED_NOT_ACTIVE / CL16_NOT_STARTED_OPERATIONALLY`

CL-16 remains open until real external evidence exists.


## Certification evidence

Implementation HEAD `e5d633a0c8e8d0b2fc11209dd4c939e335bc6445` passed the complete
`FM NFCORE V1 CI` matrix in run `36658024910` with conclusion `SUCCESS`.

The matrix remained green across secret scanning, migration policy, Ruff, Mypy, full
Pytest, dependency audits, frontend validation, Playwright E2E, runtime image builds and
smokes, non-root enforcement, secret inspection, CRITICAL vulnerability policy, SBOM,
PostgreSQL backup/restore and readiness against the restored database.

## Certified internal state

`INTERNAL_HARNESS_AVAILABLE / PREPARED_NOT_ACTIVE / CL16_NOT_STARTED_OPERATIONALLY`

No real Cakto account, secret, transaction or reconciliation evidence was fabricated by
this certification.
