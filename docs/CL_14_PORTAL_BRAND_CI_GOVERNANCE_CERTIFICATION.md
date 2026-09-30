# CL-14 — Portal/Brand/Admin UX + Site CI Governance — Certification

**Status:** CERTIFICATION CANDIDATE — internal implementation complete; exact-head CI required before merge.  
**Date:** 2026-09-30  
**Repository:** `faabio3131/kordena-fiscal-engine-v2`  
**Base main:** `68af14cbd5eb84e30220d9441995a8452be34ff7`  
**Branch:** `feat/nfcore-cl14-brand-ci-governance`

## Objective

Close CL-14 without changing fiscal, commercial, tenant, RBAC or production authorities.

## Brand reconciliation

The official product remains **FM NFCORE** with positioning **Infrastructure Mission Control** and tagline:

`Infraestrutura fiscal. Sob controle.`

The runtime uses:

- `portal/assets/fm-nfcore-mark.svg` for login/sidebar/runtime identity;
- `portal/assets/favicon.svg` for compact identity;
- official blue/cyan tokens from `docs/brand/fm-nfcore.tokens.json`.

The FM Site may use the director-approved marketing lockup in raster form. The marketing lockup and the runtime vector monogram are official context-specific variants, not competing identities.

No third visual identity is authorized.

## Provider-neutral commercial UX

The platform administration surface is now named:

`Canais de Venda / Checkout`

Cakto remains an adapter under this neutral capability.

The UI no longer presents the provider-specific label `Checkout Cakto` as the capability name. Existing Cakto endpoint/contracts remain unchanged and provider-specific details stay inside the adapter surface.

## Accessibility and responsive contract

Automated tests preserve:

- `lang="pt-BR"`;
- skip link;
- favicon and official mark;
- responsive breakpoints 1050px, 760px and 480px;
- `prefers-reduced-motion`.

## Site FM CI governance

Site repository: `faabio3131/fm-tecnologia-web-platform`.

PR #24 was merged as:

`26bfe05c2891bfc68f680587d0ae47ee36f105b1`

The Site now validates both pull requests and direct `push: main` for:

- Site validation;
- Cloudflare Worker validation.

Post-merge evidence for the exact merge commit:

- Site validation run `36650010744`: **SUCCESS**;
- Cloudflare Worker validation run `36650010707`: **SUCCESS**.

During the new gate, `npm audit` exposed an existing HIGH vulnerability in build tooling through `undici`. The site branch pinned the patched `undici 7.30.0`; both PR and post-merge validation passed after the correction.

## Safety invariants

CL-14 does not:

- grant fiscal production authority;
- change tenant identity;
- change commercial purchase authority;
- change checkout/provider authority;
- relax RBAC;
- expose secrets;
- infer homologation or `PRODUCTION_APPROVED`.

## Exit condition

The exact NFCore branch HEAD must pass the complete `FM NFCORE V1 CI` matrix before merge.

After merge, CL-15 may proceed to real staging provisioning. CL-15 remains dependent on real external infrastructure inputs.
