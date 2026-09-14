import pytest

from kordena_fiscal.product.operations import (
    DEFAULT_RUNBOOKS,
    IncidentCategory,
    IncidentRunbook,
    IncidentSeverity,
    OperationsCatalog,
    OperationsContractError,
    ServiceHealth,
)


def test_operations_catalog_covers_every_required_incident() -> None:
    catalog = OperationsCatalog()
    assert {item.category for item in catalog.runbooks} == set(IncidentCategory)
    assert {item.severity for item in catalog.targets} == set(IncidentSeverity)


def test_unknown_outcome_runbook_forbids_blind_retry_semantically() -> None:
    runbook = OperationsCatalog().runbook(IncidentCategory.UNKNOWN_OUTCOME)
    assert "do not blind retry" in runbook.first_actions
    assert "run reconciliation" in runbook.first_actions


def test_security_and_disaster_recovery_are_sev1() -> None:
    catalog = OperationsCatalog()
    assert catalog.runbook(IncidentCategory.SECURITY).default_severity is IncidentSeverity.SEV1
    assert (
        catalog.runbook(IncidentCategory.DISASTER_RECOVERY).default_severity
        is IncidentSeverity.SEV1
    )


def test_targets_are_technical_not_contractual_sla_promises() -> None:
    catalog = OperationsCatalog()
    sev1 = catalog.target(IncidentSeverity.SEV1)
    assert sev1.acknowledge_minutes == 15
    assert "not contractual SLA" in sev1.description


def test_incomplete_runbook_catalog_fails_closed() -> None:
    with pytest.raises(OperationsContractError, match="every incident category"):
        OperationsCatalog(runbooks=DEFAULT_RUNBOOKS[:-1])


def test_runbook_requires_actions() -> None:
    with pytest.raises(OperationsContractError, match="first_actions"):
        IncidentRunbook(
            IncidentCategory.SECURITY,
            IncidentSeverity.SEV1,
            (),
            True,
        )


def test_health_contract_has_operational_and_outage_states() -> None:
    assert ServiceHealth.OPERATIONAL.value == "operational"
    assert ServiceHealth.MAJOR_OUTAGE.value == "major_outage"
    assert ServiceHealth.MAINTENANCE.value == "maintenance"
