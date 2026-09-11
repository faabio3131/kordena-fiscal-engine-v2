"""Capability and readiness authority for the public FM Fiscal Bridge."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from kordena_fiscal.domain import (
    BrazilianJurisdiction,
    FiscalDocumentKind,
    FiscalDomainError,
    FiscalEnvironment,
    FiscalValidationError,
)

from .jurisdiction import (
    FiscalActionCapability,
    FiscalCapabilityLevel,
    JurisdictionCapabilityMatrix,
    JurisdictionCapabilityRule,
)
from .rtc import TechnicalValidationMode

_BRIDGE_CONTRACT_VERSION = "1.0.0"
_ACTION_ORDER = (
    FiscalActionCapability.ISSUE,
    FiscalActionCapability.QUERY,
    FiscalActionCapability.CANCEL,
    FiscalActionCapability.INUTILIZE,
    FiscalActionCapability.CONTINGENCY,
    FiscalActionCapability.RECONCILE,
    FiscalActionCapability.ARCHIVE_REFERENCE,
)


class CapabilityReadinessError(FiscalDomainError):
    """Raised when an operation cannot be authorized by explicit readiness data."""


def _required(value: str, field_name: str, max_length: int) -> str:
    normalized = value.strip()
    if not normalized:
        raise FiscalValidationError(f"{field_name} must not be blank")
    if len(normalized) > max_length:
        raise FiscalValidationError(f"{field_name} exceeds max length {max_length}")
    return normalized


def _aware(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise FiscalValidationError(f"{field_name} must be timezone-aware")
    return value


def _required_execution_level(environment: FiscalEnvironment) -> FiscalCapabilityLevel:
    if environment is FiscalEnvironment.HOMOLOGATION:
        return FiscalCapabilityLevel.HOMOLOGATION_READY
    return FiscalCapabilityLevel.PRODUCTION_APPROVED


@dataclass(frozen=True, slots=True)
class CapabilityReadinessSnapshot:
    """Resolved, versioned capability statement for one explicit fiscal context."""

    jurisdiction: BrazilianJurisdiction
    document_kind: FiscalDocumentKind
    environment: FiscalEnvironment
    readiness: FiscalCapabilityLevel
    capability_version: str
    actions: tuple[FiscalActionCapability, ...]
    provenance: str
    validation_mode: TechnicalValidationMode
    effective_from: datetime
    effective_to: datetime | None

    def __post_init__(self) -> None:
        if not isinstance(self.jurisdiction, BrazilianJurisdiction):
            raise FiscalValidationError("jurisdiction must be BrazilianJurisdiction")
        if not isinstance(self.document_kind, FiscalDocumentKind):
            raise FiscalValidationError("document_kind must be FiscalDocumentKind")
        if not isinstance(self.environment, FiscalEnvironment):
            raise FiscalValidationError("environment must be FiscalEnvironment")
        if not isinstance(self.readiness, FiscalCapabilityLevel):
            raise FiscalValidationError("readiness must be FiscalCapabilityLevel")
        object.__setattr__(
            self,
            "capability_version",
            _required(self.capability_version, "capability_version", 64),
        )
        if not isinstance(self.actions, tuple) or not all(
            isinstance(action, FiscalActionCapability) for action in self.actions
        ):
            raise FiscalValidationError("actions must contain FiscalActionCapability values")
        if len(self.actions) != len(set(self.actions)):
            raise FiscalValidationError("actions must not contain duplicates")
        object.__setattr__(self, "provenance", _required(self.provenance, "provenance", 1000))
        if not isinstance(self.validation_mode, TechnicalValidationMode):
            raise FiscalValidationError("validation_mode must be TechnicalValidationMode")
        _aware(self.effective_from, "effective_from")
        if self.effective_to is not None:
            _aware(self.effective_to, "effective_to")
            if self.effective_to <= self.effective_from:
                raise FiscalValidationError("effective_to must be after effective_from")

    @property
    def public_capabilities(self) -> tuple[str, ...]:
        """Bridge-compatible document family plus explicitly declared actions."""

        return (self.document_kind.value, *(action.value for action in self.actions))

    def to_bridge_response(self, *, correlation_id: str) -> dict[str, object]:
        """Serialize exactly the public V1 capability response shape."""

        correlation = _required(correlation_id, "correlation_id", 256)
        return {
            "contract_version": _BRIDGE_CONTRACT_VERSION,
            "readiness": self.readiness.name,
            "capability_version": self.capability_version,
            "capabilities": list(self.public_capabilities),
            "correlation_id": correlation,
            "provenance": self.provenance,
        }


class CapabilityReadinessService:
    """Single authority for querying and enforcing declared fiscal capabilities."""

    def __init__(self, matrix: JurisdictionCapabilityMatrix) -> None:
        if not isinstance(matrix, JurisdictionCapabilityMatrix):
            raise FiscalValidationError("matrix must be JurisdictionCapabilityMatrix")
        self._matrix = matrix

    @staticmethod
    def _snapshot(
        rule: JurisdictionCapabilityRule,
        jurisdiction: BrazilianJurisdiction,
    ) -> CapabilityReadinessSnapshot:
        actions = tuple(
            action for action in _ACTION_ORDER if action in rule.capabilities
        )
        return CapabilityReadinessSnapshot(
            jurisdiction=jurisdiction,
            document_kind=rule.document_kind,
            environment=rule.environment,
            readiness=rule.capability_level,
            capability_version=rule.capability_version,
            actions=actions,
            provenance=rule.source_normative,
            validation_mode=rule.validation_mode,
            effective_from=rule.effective_from,
            effective_to=rule.effective_to,
        )

    def query(
        self,
        *,
        jurisdiction: BrazilianJurisdiction,
        document_kind: FiscalDocumentKind,
        environment: FiscalEnvironment,
        instant: datetime,
    ) -> CapabilityReadinessSnapshot:
        """Return the explicit declaration without upgrading or inferring readiness."""

        rule = self._matrix.resolve(
            jurisdiction=jurisdiction,
            document_kind=document_kind,
            environment=environment,
            instant=instant,
        )
        return self._snapshot(rule, jurisdiction)

    def require_action(
        self,
        *,
        jurisdiction: BrazilianJurisdiction,
        document_kind: FiscalDocumentKind,
        environment: FiscalEnvironment,
        instant: datetime,
        action: FiscalActionCapability,
    ) -> CapabilityReadinessSnapshot:
        """Fail closed unless readiness and the requested action are both explicit."""

        if not isinstance(action, FiscalActionCapability):
            raise FiscalValidationError("action must be FiscalActionCapability")
        rule = self._matrix.resolve(
            jurisdiction=jurisdiction,
            document_kind=document_kind,
            environment=environment,
            instant=instant,
            minimum_level=_required_execution_level(environment),
        )
        if action not in rule.capabilities:
            raise CapabilityReadinessError(
                f"fiscal action '{action.value}' is not declared for this context"
            )
        return self._snapshot(rule, jurisdiction)
