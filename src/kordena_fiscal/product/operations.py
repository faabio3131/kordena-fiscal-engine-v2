"""Technical support, incident and service-health contracts for FM Fiscal."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class OperationsContractError(ValueError):
    """Raised when an operational contract is incomplete."""


class IncidentSeverity(StrEnum):
    SEV1 = "sev1"
    SEV2 = "sev2"
    SEV3 = "sev3"
    SEV4 = "sev4"


class IncidentCategory(StrEnum):
    CERTIFICATE_EXPIRATION = "certificate_expiration"
    PROVIDER_OUTAGE = "provider_outage"
    SEFAZ_OUTAGE = "sefaz_outage"
    NFSE_OUTAGE = "nfse_outage"
    QUEUE_BACKLOG = "queue_backlog"
    UNKNOWN_OUTCOME = "unknown_outcome"
    SEQUENCE_GAP = "sequence_gap"
    RECONCILIATION = "reconciliation"
    SECURITY = "security"
    CUSTOMER_ONBOARDING = "customer_onboarding"
    DISASTER_RECOVERY = "disaster_recovery"


class ServiceHealth(StrEnum):
    OPERATIONAL = "operational"
    DEGRADED = "degraded"
    PARTIAL_OUTAGE = "partial_outage"
    MAJOR_OUTAGE = "major_outage"
    MAINTENANCE = "maintenance"


@dataclass(frozen=True, slots=True)
class TechnicalServiceTarget:
    severity: IncidentSeverity
    acknowledge_minutes: int
    update_minutes: int
    description: str

    def __post_init__(self) -> None:
        if not isinstance(self.severity, IncidentSeverity):
            raise OperationsContractError("severity must be IncidentSeverity")
        for field_name in ("acknowledge_minutes", "update_minutes"):
            value = getattr(self, field_name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                raise OperationsContractError(f"{field_name} must be integer >= 1")
        if not self.description.strip():
            raise OperationsContractError("description must not be blank")


@dataclass(frozen=True, slots=True)
class IncidentRunbook:
    category: IncidentCategory
    default_severity: IncidentSeverity
    first_actions: tuple[str, ...]
    escalation_required: bool

    def __post_init__(self) -> None:
        if not isinstance(self.category, IncidentCategory):
            raise OperationsContractError("category must be IncidentCategory")
        if not isinstance(self.default_severity, IncidentSeverity):
            raise OperationsContractError("default_severity must be IncidentSeverity")
        if not self.first_actions or any(not item.strip() for item in self.first_actions):
            raise OperationsContractError("first_actions must be non-empty")
        if not isinstance(self.escalation_required, bool):
            raise OperationsContractError("escalation_required must be bool")


DEFAULT_TECHNICAL_TARGETS: tuple[TechnicalServiceTarget, ...] = (
    TechnicalServiceTarget(
        IncidentSeverity.SEV1,
        15,
        30,
        "Technical target for major fiscal-authority or security unavailability; not contractual SLA.",
    ),
    TechnicalServiceTarget(
        IncidentSeverity.SEV2,
        30,
        60,
        "Technical target for material degradation without complete authority loss.",
    ),
    TechnicalServiceTarget(
        IncidentSeverity.SEV3,
        240,
        480,
        "Technical target for limited-impact operational incidents.",
    ),
    TechnicalServiceTarget(
        IncidentSeverity.SEV4,
        480,
        1440,
        "Technical target for low-impact requests and non-urgent defects.",
    ),
)


DEFAULT_RUNBOOKS: tuple[IncidentRunbook, ...] = (
    IncidentRunbook(
        IncidentCategory.CERTIFICATE_EXPIRATION,
        IncidentSeverity.SEV2,
        ("identify affected scope", "block unsafe signing", "request governed renewal reference"),
        True,
    ),
    IncidentRunbook(
        IncidentCategory.PROVIDER_OUTAGE,
        IncidentSeverity.SEV2,
        ("open circuit if threshold reached", "preserve idempotency", "start reconciliation"),
        True,
    ),
    IncidentRunbook(
        IncidentCategory.SEFAZ_OUTAGE,
        IncidentSeverity.SEV2,
        ("confirm official availability", "apply governed contingency only if capable", "reconcile"),
        True,
    ),
    IncidentRunbook(
        IncidentCategory.NFSE_OUTAGE,
        IncidentSeverity.SEV2,
        ("identify municipality/provider", "pause unsafe mutation", "reconcile pending outcomes"),
        True,
    ),
    IncidentRunbook(
        IncidentCategory.QUEUE_BACKLOG,
        IncidentSeverity.SEV2,
        ("measure backlog partition", "apply backpressure", "inspect retry and dead-letter state"),
        True,
    ),
    IncidentRunbook(
        IncidentCategory.UNKNOWN_OUTCOME,
        IncidentSeverity.SEV2,
        ("do not blind retry", "query provider state", "run reconciliation"),
        True,
    ),
    IncidentRunbook(
        IncidentCategory.SEQUENCE_GAP,
        IncidentSeverity.SEV1,
        ("freeze affected sequence", "audit allocations", "reconcile lifecycle before resuming"),
        True,
    ),
    IncidentRunbook(
        IncidentCategory.RECONCILIATION,
        IncidentSeverity.SEV2,
        ("isolate fiscal partition", "compare canonical state", "preserve provenance"),
        True,
    ),
    IncidentRunbook(
        IncidentCategory.SECURITY,
        IncidentSeverity.SEV1,
        ("contain credential scope", "rotate affected references", "preserve security audit trail"),
        True,
    ),
    IncidentRunbook(
        IncidentCategory.CUSTOMER_ONBOARDING,
        IncidentSeverity.SEV3,
        ("resume from checkpoint", "validate missing reference", "do not bypass readiness"),
        False,
    ),
    IncidentRunbook(
        IncidentCategory.DISASTER_RECOVERY,
        IncidentSeverity.SEV1,
        ("activate recovery runbook", "restore authority state", "validate before reopening writers"),
        True,
    ),
)


class OperationsCatalog:
    def __init__(
        self,
        *,
        targets: tuple[TechnicalServiceTarget, ...] = DEFAULT_TECHNICAL_TARGETS,
        runbooks: tuple[IncidentRunbook, ...] = DEFAULT_RUNBOOKS,
    ) -> None:
        severities = tuple(target.severity for target in targets)
        categories = tuple(runbook.category for runbook in runbooks)
        if set(severities) != set(IncidentSeverity):
            raise OperationsContractError("technical targets must cover every severity")
        if set(categories) != set(IncidentCategory):
            raise OperationsContractError("runbooks must cover every incident category")
        if len(categories) != len(set(categories)):
            raise OperationsContractError("incident categories must be unique")
        self.targets = targets
        self.runbooks = runbooks

    def runbook(self, category: IncidentCategory) -> IncidentRunbook:
        return next(item for item in self.runbooks if item.category is category)

    def target(self, severity: IncidentSeverity) -> TechnicalServiceTarget:
        return next(item for item in self.targets if item.severity is severity)
