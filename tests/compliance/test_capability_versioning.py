from datetime import UTC, datetime

from kordena_fiscal.compliance import (
    FiscalActionCapability,
    FiscalCapabilityLevel,
    JurisdictionCapabilityRule,
    TechnicalValidationMode,
)
from kordena_fiscal.domain import FiscalDocumentKind, FiscalEnvironment


def _rule(
    *,
    capabilities: frozenset[FiscalActionCapability],
    source_normative: str = "normative-a",
) -> JurisdictionCapabilityRule:
    return JurisdictionCapabilityRule(
        rule_id="sp-nfe-versioned",
        version=7,
        state_code="SP",
        document_kind=FiscalDocumentKind.NFE,
        environment=FiscalEnvironment.HOMOLOGATION,
        capability_level=FiscalCapabilityLevel.HOMOLOGATION_READY,
        validation_mode=TechnicalValidationMode.TOLERANT,
        effective_from=datetime(2026, 1, 1, tzinfo=UTC),
        source_normative=source_normative,
        capabilities=capabilities,
    )


def test_capability_version_is_stable_for_identical_rule_semantics() -> None:
    first = _rule(capabilities=frozenset({FiscalActionCapability.ISSUE}))
    second = _rule(capabilities=frozenset({FiscalActionCapability.ISSUE}))

    assert first.capability_version == second.capability_version


def test_capability_version_changes_if_actions_change_without_version_bump() -> None:
    issue_only = _rule(capabilities=frozenset({FiscalActionCapability.ISSUE}))
    issue_and_cancel = _rule(
        capabilities=frozenset(
            {FiscalActionCapability.ISSUE, FiscalActionCapability.CANCEL}
        )
    )

    assert issue_only.version == issue_and_cancel.version
    assert issue_only.capability_version != issue_and_cancel.capability_version


def test_capability_version_changes_if_provenance_changes_without_version_bump() -> None:
    first = _rule(
        capabilities=frozenset({FiscalActionCapability.QUERY}),
        source_normative="normative-a",
    )
    second = _rule(
        capabilities=frozenset({FiscalActionCapability.QUERY}),
        source_normative="normative-b",
    )

    assert first.version == second.version
    assert first.capability_version != second.capability_version
