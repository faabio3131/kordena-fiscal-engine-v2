"""Technical homologation evidence gates that never replace readiness authority."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from kordena_fiscal.compliance import (
    CapabilityReadinessError,
    CapabilityReadinessService,
    CapabilityReadinessSnapshot,
    FiscalActionCapability,
    FiscalCapabilityLevel,
)
from kordena_fiscal.domain import (
    BrazilianJurisdiction,
    FiscalDocumentKind,
    FiscalDomainError,
    FiscalEnvironment,
    FiscalValidationError,
)
from kordena_fiscal.gateway import ProviderOperation


class HomologationGateError(FiscalDomainError):
    """Base error for explicit technical homologation gate failures."""


class HomologationGateNotConfiguredError(HomologationGateError):
    """No technical gate is configured for the exact provider/context tuple."""


class TechnicalGateState(StrEnum):
    NOT_CONFIGURED = "not_configured"
    CONTRACT_READY = "contract_ready"
    TECHNICALLY_CERTIFIED = "technically_certified"


_OPERATION_ACTION: dict[ProviderOperation, FiscalActionCapability] = {
    ProviderOperation.AUTHORIZE: FiscalActionCapability.ISSUE,
    ProviderOperation.QUERY: FiscalActionCapability.QUERY,
    ProviderOperation.CANCEL: FiscalActionCapability.CANCEL,
    ProviderOperation.INUTILIZE: FiscalActionCapability.INUTILIZE,
    ProviderOperation.STATUS: FiscalActionCapability.QUERY,
}


def _required(value: str, field_name: str) -> str:
    normalized = value.strip().lower()
    if not normalized:
        raise FiscalValidationError(f"{field_name} must not be blank")
    if len(normalized) > 128:
        raise FiscalValidationError(f"{field_name} exceeds max length 128")
    return normalized


@dataclass(frozen=True, slots=True)
class HomologationGateKey:
    provider_id: str
    document_kind: FiscalDocumentKind
    jurisdiction: BrazilianJurisdiction
    environment: FiscalEnvironment
    operation: ProviderOperation

    def __post_init__(self) -> None:
        object.__setattr__(self, "provider_id", _required(self.provider_id, "provider_id"))
        if not isinstance(self.document_kind, FiscalDocumentKind):
            raise FiscalValidationError("document_kind must be FiscalDocumentKind")
        if not isinstance(self.jurisdiction, BrazilianJurisdiction):
            raise FiscalValidationError("jurisdiction must be BrazilianJurisdiction")
        if not isinstance(self.environment, FiscalEnvironment):
            raise FiscalValidationError("environment must be FiscalEnvironment")
        if not isinstance(self.operation, ProviderOperation):
            raise FiscalValidationError("operation must be ProviderOperation")
        if (
            self.document_kind is FiscalDocumentKind.NFSE
            and self.jurisdiction.municipality_ibge_code is None
        ):
            raise FiscalValidationError(
                "NFSe homologation gate requires municipality_ibge_code"
            )


@dataclass(frozen=True, slots=True)
class HomologationEvidence:
    """Technical evidence only; no field can promote fiscal readiness."""

    provider_adapter_available: bool
    credentials_reference_configured: bool
    signer_capability: bool
    csc_reference_configured: bool
    transport_configured: bool
    resilience_certified: bool
    contract_tests_certified: bool
    jurisdiction_mapping: bool
    operation_supported: bool

    def missing(
        self,
        *,
        requires_signer: bool,
        requires_csc: bool,
    ) -> tuple[str, ...]:
        required = {
            "provider_adapter_available": self.provider_adapter_available,
            "credentials_reference_configured": self.credentials_reference_configured,
            "transport_configured": self.transport_configured,
            "resilience_certified": self.resilience_certified,
            "contract_tests_certified": self.contract_tests_certified,
            "jurisdiction_mapping": self.jurisdiction_mapping,
            "operation_supported": self.operation_supported,
        }
        if requires_signer:
            required["signer_capability"] = self.signer_capability
        if requires_csc:
            required["csc_reference_configured"] = self.csc_reference_configured
        return tuple(name for name, present in required.items() if not present)


@dataclass(frozen=True, slots=True)
class TechnicalHomologationRule:
    key: HomologationGateKey
    evidence: HomologationEvidence
    requires_signer: bool = False
    requires_csc: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.key, HomologationGateKey):
            raise FiscalValidationError("key must be HomologationGateKey")
        if not isinstance(self.evidence, HomologationEvidence):
            raise FiscalValidationError("evidence must be HomologationEvidence")
        if self.requires_csc and self.key.document_kind is not FiscalDocumentKind.NFCE:
            raise FiscalValidationError("CSC requirement is only valid for NFCe gates")

    @property
    def missing_evidence(self) -> tuple[str, ...]:
        return self.evidence.missing(
            requires_signer=self.requires_signer,
            requires_csc=self.requires_csc,
        )

    @property
    def technical_state(self) -> TechnicalGateState:
        if not self.evidence.provider_adapter_available or not self.evidence.jurisdiction_mapping:
            return TechnicalGateState.NOT_CONFIGURED
        if self.missing_evidence:
            return TechnicalGateState.CONTRACT_READY
        return TechnicalGateState.TECHNICALLY_CERTIFIED


class TechnicalHomologationMatrix:
    """Exact provider/context technical gates with no implicit default provider."""

    def __init__(self, rules: tuple[TechnicalHomologationRule, ...]) -> None:
        if not rules or not all(isinstance(item, TechnicalHomologationRule) for item in rules):
            raise FiscalValidationError("rules must contain TechnicalHomologationRule values")
        keys = [item.key for item in rules]
        if len(keys) != len(set(keys)):
            raise FiscalValidationError("homologation gate keys must be unique")
        self._rules = {item.key: item for item in rules}

    def resolve(self, key: HomologationGateKey) -> TechnicalHomologationRule:
        if not isinstance(key, HomologationGateKey):
            raise FiscalValidationError("key must be HomologationGateKey")
        rule = self._rules.get(key)
        if rule is None:
            raise HomologationGateNotConfiguredError(
                "technical homologation gate is not configured for exact provider context"
            )
        return rule


@dataclass(frozen=True, slots=True)
class HomologationGateResult:
    key: HomologationGateKey
    technical_state: TechnicalGateState
    readiness: FiscalCapabilityLevel
    readiness_snapshot: CapabilityReadinessSnapshot
    missing_evidence: tuple[str, ...]
    execution_authorized: bool

    @property
    def homologation_ready(self) -> bool:
        """Combined view only; readiness itself remains owned by the central authority."""

        return (
            self.key.environment is FiscalEnvironment.HOMOLOGATION
            and self.technical_state is TechnicalGateState.TECHNICALLY_CERTIFIED
            and self.execution_authorized
            and self.readiness >= FiscalCapabilityLevel.HOMOLOGATION_READY
        )


class HomologationGateEvaluator:
    """Combine technical evidence with a read-only query/enforcement of central readiness."""

    def __init__(
        self,
        *,
        matrix: TechnicalHomologationMatrix,
        readiness: CapabilityReadinessService,
    ) -> None:
        self._matrix = matrix
        self._readiness = readiness

    def evaluate(
        self,
        key: HomologationGateKey,
        *,
        instant: datetime,
    ) -> HomologationGateResult:
        rule = self._matrix.resolve(key)
        snapshot = self._readiness.query(
            jurisdiction=key.jurisdiction,
            document_kind=key.document_kind,
            environment=key.environment,
            instant=instant,
        )
        authorized = False
        if rule.technical_state is TechnicalGateState.TECHNICALLY_CERTIFIED:
            try:
                self._readiness.require_action(
                    jurisdiction=key.jurisdiction,
                    document_kind=key.document_kind,
                    environment=key.environment,
                    instant=instant,
                    action=_OPERATION_ACTION[key.operation],
                )
            except CapabilityReadinessError:
                authorized = False
            else:
                authorized = True
        return HomologationGateResult(
            key=key,
            technical_state=rule.technical_state,
            readiness=snapshot.readiness,
            readiness_snapshot=snapshot,
            missing_evidence=rule.missing_evidence,
            execution_authorized=authorized,
        )
