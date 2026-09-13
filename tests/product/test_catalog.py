import pytest

from kordena_fiscal.product.catalog import (
    DEFAULT_COMMERCIAL_CATALOG,
    CommercialCatalog,
    CommercialModule,
    ProductCatalogError,
)


def test_default_identity_is_fm_fiscal_not_kordena() -> None:
    identity = DEFAULT_COMMERCIAL_CATALOG.identity
    assert identity.product_id == "fm-fiscal"
    assert identity.name == "FM Fiscal"
    assert identity.company == "FM Tecnologia"
    assert "Kordena" not in identity.name


def test_default_catalog_has_configurable_editions_without_pricing() -> None:
    catalog = DEFAULT_COMMERCIAL_CATALOG
    assert {edition.edition_id for edition in catalog.editions} == {
        "foundation",
        "growth",
        "enterprise",
    }
    assert not hasattr(catalog, "price")
    assert all(not hasattr(edition, "price") for edition in catalog.editions)
    assert CommercialModule.CONTROL_PLANE in catalog.edition("enterprise").modules


def test_external_mapping_can_define_new_plan_without_code_change() -> None:
    catalog = CommercialCatalog.from_mapping(
        {
            "identity": {
                "product_id": "fm-fiscal",
                "name": "FM Fiscal",
                "company": "FM Tecnologia",
                "value_proposition": "Fiscal infrastructure for SaaS.",
                "target_audience": ["SaaS"],
                "differentiators": ["Fail-closed fiscal authority"],
            },
            "entitlements": [
                {
                    "entitlement_id": "documents.query",
                    "description": "Query documents",
                }
            ],
            "editions": [
                {
                    "edition_id": "partner-custom",
                    "display_name": "Partner Custom",
                    "modules": ["core", "bridge_api"],
                    "entitlement_ids": ["documents.query"],
                }
            ],
        }
    )

    assert catalog.edition("partner-custom").modules == (
        CommercialModule.CORE,
        CommercialModule.BRIDGE_API,
    )


def test_unknown_entitlement_reference_fails_closed() -> None:
    with pytest.raises(ProductCatalogError, match="unknown entitlements"):
        CommercialCatalog.from_mapping(
            {
                "identity": {
                    "product_id": "fm-fiscal",
                    "name": "FM Fiscal",
                    "company": "FM Tecnologia",
                    "value_proposition": "Fiscal infrastructure.",
                    "target_audience": ["SaaS"],
                    "differentiators": ["Governance"],
                },
                "entitlements": [
                    {
                        "entitlement_id": "documents.query",
                        "description": "Query documents",
                    }
                ],
                "editions": [
                    {
                        "edition_id": "bad",
                        "display_name": "Bad",
                        "modules": ["core"],
                        "entitlement_ids": ["unknown.capability"],
                    }
                ],
            }
        )


def test_duplicate_catalog_ids_fail_closed() -> None:
    payload = {
        "identity": {
            "product_id": "fm-fiscal",
            "name": "FM Fiscal",
            "company": "FM Tecnologia",
            "value_proposition": "Fiscal infrastructure.",
            "target_audience": ["SaaS"],
            "differentiators": ["Governance"],
        },
        "entitlements": [
            {"entitlement_id": "same", "description": "One"},
            {"entitlement_id": "same", "description": "Two"},
        ],
        "editions": [
            {
                "edition_id": "one",
                "display_name": "One",
                "modules": ["core"],
                "entitlement_ids": ["same"],
            }
        ],
    }
    with pytest.raises(ProductCatalogError, match="uniquely identified"):
        CommercialCatalog.from_mapping(payload)


def test_catalog_rejects_unknown_edition_and_entitlement_queries() -> None:
    with pytest.raises(ProductCatalogError, match="unknown edition"):
        DEFAULT_COMMERCIAL_CATALOG.edition("missing")
    with pytest.raises(ProductCatalogError, match="unknown entitlement"):
        DEFAULT_COMMERCIAL_CATALOG.entitlement("missing")
