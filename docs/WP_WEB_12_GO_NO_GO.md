# WP-WEB-12 — Controlled Fiscal Pilot Go/No-Go

Decision: **BLOCKED_EXTERNAL**

This decision is not a software failure. It records that the repository-controlled preparation can be internally complete while the evidence required for a real fiscal pilot is external and currently absent.

## Internal gate

The repository contains the required internal safety primitives for a later controlled pilot:

- exact tenant/unit scoping;
- provider/jurisdiction/document/operation binding;
- SecretReference/Vault separation;
- signing and CSC boundaries;
- technical homologation matrices;
- idempotency, reconciliation and unknown-delivery handling;
- controlled-pilot allowlist and kill switch;
- explicit fiscal-production activation authority with revocation;
- observability, recovery and CI security gates.

These primitives do not constitute official homologation.

## Real pilot prerequisites

A real pilot remains blocked until all of the following are evidenced for the pilot scope:

- explicit tenant and unit authorization;
- target document families and operations selected;
- target UF and, for NFS-e, exact municipality selected;
- target provider selected;
- real A1/CSC/provider credentials available only through the approved secret backend;
- official homologation connectivity available;
- every required exact homologation cell has official external evidence;
- callback/webhook paths, when applicable, are verified externally;
- reconciliation and duplicate-prevention recovery are proven under controlled failure;
- monitoring/stop thresholds are agreed for the real pilot.

## NO-GO conditions during a future pilot

The pilot must stop or remain disabled if any of these occurs:

- certificate, CSC or credential resolution failure;
- exact provider binding ambiguity or jurisdiction mismatch;
- evidence for a required homologation cell is missing;
- unknown authorization outcome cannot be reconciled safely;
- duplicate-emission risk cannot be ruled out;
- material discrepancy between official provider state and internal reconciliation state;
- uncontrolled cross-tenant/cross-unit access;
- kill switch/revocation cannot be demonstrated;
- production approval is absent or not explicitly human-controlled.

## Current evidence

No real fiscal credential, official homologation response or authorized pilot execution was available during this WP. Historical NF-e/NFC-e/NFS-e matrices are synthetic/internal and stay classified as such.

## Production decision

No `PRODUCTION_APPROVED` decision is recorded by this package.

Even after a successful future pilot, promotion to production requires a separate explicit human decision for the exact fiscal production cells. Software may validate and enforce that decision but may not create it automatically.
