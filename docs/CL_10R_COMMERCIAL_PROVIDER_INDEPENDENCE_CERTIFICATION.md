# CL-10R — Commercial Provider Independence — Certification

**Status:** CERTIFICATION CANDIDATE — implementation complete; exact documentary HEAD must pass the complete CI matrix.
**Date:** 2026-09-27
**Repository:** `faabio3131/kordena-fiscal-engine-v2`
**Base main:** `08294a0d86ee865bd5aa6eb9868885ae121d55c1`
**PR:** #66
**Branch:** `fix/nfcore-commercial-provider-independence`

## Reason for correction

A reconciliation against the FM Master Foundation Architecture and the pre-existing NFCore commercial configurability documents identified a localized CL-10 regression.

The original foundation is provider-neutral:

- pricing owns generic `external_price_reference`;
- billing owns plans, subscription state, entitlement and quota without gateway identity;
- tenant/platform external configuration models generic commercial gateway references;
- external providers belong to adapter/infrastructure boundaries;
- customer/provider differences must be configuration when the platform already supports the capability.

CL-10 correctly preserved Cakto as an external integration, but incorrectly promoted Cakto-specific checkout types and readiness into the canonical public commercial-offer path. Site FM PR #21 then mirrored that provider-specific public contract.

CL-10R corrects that regression without replacing the existing billing, pricing, tenant, provisioning, Cakto runtime or fiscal authorities.

## Canonical architecture after CL-10R

`GET /v1/commercial/offer` now depends only on the provider-neutral checkout contract:

- `CommercialCheckoutProjector`;
- `CommercialCheckoutProjection`;
- `CommercialCheckoutItem`;
- `CommercialCheckoutStatus`.

The public contract may project any valid provider identifier. No canonical commercial-release code imports or names Cakto.

Cakto remains a provider-specific adapter through `CaktoCheckoutAdministrationService`, which implements the neutral projection contract. Its provider-specific administration route, webhook verification, persistence, reconciliation and entitlement processing remain intact.

## Runtime configuration

Cakto checkout is no longer composed by default.

The runtime setting:

`NFCORE_COMMERCIAL_CHECKOUT_PROVIDER=<provider-id>`

selects the intended commercial checkout provider configuration.

For the currently implemented Cakto adapter, `NFCORE_COMMERCIAL_CHECKOUT_PROVIDER=cakto` explicitly enables its checkout administration composition. Without a configured provider, the canonical commercial offer remains fail-closed and does not initialize the Cakto checkout store solely to serve the public offer.

Future providers may implement the same neutral contract without changing the canonical pricing, commercial release, billing, provisioning or public-offer rules.

## Security and fail-closed invariants

- no provider configured -> checkout remains `unconfigured`, provider is null and purchase is disabled;
- provider identifiers are normalized and constrained;
- checkout URLs must be absolute HTTPS URLs without embedded credentials;
- checkout status must be mathematically coherent with expected/configured item counts;
- checkout items must belong to the selected provider;
- public checkout URLs remain hidden while purchase is disabled;
- purchase still requires explicit human commercial approval, complete checkout projection and provider processing readiness;
- checkout/billing cannot grant fiscal production authority;
- Cakto credentials/secrets remain outside source and outside the public contract.

## Architecture fitness evidence

A dedicated provider-independence test proves that:

1. canonical `web/commercial_release.py` contains no Cakto dependency;
2. a synthetic non-Cakto provider (`hotmart`) can satisfy the canonical checkout projection;
3. the same `GET /v1/commercial/offer` enables purchase when the generic gates are coherent;
4. invalid projection status/count combinations fail closed.

This is an architecture fitness test, not evidence that Hotmart is implemented or homologated. It proves only provider independence of the canonical contract.

## Preserved Cakto capability

CL-10R does not delete or invalidate the Cakto adapter. The following provider-specific capabilities remain available when explicitly configured:

- Cakto product/offer binding;
- `cakto://...` external price reference parsing inside the adapter;
- Cakto checkout URL derivation inside the adapter;
- Cakto webhook receiver/verifier;
- durable Cakto inbox;
- idempotency/retry/dead-letter/reconciliation;
- Cakto commercial entitlement processing;
- provider-specific admin route and portal surface.

## Scope not performed

This correction does not:

- implement Hotmart, Kax or another provider adapter;
- configure any real external commercial account;
- add real product/offer IDs;
- add credentials or secrets;
- activate billing;
- deploy;
- change DNS;
- activate fiscal production;
- perform homologation;
- perform Go-Live.

A new unsupported provider may require one reusable adapter implementation. Once supported, account/product/offer/secret differences remain configuration rather than customer-specific source forks.

## CI

The code-only candidate passed repository secret scan, migration policy, Ruff and Mypy, and its Pytest gate passed before the final documentation/hardening commits.

The exact final documentary HEAD of PR #66 must pass the complete `FM NFCORE V1 CI` matrix before promotion. The final exact SHA/run is recorded in the PR checkpoint to avoid a self-referential documentation loop.
