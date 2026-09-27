# NFCORE V1 — Pricing Administration Governance Certification

## Business rule

Commercial prices are configuration data. Changing a price, plan, trial, package, add-on, promotion or external gateway price reference must not require a source-code edit.

No real FM NFCORE commercial price is approved or introduced by this change. Numeric values used by automated tests are synthetic fixtures only.

## Administrative authority

`CommercialPricingAdministrationService` is the governed application write boundary for pricing publication.

A write requires an `AdminPrincipal` that has both:

- `commercial_config.write`;
- `global_scope=True`.

Tenant-scoped administrators and customer portal identities cannot publish platform pricing.

The code deliberately does not hardcode a human name, email or username. Production IAM is responsible for assigning the global pricing authority only to the FM administrative account designated by management.

## Existing pricing model preserved

The existing `CommercialPricingConfiguration` remains data-driven and versioned. It supports prices, plans, packages, add-ons, promotions, tenant overrides, billing cadences and external price references.

`CommercialPricingRegistry` continues to enforce optimistic version publication. The new administration service wraps that mutation with platform-level authorization.

## Next implementation boundary

The productive administrative CRUD/dashboard is still required before operational price management is complete. It must:

- persist published catalog versions durably;
- preserve history and audit actor/time/version;
- expose writes only through the platform administration authority;
- allow the public site/checkout/portal to read the active published catalog;
- never duplicate a commercial price in frontend/source code;
- support an intentionally unpriced state until management approves real prices after market research.

This work belongs to the upcoming commercial pricing administration block and must not be replaced by Git-tracked JSON as an operational control plane.

## Fiscal authority separation

Pricing changes cannot create homologation evidence, install secrets, approve certificates, create production grants or promote `PRODUCTION_APPROVED`.

## Certification rule

This correction is internally certified only when the exact final branch HEAD containing this document completes the full `FM NFCORE V1 CI` matrix with `success`.

No merge, deploy, DNS, cutover, real checkout or production activation is authorized by this document.
