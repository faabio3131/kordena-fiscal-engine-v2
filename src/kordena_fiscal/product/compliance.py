"""Technical data-governance package for commercial FM Fiscal readiness.

This module is not legal advice. Policies requiring legal confirmation are explicitly marked
LEGAL_VALIDATION_REQUIRED and do not claim a statutory retention period.
"""

from dataclasses import dataclass
from enum import StrEnum

LEGAL_VALIDATION_REQUIRED = "LEGAL_VALIDATION_REQUIRED"


class ComplianceContractError(ValueError):
    """Raised when a technical compliance policy is unsafe or incomplete."""


class DataCategory(StrEnum):
    ACCOUNT_IDENTITY = "account_identity"
    FISCAL_PROFILE = "fiscal_profile"
    FISCAL_DOCUMENT = "fiscal_document"
    AUDIT_TRAIL = "audit_trail"
    OPERATIONAL_TELEMETRY = "operational_telemetry"
    WEBHOOK_METADATA = "webhook_metadata"
    BILLING_METADATA = "billing_metadata"
    SECRET_REFERENCE = "secret_reference"
    BACKUP = "backup"


@dataclass(frozen=True, slots=True)
class RetentionRule:
    category: DataCategory
    retention_class: str
    customer_exportable: bool
    deletion_restricted: bool
    legal_hold_supported: bool
    legal_validation: str | None
    rationale: str

    def __post_init__(self) -> None:
        if not isinstance(self.category, DataCategory):
            raise ComplianceContractError("category must be DataCategory")
        if not self.retention_class.strip():
            raise ComplianceContractError("retention_class must not be blank")
        if not self.rationale.strip():
            raise ComplianceContractError("rationale must not be blank")
        if self.legal_validation not in {None, LEGAL_VALIDATION_REQUIRED}:
            raise ComplianceContractError("invalid legal_validation marker")


DEFAULT_RETENTION_MATRIX: tuple[RetentionRule, ...] = (
    RetentionRule(
        DataCategory.ACCOUNT_IDENTITY,
        "contract-lifecycle-plus-approved-retention",
        True,
        False,
        True,
        LEGAL_VALIDATION_REQUIRED,
        "Identity data follows account lifecycle and an approved post-contract retention policy.",
    ),
    RetentionRule(
        DataCategory.FISCAL_PROFILE,
        "effective-dated-history",
        True,
        True,
        True,
        LEGAL_VALIDATION_REQUIRED,
        "Historical fiscal configuration may be required to explain past document behavior.",
    ),
    RetentionRule(
        DataCategory.FISCAL_DOCUMENT,
        "fiscal-archive",
        True,
        True,
        True,
        LEGAL_VALIDATION_REQUIRED,
        "Fiscal documents are governed records and cannot follow ordinary account deletion rules.",
    ),
    RetentionRule(
        DataCategory.AUDIT_TRAIL,
        "security-and-compliance-audit",
        False,
        True,
        True,
        LEGAL_VALIDATION_REQUIRED,
        "Audit evidence requires integrity and restricted deletion.",
    ),
    RetentionRule(
        DataCategory.OPERATIONAL_TELEMETRY,
        "bounded-operational-retention",
        False,
        False,
        False,
        LEGAL_VALIDATION_REQUIRED,
        "Telemetry should be minimized, sanitized and retained only for an approved window.",
    ),
    RetentionRule(
        DataCategory.WEBHOOK_METADATA,
        "delivery-audit-retention",
        False,
        True,
        True,
        LEGAL_VALIDATION_REQUIRED,
        "Delivery evidence supports replay protection, support and audit without raw secrets.",
    ),
    RetentionRule(
        DataCategory.BILLING_METADATA,
        "commercial-record-retention",
        True,
        True,
        True,
        LEGAL_VALIDATION_REQUIRED,
        "Commercial billing metadata requires accounting/legal retention validation.",
    ),
    RetentionRule(
        DataCategory.SECRET_REFERENCE,
        "reference-only",
        False,
        True,
        False,
        None,
        "The product stores references/metadata, never raw private key or credential material.",
    ),
    RetentionRule(
        DataCategory.BACKUP,
        "encrypted-recovery-retention",
        False,
        True,
        True,
        LEGAL_VALIDATION_REQUIRED,
        "Backup retention and deletion propagation require an approved recovery/privacy policy.",
    ),
)


class TechnicalCompliancePackage:
    def __init__(
        self,
        rules: tuple[RetentionRule, ...] = DEFAULT_RETENTION_MATRIX,
    ) -> None:
        categories = tuple(rule.category for rule in rules)
        if set(categories) != set(DataCategory):
            raise ComplianceContractError("retention matrix must cover every data category")
        if len(categories) != len(set(categories)):
            raise ComplianceContractError("retention categories must be unique")
        self.rules = rules

    def rule(self, category: DataCategory) -> RetentionRule:
        return next(rule for rule in self.rules if rule.category is category)

    @property
    def legal_validation_items(self) -> tuple[DataCategory, ...]:
        return tuple(
            rule.category
            for rule in self.rules
            if rule.legal_validation == LEGAL_VALIDATION_REQUIRED
        )

    def exportable_categories(self) -> tuple[DataCategory, ...]:
        return tuple(rule.category for rule in self.rules if rule.customer_exportable)

    def deletable_without_special_process(self) -> tuple[DataCategory, ...]:
        return tuple(rule.category for rule in self.rules if not rule.deletion_restricted)
