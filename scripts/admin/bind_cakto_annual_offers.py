"""Governed one-off script: bind the 4 new Cakto annual offers and republish pricing.

Run inside the nfcore-api container, where DATABASE_URL is already present in the
process environment. Never prints or logs the DSN or any other credential.

Step 1 (read-only, default): print existing Cakto bindings (plan_id, external ids,
entitlement_ids) and the current pricing catalog's annual price_ids, so the operator
can confirm before any write.

Step 2 (write, requires --apply): set the 4 new annual Cakto bindings (same plan_id
and entitlement_ids as the matching monthly binding, new external_product_id/
external_offer_id) and publish a new pricing catalog version where each annual
price's external_price_reference points at its new binding. Monthly bindings and
monthly prices are left untouched.
"""

from __future__ import annotations

import argparse
import os
from dataclasses import replace
from datetime import UTC, datetime

from kordena_fiscal.control_plane.cakto_checkout import CaktoCheckoutAdministrationService
from kordena_fiscal.control_plane.models import AdminPrincipal, ControlPlanePermission
from kordena_fiscal.control_plane.pricing_admin import CommercialPricingAdministrationService
from kordena_fiscal.persistence.cakto import postgres_cakto_commercial_database
from kordena_fiscal.persistence.postgres import PostgresFiscalDatabase
from kordena_fiscal.product.cakto import CaktoPlanBinding
from kordena_fiscal.product.pricing import BillingCadence

# plan_id -> (external_product_id, external_offer_id) for the new annual Cakto products
ANNUAL_BINDINGS: dict[str, tuple[str, str]] = {
    "starter": ("b271c9b1-ae53-42c4-aafc-85b5a4c976b3", "6geyuwq"),
    "pro": ("6e897678-9357-4a2a-b1ec-163a1e687b92", "inahojr"),
    "business": ("e55e1bbc-0b52-483b-8f2c-db7afcf9a6b5", "h7m7vny"),
    "enterprise": ("c98d67be-c018-4077-b33f-d75329e40a98", "ttbn697"),
}


def _actor() -> AdminPrincipal:
    return AdminPrincipal(
        actor_id="ops-script-bind-cakto-annual",
        permissions=frozenset({ControlPlanePermission.COMMERCIAL_CONFIG_WRITE}),
        global_scope=True,
    )


def run(*, apply: bool) -> None:
    dsn = os.environ["DATABASE_URL"]
    database = PostgresFiscalDatabase(dsn)
    try:
        actor = _actor()
        cakto_database = postgres_cakto_commercial_database(database)
        checkout = CaktoCheckoutAdministrationService(cakto_database)
        pricing_administration = CommercialPricingAdministrationService(database.pricing_catalog())

        print("== current cakto bindings ==")
        existing = checkout.bindings(actor=actor)
        monthly_entitlements: dict[str, tuple[str, ...]] = {}
        for binding in existing:
            print(
                f"plan_id={binding.plan_id} product={binding.external_product_id} "
                f"offer={binding.external_offer_id} enabled={binding.enabled} "
                f"entitlements={binding.entitlement_ids}"
            )
            monthly_entitlements[binding.plan_id] = binding.entitlement_ids

        configuration = pricing_administration.current
        if configuration is None:
            print("no pricing configuration is currently published")
            return

        print("\n== current prices ==")
        annual_price_ids: dict[str, str] = {}
        for plan in configuration.plans:
            for price_id in plan.price_ids:
                price = next((p for p in configuration.prices if p.price_id == price_id), None)
                if price is None:
                    continue
                print(
                    f"plan_id={plan.plan_id} price_id={price.price_id} "
                    f"cadence={price.cadence} "
                    f"external_price_reference={price.external_price_reference}"
                )
                if price.cadence == BillingCadence.ANNUAL:
                    annual_price_ids[plan.plan_id] = price.price_id

        missing_plans = set(ANNUAL_BINDINGS) - set(monthly_entitlements)
        if missing_plans:
            raise RuntimeError(f"no existing monthly binding found for plans: {missing_plans}")
        missing_prices = set(ANNUAL_BINDINGS) - set(annual_price_ids)
        if missing_prices:
            raise RuntimeError(f"no annual price found for plans: {missing_prices}")

        if not apply:
            print("\n(dry run — pass --apply to write the 4 new bindings and republish pricing)")
            return

        print("\n== setting new annual bindings ==")
        for plan_id, (product_id, offer_id) in ANNUAL_BINDINGS.items():
            binding = CaktoPlanBinding(
                external_product_id=product_id,
                external_offer_id=offer_id,
                plan_id=plan_id,
                entitlement_ids=monthly_entitlements[plan_id],
                enabled=True,
            )
            persisted = checkout.set_binding(actor=actor, binding=binding)
            print(
                f"bound plan_id={plan_id} -> "
                f"{persisted.external_product_id}/{persisted.external_offer_id}"
            )

        print("\n== republishing pricing catalog ==")
        new_prices = []
        for price in configuration.prices:
            plan_id = next(
                (plan.plan_id for plan in configuration.plans if price.price_id in plan.price_ids),
                None,
            )
            if (
                plan_id in ANNUAL_BINDINGS
                and price.cadence == BillingCadence.ANNUAL
                and annual_price_ids.get(plan_id) == price.price_id
            ):
                product_id, offer_id = ANNUAL_BINDINGS[plan_id]
                new_prices.append(
                    replace(price, external_price_reference=f"cakto://{product_id}/{offer_id}")
                )
            else:
                new_prices.append(price)

        new_configuration = replace(
            configuration,
            prices=tuple(new_prices),
            version=configuration.version + 1,
        )
        published = pricing_administration.publish(
            actor=actor,
            configuration=new_configuration,
            expected_version=configuration.version,
            correlation_id="bind-cakto-annual-offers",
            published_at=datetime.now(UTC),
        )
        print(f"published pricing catalog version={published.version}")
    finally:
        database.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    run(apply=bool(args.apply))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
