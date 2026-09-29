# CL-13 — Commercial Security, Privacy, LGPD & Observability — Certification

**Status:** CERTIFICATION CANDIDATE  
**Date:** 2026-09-29  
**Repository:** `faabio3131/kordena-fiscal-engine-v2`

## Scope

CL-13 does not create a second security, privacy or observability stack. It reuses the
already-certified NFCore authorities and closes gaps specific to the commercial chain.

Inherited certified boundaries include:

- S2S/workload identity and HMAC verification;
- edge security, CORS, trusted proxy and HSTS controls;
- canonical tenant/unit/provider isolation;
- fixed-window rate limiting;
- durable inbox/outbox/retry/DLQ boundaries;
- structured logging and metrics;
- fiscal observability/tracing/alerts;
- Bandit/pip-audit and secret scans;
- LGPD/retention technical package with explicit `LEGAL_VALIDATION_REQUIRED` items.

## Commercial PII hardening

Runtime redaction now treats the following key families as sensitive in addition to
credentials/secrets:

- e-mail;
- legal name;
- buyer identity;
- external customer id.

This prevents commercial PII from being emitted by generic runtime logging when an
application/adaptor accidentally passes such fields.

## Commercial telemetry

A bounded `CommercialTelemetry` boundary was added for:

- acquisition;
- validated sale event;
- claim;
- provisioning;
- activation;
- billing transition;
- provider drift;
- backlog;
- failure.

Telemetry uses only low-cardinality `operation` and `outcome` metric labels. It
does not accept tenant ids, e-mail, customer ids, payloads or arbitrary free-form
reason text as metric dimensions.

Reason codes must be bounded safe tokens. Structured logger redaction remains a
second defensive layer.

## Privacy/LGPD

The previously certified technical LGPD package remains authoritative. CL-13 does
not invent legal retention periods or legal bases.

The following remain explicitly human/legal dependencies before commercial live:

- final privacy policy;
- DPA/terms;
- final retention periods;
- legal basis/purpose review;
- subprocessor register and transfer review;
- lawyer/accountant/DPO review where applicable.

## Security invariants

- external provider id never becomes canonical tenant id;
- browser cannot assert payment success, entitlement, tenant or fiscal production authority;
- commercial events cannot promote fiscal readiness or `PRODUCTION_APPROVED`;
- secrets/PII are forbidden from logs and metrics;
- duplicate/replay and rate-limit controls remain fail-closed;
- observability failure cannot become commercial/fiscal authority.

## Exit condition

The exact PR HEAD must pass the complete `FM NFCORE V1 CI` matrix before merge.
