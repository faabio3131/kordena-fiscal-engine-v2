"""Verify that the approved four-plan offer can actually provision a canonical trial.

All database writes are confined to a disposable local PostgreSQL *_test schema.
No production DB, webhooks, provider API, payment or fiscal issuance is touched.
"""
from __future__ import annotations

import os
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict

from kordena_fiscal.control_plane.models import AdminPrincipal, ControlPlanePermission
from kordena_fiscal.persistence.postgres import PostgresFiscalDatabase
from kordena_fiscal.product.billing import SubscriptionStatus
from kordena_fiscal.product.catalog import DEFAULT_COMMERCIAL_CATALOG, CommercialModule
from kordena_fiscal.product.commercial_plan_candidate import build_canonical_candidate
from kordena_fiscal.runtime.composition import build_postgres_runtime_composition
from kordena_fiscal.security.human_identity import PortalRole

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "config" / "commercial" / "plans.json"
NOW = datetime(2026, 11, 11, 16, tzinfo=UTC)


def _published_config():
    candidate = build_canonical_candidate(CONFIG)
    return replace(
        candidate,
        plans=tuple(replace(item, enabled=True) for item in candidate.plans),
    )


def test_approved_offer_all_four_plans_resolve_one_canonical_feature_edition() -> None:
    config = _published_config()
    assert {plan.plan_id for plan in config.plans} == {
        "starter", "pro", "business", "enterprise",
    }
    for plan in config.plans:
        edition = DEFAULT_COMMERCIAL_CATALOG.edition(plan.edition_id)
        assert edition.edition_id == "nfcore-total-feature-parity"
        assert set(edition.modules) == set(CommercialModule)
        assert plan.trial_days == 14
        assert len(plan.price_ids) == 2


@pytest.fixture
def local_db() -> PostgresFiscalDatabase:
    dsn = os.environ.get("NFCORE_TEST_POSTGRES_DSN", "").strip()
    if not dsn:
        pytest.skip("local NFCORE_TEST_POSTGRES_DSN required")
    conninfo = conninfo_to_dict(dsn)
    if (
        conninfo.get("host") not in {"localhost", "127.0.0.1", "::1"}
        or not str(conninfo.get("dbname", "")).endswith("_test")
    ):
        pytest.fail("NEVER create trial fixtures outside local *_test PostgreSQL")
    schema = "nfv1_four_plan_trial_" + uuid4().hex
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
    uri = urlsplit(dsn)
    qs = dict(parse_qsl(uri.query, keep_blank_values=True))
    qs["options"] = f"-c search_path={schema}"
    isolated = urlunsplit(uri._replace(query=urlencode(qs, quote_via=quote)))
    database = None
    try:
        database = PostgresFiscalDatabase(isolated)
        database.initialize()
        database.require_current_schema()
        yield database
    finally:
        if database is not None:
            database.close()
        with psycopg.connect(dsn, autocommit=True) as conn:
            conn.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))


def test_approved_four_plans_each_create_one_unbilled_14_day_trial(
    local_db: PostgresFiscalDatabase,
) -> None:
    comp = build_postgres_runtime_composition(local_db)
    config = _published_config()
    comp.pricing_administration.publish(
        actor=AdminPrincipal(
            actor_id="synthetic-pricing-admin",
            permissions=frozenset({ControlPlanePermission.COMMERCIAL_CONFIG_WRITE}),
            global_scope=True,
        ),
        configuration=config,
        expected_version=None,
        correlation_id="synthetic-four-plan-trial",
        published_at=NOW,
    )
    for plan in config.plans:
        buyer_email = f"synthetic-{plan.plan_id}@example.test"
        started = comp.commercial_trial.begin(
            plan_id=plan.plan_id,
            price_id=plan.price_ids[0],
            buyer_email=buyer_email,
            legal_name=f"Synthetic {plan.plan_id} Customer LTDA",
            idempotency_key=f"four-plan-trial-{plan.plan_id}-20261111",
            now=NOW + timedelta(minutes=1),
        )
        assert started.replay is False
        assert started.purchase.provider_id == "nfcore-trial"
        assert started.purchase.billing_status is SubscriptionStatus.TRIAL
        assert started.purchase.external_subscription_id is None
        assert started.purchase.external_customer_id is None
        assert started.subscription.checkpoint.status is SubscriptionStatus.TRIAL
        assert started.subscription.checkpoint.period_end - (
            started.subscription.checkpoint.period_start
        ) == timedelta(days=14)
        assert started.activation_reset is not None
        account = local_db.human_accounts().by_email(buyer_email)
        assert account is not None
        assert account.role is PortalRole.OWNER
        assert account.platform_admin is False
        assert account.tenant_id == started.purchase.tenant_id
        assert set(started.subscription.checkpoint.plan.entitlement_ids) == set(
            DEFAULT_COMMERCIAL_CATALOG.edition(plan.edition_id).entitlement_ids
        )
        with local_db.unit_of_work() as uow:
            organization = uow.control_plane.get_organization(account.tenant_id)
        assert organization is not None
        assert organization.legal_name == f"Synthetic {plan.plan_id} Customer LTDA"
