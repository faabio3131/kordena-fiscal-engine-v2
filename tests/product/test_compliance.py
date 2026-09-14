import pytest

from kordena_fiscal.product.compliance import (
    LEGAL_VALIDATION_REQUIRED,
    ComplianceContractError,
    DataCategory,
    RetentionRule,
    TechnicalCompliancePackage,
)


def test_retention_matrix_covers_every_data_category() -> None:
    package = TechnicalCompliancePackage()
    assert {rule.category for rule in package.rules} == set(DataCategory)


def test_fiscal_documents_and_audit_require_restricted_deletion() -> None:
    package = TechnicalCompliancePackage()
    assert package.rule(DataCategory.FISCAL_DOCUMENT).deletion_restricted is True
    assert package.rule(DataCategory.AUDIT_TRAIL).deletion_restricted is True


def test_secret_material_policy_is_reference_only_and_not_exportable() -> None:
    rule = TechnicalCompliancePackage().rule(DataCategory.SECRET_REFERENCE)
    assert rule.retention_class == "reference-only"
    assert rule.customer_exportable is False
    assert "never raw private key" in rule.rationale


def test_legal_validation_items_are_explicit_not_invented_periods() -> None:
    package = TechnicalCompliancePackage()
    assert DataCategory.FISCAL_DOCUMENT in package.legal_validation_items
    assert DataCategory.BILLING_METADATA in package.legal_validation_items
    for category in package.legal_validation_items:
        assert package.rule(category).legal_validation == LEGAL_VALIDATION_REQUIRED


def test_customer_export_is_scoped_to_supported_categories() -> None:
    exportable = TechnicalCompliancePackage().exportable_categories()
    assert DataCategory.ACCOUNT_IDENTITY in exportable
    assert DataCategory.FISCAL_PROFILE in exportable
    assert DataCategory.FISCAL_DOCUMENT in exportable
    assert DataCategory.SECRET_REFERENCE not in exportable
    assert DataCategory.AUDIT_TRAIL not in exportable


def test_incomplete_retention_matrix_fails_closed() -> None:
    package = TechnicalCompliancePackage()
    with pytest.raises(ComplianceContractError, match="every data category"):
        TechnicalCompliancePackage(package.rules[:-1])


def test_invalid_legal_marker_is_rejected() -> None:
    with pytest.raises(ComplianceContractError, match="legal_validation"):
        RetentionRule(
            DataCategory.ACCOUNT_IDENTITY,
            "test",
            True,
            False,
            False,
            "LEGAL_APPROVED",
            "Synthetic test rationale",
        )
