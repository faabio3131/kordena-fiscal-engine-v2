from __future__ import annotations

import os
from datetime import UTC, datetime

import psycopg
import pytest

from kordena_fiscal.persistence.cakto import postgres_cakto_commercial_database
from kordena_fiscal.persistence.postgres import PostgresFiscalDatabase
from kordena_fiscal.product.cakto import CaktoPlanBinding

DSN_ENV = "NFCORE_TEST_POSTGRES_DSN"
NOW = datetime(2026, 9, 15, 20, 15, tzinfo=UTC)


def _dsn() -> str:
    value = os.environ.get(DSN_ENV, "").strip()
    if not value:
        pytest.skip(f"{DSN_ENV} is required for real PostgreSQL certification")
    return value


def test_cakto_schema_and_plan_mapping_are_durable_on_postgres() -> None:
    dsn = _dsn()
    with psycopg.connect(dsn, autocommit=True) as connection:
        connection.execute("DROP SCHEMA public CASCADE")
        connection.execute("CREATE SCHEMA public")
    core = PostgresFiscalDatabase(dsn)
    try:
        core.initialize()
        cakto = postgres_cakto_commercial_database(core)
        assert cakto.initialize() is True
        assert cakto.initialize() is False
        binding = CaktoPlanBinding(
            external_product_id="product-postgres",
            external_offer_id="offer-postgres",
            plan_id="pro",
            entitlement_ids=("portal",),
        )
        with cakto() as uow:
            uow.commercial.put_cakto_plan_binding(binding)
            uow.commit()
        with cakto() as uow:
            restored = uow.commercial.resolve_cakto_plan_binding(
                "product-postgres", "offer-postgres"
            )
        assert restored == binding
    finally:
        core.close()
