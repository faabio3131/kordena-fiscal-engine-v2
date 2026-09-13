"""Durable commercial-runtime configuration records for zero-code onboarding."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from kordena_fiscal.domain import (
    BrazilianJurisdiction,
    ElectronicInvoiceModel,
    FiscalDocumentKind,
    FiscalEnvironment,
    FiscalValidationError,
)
from kordena_fiscal.numbering import FiscalSequencePolicy


def _token(value: str, field_name: str) -> str:
    normalized = value.strip().lower()
    if not normalized or len(normalized) > 128:
        raise FiscalValidationError(f"{field_name} must be a non-blank token <= 128 chars")
    allowed = set("abcdefghijklmnopqrstuvwxyz0123456789._-")
    if any(character not in allowed for character in normalized):
        raise FiscalValidationError(f"{field_name} has invalid token format")
    return normalized


def _optional_text(value: str | None, field_name: str) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized or len(normalized) > 512:
        raise FiscalValidationError(f"{field_name} must be non-blank and <= 512 chars")
    return normalized


def _aware(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise FiscalValidationError(f"{field_name} must be timezone-aware")
    return value


@dataclass(frozen=True, slots=True)
class NumberingConfiguration:
    """Durable numbering authority for one tenant/unit/environment/document model."""

    tenant_id: str
    unit_id: str
    environment: FiscalEnvironment
    model: ElectronicInvoiceModel
    series: int
    first_number: int = 1
    max_number: int | None = None
    enabled: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "tenant_id", _token(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "unit_id", _token(self.unit_id, "unit_id"))
        if not isinstance(self.environment, FiscalEnvironment):
            raise FiscalValidationError("environment must be FiscalEnvironment")
        if not isinstance(self.model, ElectronicInvoiceModel):
            raise FiscalValidationError("model must be ElectronicInvoiceModel")
        if not isinstance(self.series, int) or isinstance(self.series, bool) or self.series < 0:
            raise FiscalValidationError("series must be a non-negative integer")
        FiscalSequencePolicy(
            first_number=self.first_number,
            max_number=self.max_number,
        )
        if not isinstance(self.enabled, bool):
            raise FiscalValidationError("enabled must be bool")

    @property
    def policy(self) -> FiscalSequencePolicy:
        return FiscalSequencePolicy(
            first_number=self.first_number,
            max_number=self.max_number,
        )


@dataclass(frozen=True, slots=True)
class HomologationEvidenceRecord:
    """Durable technical/official evidence metadata; never a readiness authority."""

    tenant_id: str
    unit_id: str
    environment: FiscalEnvironment
    provider_id: str
    document_kind: FiscalDocumentKind
    jurisdiction: BrazilianJurisdiction
    operation: str
    provider_adapter_available: bool
    credentials_reference_configured: bool
    signer_capability: bool
    csc_reference_configured: bool
    transport_configured: bool
    resilience_certified: bool
    contract_tests_certified: bool
    jurisdiction_mapping: bool
    operation_supported: bool
    requires_signer: bool = False
    requires_csc: bool = False
    external_evidence_id: str | None = None
    external_official: bool = False
    recorded_at: datetime | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "tenant_id", _token(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "unit_id", _token(self.unit_id, "unit_id"))
        object.__setattr__(self, "provider_id", _token(self.provider_id, "provider_id"))
        if not isinstance(self.environment, FiscalEnvironment):
            raise FiscalValidationError("environment must be FiscalEnvironment")
        if not isinstance(self.document_kind, FiscalDocumentKind):
            raise FiscalValidationError("document_kind must be FiscalDocumentKind")
        if not isinstance(self.jurisdiction, BrazilianJurisdiction):
            raise FiscalValidationError("jurisdiction must be BrazilianJurisdiction")
        operation = _token(self.operation, "operation")
        if operation not in {"authorize", "query", "cancel", "inutilize", "status"}:
            raise FiscalValidationError("operation is not a supported provider operation")
        object.__setattr__(self, "operation", operation)
        if self.document_kind is FiscalDocumentKind.NFSE:
            if self.jurisdiction.municipality_ibge_code is None:
                raise FiscalValidationError(
                    "NFSe homologation evidence requires municipality IBGE code"
                )
        if self.requires_csc and self.document_kind is not FiscalDocumentKind.NFCE:
            raise FiscalValidationError("CSC evidence requirement is only valid for NFCe")
        for field_name in (
            "provider_adapter_available",
            "credentials_reference_configured",
            "signer_capability",
            "csc_reference_configured",
            "transport_configured",
            "resilience_certified",
            "contract_tests_certified",
            "jurisdiction_mapping",
            "operation_supported",
            "requires_signer",
            "requires_csc",
            "external_official",
        ):
            if not isinstance(getattr(self, field_name), bool):
                raise FiscalValidationError(f"{field_name} must be bool")
        object.__setattr__(
            self,
            "external_evidence_id",
            _optional_text(self.external_evidence_id, "external_evidence_id"),
        )
        if self.external_official and self.external_evidence_id is None:
            raise FiscalValidationError(
                "official external evidence requires external_evidence_id"
            )
        if self.recorded_at is not None:
            _aware(self.recorded_at, "recorded_at")

    @property
    def exact_key(self) -> tuple[str, str, str, str, str, str, str, str]:
        return (
            self.tenant_id,
            self.unit_id,
            self.environment.value,
            self.provider_id,
            self.document_kind.value,
            self.jurisdiction.state_code,
            self.jurisdiction.municipality_ibge_code or "",
            self.operation,
        )
