"""Configuration-driven external dependencies for standalone FM Fiscal tenants.

The module deliberately stores references and commercial/fiscal metadata only. Secret material,
certificate bytes, CSC tokens and provider/gateway credentials must live in an external vault.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import StrEnum


class TenantConfigurationError(ValueError):
    """Raised when tenant configuration violates a fail-closed invariant."""


class ExternalDependencyState(StrEnum):
    MISSING = "missing"
    CONFIGURED = "configured"
    VERIFIED = "verified"


class DocumentKind(StrEnum):
    NFE = "nfe"
    NFCE = "nfce"
    NFSE = "nfse"


class FiscalEnvironment(StrEnum):
    HOMOLOGATION = "homologation"
    PRODUCTION = "production"


class PricingMode(StrEnum):
    FIXED = "fixed"
    PER_DOCUMENT = "per_document"
    TIERED = "tiered"
    CUSTOM = "custom"


def _required_text(value: str, field_name: str, max_length: int = 256) -> str:
    normalized = value.strip()
    if not normalized or len(normalized) > max_length:
        raise TenantConfigurationError(
            f"{field_name} must be non-blank and <= {max_length} chars"
        )
    return normalized


def _optional_text(value: str | None, field_name: str, max_length: int = 256) -> str | None:
    if value is None:
        return None
    return _required_text(value, field_name, max_length)


@dataclass(frozen=True, slots=True)
class ExternalReference:
    """Reference-only external dependency state; never contains secret material."""

    reference_id: str | None
    state: ExternalDependencyState
    evidence_reference: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.state, ExternalDependencyState):
            raise TenantConfigurationError("state must be ExternalDependencyState")
        normalized_reference = _optional_text(self.reference_id, "reference_id", 320)
        normalized_evidence = _optional_text(
            self.evidence_reference,
            "evidence_reference",
            320,
        )
        if self.state is ExternalDependencyState.MISSING:
            if normalized_reference is not None or normalized_evidence is not None:
                raise TenantConfigurationError("missing dependency cannot carry references")
        else:
            if normalized_reference is None:
                raise TenantConfigurationError("configured dependency requires reference_id")
        if self.state is ExternalDependencyState.VERIFIED and normalized_evidence is None:
            raise TenantConfigurationError("verified dependency requires evidence_reference")
        object.__setattr__(self, "reference_id", normalized_reference)
        object.__setattr__(self, "evidence_reference", normalized_evidence)

    @property
    def verified(self) -> bool:
        return self.state is ExternalDependencyState.VERIFIED


@dataclass(frozen=True, slots=True)
class FiscalChannelConfiguration:
    channel_id: str
    document_kind: DocumentKind
    environment: FiscalEnvironment
    provider_profile_id: str
    uf: str | None
    municipality_code: str | None
    certificate: ExternalReference
    csc_identifier: ExternalReference
    csc_token: ExternalReference
    provider_credentials: ExternalReference
    official_homologation: ExternalReference
    enabled: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "channel_id", _required_text(self.channel_id, "channel_id", 128))
        object.__setattr__(
            self,
            "provider_profile_id",
            _required_text(self.provider_profile_id, "provider_profile_id", 128),
        )
        if not isinstance(self.document_kind, DocumentKind):
            raise TenantConfigurationError("document_kind must be DocumentKind")
        if not isinstance(self.environment, FiscalEnvironment):
            raise TenantConfigurationError("environment must be FiscalEnvironment")
        normalized_uf = self.uf.strip().upper() if self.uf is not None else None
        if normalized_uf is not None and (len(normalized_uf) != 2 or not normalized_uf.isalpha()):
            raise TenantConfigurationError("uf must be a two-letter code")
        normalized_municipality = _optional_text(
            self.municipality_code,
            "municipality_code",
            16,
        )
        if self.document_kind in {DocumentKind.NFE, DocumentKind.NFCE} and normalized_uf is None:
            raise TenantConfigurationError("NF-e/NFC-e channel requires uf")
        if self.document_kind is DocumentKind.NFSE and normalized_municipality is None:
            raise TenantConfigurationError("NFS-e channel requires municipality_code")
        if self.document_kind is not DocumentKind.NFCE:
            if self.csc_identifier.state is not ExternalDependencyState.MISSING:
                raise TenantConfigurationError("CSC identifier applies only to NFC-e")
            if self.csc_token.state is not ExternalDependencyState.MISSING:
                raise TenantConfigurationError("CSC token applies only to NFC-e")
        object.__setattr__(self, "uf", normalized_uf)
        object.__setattr__(self, "municipality_code", normalized_municipality)

    @property
    def externally_ready(self) -> bool:
        required = [self.certificate, self.provider_credentials, self.official_homologation]
        if self.document_kind is DocumentKind.NFCE:
            required.extend([self.csc_identifier, self.csc_token])
        return self.enabled and all(item.verified for item in required)


@dataclass(frozen=True, slots=True)
class CommercialGatewayConfiguration:
    gateway_profile_id: str
    account_reference: ExternalReference
    webhook_secret_reference: ExternalReference
    enabled: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "gateway_profile_id",
            _required_text(self.gateway_profile_id, "gateway_profile_id", 128),
        )


@dataclass(frozen=True, slots=True)
class CommercialOfferConfiguration:
    offer_id: str
    edition_id: str
    pricing_mode: PricingMode
    currency: str
    base_amount: Decimal | None = None
    per_document_amount: Decimal | None = None
    external_price_reference: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "offer_id", _required_text(self.offer_id, "offer_id", 128))
        object.__setattr__(
            self,
            "edition_id",
            _required_text(self.edition_id, "edition_id", 128),
        )
        if not isinstance(self.pricing_mode, PricingMode):
            raise TenantConfigurationError("pricing_mode must be PricingMode")
        currency = self.currency.strip().upper()
        if len(currency) != 3 or not currency.isalpha():
            raise TenantConfigurationError("currency must be an ISO-like three-letter code")
        object.__setattr__(self, "currency", currency)
        for field_name in ("base_amount", "per_document_amount"):
            amount = getattr(self, field_name)
            if amount is not None and amount < Decimal("0"):
                raise TenantConfigurationError(f"{field_name} cannot be negative")
        object.__setattr__(
            self,
            "external_price_reference",
            _optional_text(self.external_price_reference, "external_price_reference", 256),
        )


@dataclass(frozen=True, slots=True)
class TenantExternalConfiguration:
    """One versioned configuration snapshot for a tenant/unit.

    Adding a customer is data-only when its required document/provider profiles are already
    supported by the platform. Production readiness is derived from verified evidence references,
    never from mere presence of configuration.
    """

    configuration_id: str
    version: int
    tenant_id: str
    company_id: str
    unit_id: str
    channels: tuple[FiscalChannelConfiguration, ...]
    gateway: CommercialGatewayConfiguration | None
    offer: CommercialOfferConfiguration | None
    legal_approval: ExternalReference
    pilot_approval: ExternalReference
    production_activation: ExternalReference

    def __post_init__(self) -> None:
        for field_name in ("configuration_id", "tenant_id", "company_id", "unit_id"):
            object.__setattr__(
                self,
                field_name,
                _required_text(getattr(self, field_name), field_name, 160),
            )
        if self.version < 1:
            raise TenantConfigurationError("version must be >= 1")
        ids = tuple(channel.channel_id for channel in self.channels)
        if len(ids) != len(set(ids)):
            raise TenantConfigurationError("channel_id values must be unique")

    @property
    def production_ready(self) -> bool:
        enabled_channels = tuple(channel for channel in self.channels if channel.enabled)
        if not enabled_channels:
            return False
        return (
            all(channel.externally_ready for channel in enabled_channels)
            and self.legal_approval.verified
            and self.pilot_approval.verified
            and self.production_activation.verified
        )

    @property
    def requires_code_change(self) -> bool:
        """False by design: supported customer differences live in configuration."""
        return False

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> TenantExternalConfiguration:
        channels_payload = _mapping_sequence(payload.get("channels"), "channels")
        channels = tuple(_channel_from_mapping(item) for item in channels_payload)
        gateway_payload = payload.get("gateway")
        offer_payload = payload.get("offer")
        return cls(
            configuration_id=_string(payload.get("configuration_id"), "configuration_id"),
            version=_integer(payload.get("version"), "version"),
            tenant_id=_string(payload.get("tenant_id"), "tenant_id"),
            company_id=_string(payload.get("company_id"), "company_id"),
            unit_id=_string(payload.get("unit_id"), "unit_id"),
            channels=channels,
            gateway=(
                None
                if gateway_payload is None
                else _gateway_from_mapping(_mapping(gateway_payload, "gateway"))
            ),
            offer=(
                None
                if offer_payload is None
                else _offer_from_mapping(_mapping(offer_payload, "offer"))
            ),
            legal_approval=_reference_from_mapping(
                _mapping(payload.get("legal_approval"), "legal_approval")
            ),
            pilot_approval=_reference_from_mapping(
                _mapping(payload.get("pilot_approval"), "pilot_approval")
            ),
            production_activation=_reference_from_mapping(
                _mapping(payload.get("production_activation"), "production_activation")
            ),
        )


class TenantConfigurationRegistry:
    """Optimistic in-memory authority for immutable configuration snapshots."""

    def __init__(self) -> None:
        self._items: dict[tuple[str, str], TenantExternalConfiguration] = {}

    def get(self, tenant_id: str, unit_id: str) -> TenantExternalConfiguration | None:
        return self._items.get((tenant_id.strip(), unit_id.strip()))

    def upsert(
        self,
        configuration: TenantExternalConfiguration,
        *,
        expected_version: int | None,
    ) -> TenantExternalConfiguration:
        key = (configuration.tenant_id, configuration.unit_id)
        current = self._items.get(key)
        if current is None:
            if expected_version is not None:
                raise TenantConfigurationError("new configuration requires expected_version=None")
            if configuration.version != 1:
                raise TenantConfigurationError("new configuration must start at version 1")
        else:
            if expected_version != current.version:
                raise TenantConfigurationError("configuration version conflict")
            if configuration.version != current.version + 1:
                raise TenantConfigurationError("configuration version must increment by one")
        self._items[key] = configuration
        return configuration


def _reference_from_mapping(payload: Mapping[str, object]) -> ExternalReference:
    state = ExternalDependencyState(_string(payload.get("state"), "state"))
    return ExternalReference(
        reference_id=_optional_string(payload.get("reference_id"), "reference_id"),
        state=state,
        evidence_reference=_optional_string(
            payload.get("evidence_reference"),
            "evidence_reference",
        ),
    )


def _channel_from_mapping(payload: Mapping[str, object]) -> FiscalChannelConfiguration:
    return FiscalChannelConfiguration(
        channel_id=_string(payload.get("channel_id"), "channel_id"),
        document_kind=DocumentKind(_string(payload.get("document_kind"), "document_kind")),
        environment=FiscalEnvironment(_string(payload.get("environment"), "environment")),
        provider_profile_id=_string(
            payload.get("provider_profile_id"),
            "provider_profile_id",
        ),
        uf=_optional_string(payload.get("uf"), "uf"),
        municipality_code=_optional_string(
            payload.get("municipality_code"),
            "municipality_code",
        ),
        certificate=_reference_from_mapping(_mapping(payload.get("certificate"), "certificate")),
        csc_identifier=_reference_from_mapping(
            _mapping(payload.get("csc_identifier"), "csc_identifier")
        ),
        csc_token=_reference_from_mapping(_mapping(payload.get("csc_token"), "csc_token")),
        provider_credentials=_reference_from_mapping(
            _mapping(payload.get("provider_credentials"), "provider_credentials")
        ),
        official_homologation=_reference_from_mapping(
            _mapping(payload.get("official_homologation"), "official_homologation")
        ),
        enabled=_boolean(payload.get("enabled", True), "enabled"),
    )


def _gateway_from_mapping(payload: Mapping[str, object]) -> CommercialGatewayConfiguration:
    return CommercialGatewayConfiguration(
        gateway_profile_id=_string(payload.get("gateway_profile_id"), "gateway_profile_id"),
        account_reference=_reference_from_mapping(
            _mapping(payload.get("account_reference"), "account_reference")
        ),
        webhook_secret_reference=_reference_from_mapping(
            _mapping(payload.get("webhook_secret_reference"), "webhook_secret_reference")
        ),
        enabled=_boolean(payload.get("enabled", True), "enabled"),
    )


def _offer_from_mapping(payload: Mapping[str, object]) -> CommercialOfferConfiguration:
    return CommercialOfferConfiguration(
        offer_id=_string(payload.get("offer_id"), "offer_id"),
        edition_id=_string(payload.get("edition_id"), "edition_id"),
        pricing_mode=PricingMode(_string(payload.get("pricing_mode"), "pricing_mode")),
        currency=_string(payload.get("currency"), "currency"),
        base_amount=_decimal(payload.get("base_amount"), "base_amount"),
        per_document_amount=_decimal(
            payload.get("per_document_amount"),
            "per_document_amount",
        ),
        external_price_reference=_optional_string(
            payload.get("external_price_reference"),
            "external_price_reference",
        ),
    )


def _mapping(value: object, field_name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise TenantConfigurationError(f"{field_name} must be a mapping")
    return value


def _mapping_sequence(value: object, field_name: str) -> Sequence[Mapping[str, object]]:
    if not isinstance(value, (list, tuple)):
        raise TenantConfigurationError(f"{field_name} must be a sequence")
    return tuple(_mapping(item, f"{field_name} item") for item in value)


def _string(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise TenantConfigurationError(f"{field_name} must be string")
    return value


def _optional_string(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    return _string(value, field_name)


def _integer(value: object, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TenantConfigurationError(f"{field_name} must be integer")
    return value


def _boolean(value: object, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise TenantConfigurationError(f"{field_name} must be bool")
    return value


def _decimal(value: object, field_name: str) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise TenantConfigurationError(f"{field_name} must be decimal-compatible")
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise TenantConfigurationError(f"{field_name} must be decimal-compatible") from exc
