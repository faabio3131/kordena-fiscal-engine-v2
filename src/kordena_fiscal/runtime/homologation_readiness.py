"""Durable HOMOLOGATION readiness assessment for zero-code customer configuration.

This runtime service verifies that persisted customer configuration matches a
platform provider descriptor and separates internal technical certification from
external official evidence. It never promotes production readiness.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from kordena_fiscal.control_plane import SecretReferenceKind
from kordena_fiscal.control_plane.commercial import ConfiguredFiscalOperation
from kordena_fiscal.control_plane.commercial_models import HomologationEvidenceRecord
from kordena_fiscal.domain import (
    BrazilianJurisdiction,
    ExecutionScope,
    FiscalDocumentKind,
    FiscalEnvironment,
    FiscalValidationError,
)
from kordena_fiscal.gateway import ProviderDescriptor, ProviderOperation
from kordena_fiscal.gateway.production_activation import (
    HumanProductionApproval,
    ProductionActivationKey,
    ProductionActivationRecord,
    ProductionActivationState,
)
from kordena_fiscal.homologation import (
    HomologationEvidence,
    HomologationGateKey,
    TechnicalGateState,
    TechnicalHomologationRule,
)
from kordena_fiscal.persistence.ports import FiscalUnitOfWorkFactory


@dataclass(frozen=True, slots=True)
class HomologationEnvironmentReadinessAssessment:
    """One exact customer/provider capability assessment with no secret material."""

    scope: ExecutionScope
    document_kind: FiscalDocumentKind
    jurisdiction: BrazilianJurisdiction
    operation: ProviderOperation
    provider_id: str | None
    missing_configuration: tuple[str, ...]
    technical_state: TechnicalGateState
    external_official: bool
    external_evidence_id: str | None
    external_recorded_at: datetime | None = None

    @property
    def internally_ready(self) -> bool:
        return (
            self.scope.environment is FiscalEnvironment.HOMOLOGATION
            and not self.missing_configuration
            and self.technical_state is TechnicalGateState.TECHNICALLY_CERTIFIED
        )

    @property
    def officially_homologated(self) -> bool:
        return (
            self.internally_ready
            and self.external_official
            and self.external_evidence_id is not None
            and self.external_recorded_at is not None
        )


class ExternalReadinessFlag(StrEnum):
    """Read-only reconciliation flags; none of them grants fiscal authority."""

    READY_INTERNAL = "ready_internal"
    MISSING_EXTERNAL_CREDENTIAL = "missing_external_credential"
    MISSING_OFFICIAL_EVIDENCE = "missing_official_evidence"
    MISSING_PILOT_AUTHORIZATION = "missing_pilot_authorization"
    MISSING_HUMAN_APPROVAL = "missing_human_approval"
    BLOCKED_EXTERNAL = "blocked_external"


@dataclass(frozen=True, slots=True)
class ExternalReadinessCellReport:
    """Exact-cell projection over canonical readiness/approval/activation objects."""

    assessment: HomologationEnvironmentReadinessAssessment
    flags: frozenset[ExternalReadinessFlag]
    pilot_authorized: bool
    human_approval_present: bool
    production_activation_present: bool

    @property
    def blocked_external(self) -> bool:
        return ExternalReadinessFlag.BLOCKED_EXTERNAL in self.flags


def _expected_production_key(
    assessment: HomologationEnvironmentReadinessAssessment,
) -> ProductionActivationKey:
    provider_id = assessment.provider_id
    if provider_id is None:
        raise FiscalValidationError(
            "exact production key cannot be reconciled without provider_id"
        )
    return ProductionActivationKey(
        tenant_id=assessment.scope.tenant_id,
        unit_id=assessment.scope.unit_id,
        provider_id=provider_id,
        document_kind=assessment.document_kind,
        jurisdiction=assessment.jurisdiction,
        operation=assessment.operation,
    )


def reconcile_external_readiness(
    assessment: HomologationEnvironmentReadinessAssessment,
    *,
    pilot_authorized: bool = False,
    human_approval: HumanProductionApproval | None = None,
    activation_record: ProductionActivationRecord | None = None,
) -> ExternalReadinessCellReport:
    """Compose canonical facts into a report without creating readiness or authority.

    This function is deliberately read-only. It never creates official evidence,
    pilot authorization, human approval or production activation. Exact approval
    and activation objects, when supplied, must match the assessed cell.
    """

    if not isinstance(assessment, HomologationEnvironmentReadinessAssessment):
        raise FiscalValidationError(
            "assessment must be HomologationEnvironmentReadinessAssessment"
        )

    flags: set[ExternalReadinessFlag] = set()
    if assessment.internally_ready:
        flags.add(ExternalReadinessFlag.READY_INTERNAL)

    external_secret_markers = {
        "provider_credentials_reference",
        "certificate_reference",
        "csc_reference",
    }
    if any(
        item in external_secret_markers for item in assessment.missing_configuration
    ):
        flags.add(ExternalReadinessFlag.MISSING_EXTERNAL_CREDENTIAL)

    if not assessment.officially_homologated:
        flags.add(ExternalReadinessFlag.MISSING_OFFICIAL_EVIDENCE)
    if not pilot_authorized:
        flags.add(ExternalReadinessFlag.MISSING_PILOT_AUTHORIZATION)
    if human_approval is None:
        flags.add(ExternalReadinessFlag.MISSING_HUMAN_APPROVAL)

    expected_key: ProductionActivationKey | None = None
    if human_approval is not None or activation_record is not None:
        expected_key = _expected_production_key(assessment)

    if human_approval is not None and human_approval.key != expected_key:
        raise FiscalValidationError(
            "human production approval does not match the exact assessed cell"
        )

    production_activation_present = False
    if activation_record is not None:
        if activation_record.key != expected_key:
            raise FiscalValidationError(
                "production activation record does not match the exact assessed cell"
            )
        production_activation_present = (
            activation_record.state is ProductionActivationState.ACTIVE
        )

    external_blockers = {
        ExternalReadinessFlag.MISSING_EXTERNAL_CREDENTIAL,
        ExternalReadinessFlag.MISSING_OFFICIAL_EVIDENCE,
        ExternalReadinessFlag.MISSING_PILOT_AUTHORIZATION,
        ExternalReadinessFlag.MISSING_HUMAN_APPROVAL,
    }
    if flags.intersection(external_blockers):
        flags.add(ExternalReadinessFlag.BLOCKED_EXTERNAL)

    return ExternalReadinessCellReport(
        assessment=assessment,
        flags=frozenset(flags),
        pilot_authorized=pilot_authorized,
        human_approval_present=human_approval is not None,
        production_activation_present=production_activation_present,
    )


class DurableHomologationEnvironmentReadinessService:
    """Audit exact HOMOLOGATION configuration without customer-specific branching."""

    def __init__(
        self,
        unit_of_work_factory: FiscalUnitOfWorkFactory,
        *,
        provider_catalog: tuple[ProviderDescriptor, ...],
    ) -> None:
        if not provider_catalog or not all(
            isinstance(item, ProviderDescriptor) for item in provider_catalog
        ):
            raise FiscalValidationError(
                "provider_catalog must contain ProviderDescriptor values"
            )
        ids = [item.provider_id for item in provider_catalog]
        if len(ids) != len(set(ids)):
            raise FiscalValidationError("provider_catalog ids must be unique")
        self._unit_of_work_factory = unit_of_work_factory
        self._providers = {item.provider_id: item for item in provider_catalog}

    def assess(
        self,
        *,
        scope: ExecutionScope,
        document_kind: FiscalDocumentKind,
        jurisdiction: BrazilianJurisdiction,
        operation: ProviderOperation,
    ) -> HomologationEnvironmentReadinessAssessment:
        if not isinstance(scope, ExecutionScope) or scope.host_namespace is None:
            raise FiscalValidationError("readiness assessment requires bound ExecutionScope")
        if scope.environment is not FiscalEnvironment.HOMOLOGATION:
            raise FiscalValidationError(
                "homologation environment readiness only accepts HOMOLOGATION scope"
            )
        if not isinstance(document_kind, FiscalDocumentKind):
            raise FiscalValidationError("document_kind must be FiscalDocumentKind")
        if not isinstance(jurisdiction, BrazilianJurisdiction):
            raise FiscalValidationError("jurisdiction must be BrazilianJurisdiction")
        if not isinstance(operation, ProviderOperation):
            raise FiscalValidationError("operation must be ProviderOperation")

        try:
            configured_operation = ConfiguredFiscalOperation(operation.value)
        except ValueError as exc:
            raise FiscalValidationError("unsupported configured provider operation") from exc

        missing: list[str] = []
        provider_id: str | None = None
        evidence_record: HomologationEvidenceRecord | None = None
        technical_state = TechnicalGateState.NOT_CONFIGURED

        with self._unit_of_work_factory() as uow:
            unit = uow.control_plane.get_unit(scope.tenant_id, scope.unit_id)
            if unit is None or scope.environment not in unit.enabled_environments:
                missing.append("unit_environment")

            binding = uow.commercial.resolve_provider_binding(
                tenant_id=scope.tenant_id,
                unit_id=scope.unit_id,
                environment=scope.environment,
                document_kind=document_kind,
                jurisdiction=jurisdiction,
                operation=configured_operation,
            )
            if binding is None or not binding.enabled:
                missing.append("provider_binding")
            else:
                provider_id = binding.provider_id

            descriptor = self._providers.get(provider_id) if provider_id is not None else None
            if descriptor is None:
                missing.append("provider_descriptor")
            elif not descriptor.supports(
                document_kind=document_kind,
                jurisdiction=jurisdiction,
                environment=scope.environment,
                operation=operation,
            ):
                missing.append("provider_capability")

            if provider_id is not None:
                credentials = uow.control_plane.get_secret_reference(
                    scope.tenant_id,
                    scope.unit_id,
                    scope.environment,
                    SecretReferenceKind.CREDENTIALS,
                    provider_id=provider_id,
                )
                if credentials is None:
                    missing.append("provider_credentials_reference")

                policy = uow.commercial.get_runtime_policy(
                    tenant_id=scope.tenant_id,
                    unit_id=scope.unit_id,
                    environment=scope.environment,
                    provider_id=provider_id,
                )
                if policy is None:
                    missing.append("provider_runtime_policy")

                evidence_record = uow.commercial.get_homologation_evidence(
                    tenant_id=scope.tenant_id,
                    unit_id=scope.unit_id,
                    environment=scope.environment,
                    provider_id=provider_id,
                    document_kind=document_kind,
                    jurisdiction=jurisdiction,
                    operation=operation.value,
                )
                if evidence_record is None:
                    missing.append("homologation_evidence")

            requires_signer = (
                evidence_record.requires_signer
                if evidence_record is not None
                else operation is ProviderOperation.AUTHORIZE
                and document_kind in {FiscalDocumentKind.NFE, FiscalDocumentKind.NFCE}
            )
            if requires_signer:
                certificate = uow.control_plane.get_secret_reference(
                    scope.tenant_id,
                    scope.unit_id,
                    scope.environment,
                    SecretReferenceKind.CERTIFICATE,
                )
                if certificate is None:
                    missing.append("certificate_reference")

            requires_csc = (
                descriptor.requires_csc(document_kind, operation)
                if descriptor is not None
                else False
            )
            if requires_csc and provider_id is not None:
                csc = uow.control_plane.get_secret_reference(
                    scope.tenant_id,
                    scope.unit_id,
                    scope.environment,
                    SecretReferenceKind.CSC,
                    provider_id=provider_id,
                )
                if csc is None:
                    missing.append("csc_reference")

        if evidence_record is not None and provider_id is not None:
            rule = TechnicalHomologationRule(
                key=HomologationGateKey(
                    provider_id=provider_id,
                    document_kind=document_kind,
                    jurisdiction=jurisdiction,
                    environment=scope.environment,
                    operation=operation,
                ),
                evidence=HomologationEvidence(
                    provider_adapter_available=evidence_record.provider_adapter_available,
                    credentials_reference_configured=(
                        evidence_record.credentials_reference_configured
                    ),
                    signer_capability=evidence_record.signer_capability,
                    csc_reference_configured=evidence_record.csc_reference_configured,
                    transport_configured=evidence_record.transport_configured,
                    resilience_certified=evidence_record.resilience_certified,
                    contract_tests_certified=evidence_record.contract_tests_certified,
                    jurisdiction_mapping=evidence_record.jurisdiction_mapping,
                    operation_supported=evidence_record.operation_supported,
                ),
                requires_signer=evidence_record.requires_signer,
                requires_csc=evidence_record.requires_csc,
            )
            technical_state = rule.technical_state

        return HomologationEnvironmentReadinessAssessment(
            scope=scope,
            document_kind=document_kind,
            jurisdiction=jurisdiction,
            operation=operation,
            provider_id=provider_id,
            missing_configuration=tuple(dict.fromkeys(missing)),
            technical_state=technical_state,
            external_official=(
                evidence_record.external_official if evidence_record is not None else False
            ),
            external_evidence_id=(
                evidence_record.external_evidence_id
                if evidence_record is not None
                else None
            ),
            external_recorded_at=(
                evidence_record.recorded_at if evidence_record is not None else None
            ),
        )
