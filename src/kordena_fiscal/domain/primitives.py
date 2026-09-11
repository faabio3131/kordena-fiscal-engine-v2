"""Canonical fiscal-domain primitives.

These value objects are intentionally host-agnostic. They carry only the minimum
information required by the fiscal engine and never depend on private host models.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from enum import IntEnum, StrEnum

from .errors import FiscalValidationError

_BRAZILIAN_STATES = frozenset(
    {
        "AC",
        "AL",
        "AP",
        "AM",
        "BA",
        "CE",
        "DF",
        "ES",
        "GO",
        "MA",
        "MT",
        "MS",
        "MG",
        "PA",
        "PB",
        "PR",
        "PE",
        "PI",
        "RJ",
        "RN",
        "RS",
        "RO",
        "RR",
        "SC",
        "SP",
        "SE",
        "TO",
    }
)
_HOST_NAMESPACE_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9._-]{0,62}[a-z0-9])?$")


def _required_text(value: str, field_name: str, *, max_length: int = 128) -> str:
    normalized = value.strip()
    if not normalized:
        raise FiscalValidationError(f"{field_name} must not be blank")
    if len(normalized) > max_length:
        raise FiscalValidationError(f"{field_name} exceeds max length {max_length}")
    return normalized


def _normalize_host_namespace(value: str) -> str:
    normalized = _required_text(value, "host_namespace", max_length=64).lower()
    if not _HOST_NAMESPACE_PATTERN.fullmatch(normalized):
        raise FiscalValidationError(
            "host_namespace must use lowercase letters, digits, '.', '_' or '-' "
            "and must start/end with an alphanumeric character"
        )
    return normalized


class FiscalEnvironment(StrEnum):
    """Execution environment for fiscal communication."""

    HOMOLOGATION = "homologation"
    PRODUCTION = "production"


class FiscalDocumentKind(StrEnum):
    """Canonical fiscal document families supported by the engine roadmap."""

    NFE = "nfe"
    NFCE = "nfce"
    NFSE = "nfse"


class ElectronicInvoiceModel(IntEnum):
    """Official model numbers for NF-e and NFC-e."""

    NFE = 55
    NFCE = 65


@dataclass(frozen=True, slots=True)
class ExecutionScope:
    """Host-neutral fiscal account/unit scope carried through every operation.

    ``host_namespace`` is optional only for compatibility with the certified V1
    baseline. New host-facing V2 boundaries must populate it through a governed
    FiscalAccountBinding before entering the Core.
    """

    tenant_id: str
    unit_id: str
    environment: FiscalEnvironment
    correlation_id: str
    host_namespace: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "tenant_id", _required_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "unit_id", _required_text(self.unit_id, "unit_id"))
        object.__setattr__(
            self,
            "correlation_id",
            _required_text(self.correlation_id, "correlation_id", max_length=256),
        )
        if not isinstance(self.environment, FiscalEnvironment):
            raise FiscalValidationError("environment must be a FiscalEnvironment")
        if self.host_namespace is not None:
            object.__setattr__(
                self,
                "host_namespace",
                _normalize_host_namespace(self.host_namespace),
            )

    @property
    def partition_key(self) -> tuple[str, str, FiscalEnvironment]:
        """Legacy-compatible tenant/unit/environment partition tuple."""

        return (self.tenant_id, self.unit_id, self.environment)

    @property
    def identity_partition_key(
        self,
    ) -> tuple[str | None, str, str, FiscalEnvironment]:
        """Universal V2 identity partition including host namespace."""

        return (self.host_namespace, self.tenant_id, self.unit_id, self.environment)

    @property
    def identity_material(self) -> tuple[str, ...]:
        """Stable string material for hashes/keys with legacy compatibility.

        Legacy scopes intentionally keep the original three-part material so the
        certified V1 identities remain stable. Bound V2 scopes add host namespace
        as the leading partition dimension.
        """

        legacy = (self.tenant_id, self.unit_id, self.environment.value)
        if self.host_namespace is None:
            return legacy
        return (self.host_namespace, *legacy)


@dataclass(frozen=True, slots=True)
class BrazilianJurisdiction:
    """Brazilian state/municipality jurisdiction without provider-specific encoding."""

    state_code: str
    municipality_ibge_code: str | None = None
    country_code: str = "BR"

    def __post_init__(self) -> None:
        state_code = _required_text(self.state_code, "state_code", max_length=2).upper()
        if state_code not in _BRAZILIAN_STATES:
            raise FiscalValidationError(f"unsupported Brazilian state code: {state_code}")

        country_code = _required_text(self.country_code, "country_code", max_length=2).upper()
        if country_code != "BR":
            raise FiscalValidationError("BrazilianJurisdiction only accepts country BR")

        municipality_code = self.municipality_ibge_code
        if municipality_code is not None:
            municipality_code = municipality_code.strip()
            if len(municipality_code) != 7 or not municipality_code.isdigit():
                raise FiscalValidationError(
                    "municipality_ibge_code must contain exactly 7 digits"
                )

        object.__setattr__(self, "state_code", state_code)
        object.__setattr__(self, "country_code", country_code)
        object.__setattr__(self, "municipality_ibge_code", municipality_code)


@dataclass(frozen=True, slots=True)
class SourceReference:
    """Stable reference to the host operation that originated a fiscal action."""

    source_type: str
    source_id: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "source_type",
            _required_text(self.source_type, "source_type", max_length=64).lower(),
        )
        object.__setattr__(
            self,
            "source_id",
            _required_text(self.source_id, "source_id", max_length=256),
        )

    @property
    def canonical_tuple(self) -> tuple[str, str]:
        """Unambiguous material for later deterministic idempotency derivation."""

        return (self.source_type, self.source_id)


@dataclass(frozen=True, slots=True)
class Money:
    """Brazilian monetary value using Decimal and no implicit rounding."""

    amount: Decimal
    currency: str = "BRL"

    def __post_init__(self) -> None:
        if not isinstance(self.amount, Decimal):
            raise FiscalValidationError("amount must be a Decimal")
        if not self.amount.is_finite():
            raise FiscalValidationError("amount must be finite")

        currency = _required_text(self.currency, "currency", max_length=3).upper()
        if currency != "BRL":
            raise FiscalValidationError("the fiscal engine currently accepts BRL only")
        object.__setattr__(self, "currency", currency)

    @classmethod
    def zero(cls) -> Money:
        return cls(Decimal("0"))

    def __add__(self, other: Money) -> Money:
        if not isinstance(other, Money):
            return NotImplemented
        if self.currency != other.currency:
            raise FiscalValidationError("cannot add monetary values with different currencies")
        return Money(self.amount + other.amount, self.currency)

    def __sub__(self, other: Money) -> Money:
        if not isinstance(other, Money):
            return NotImplemented
        if self.currency != other.currency:
            raise FiscalValidationError(
                "cannot subtract monetary values with different currencies"
            )
        return Money(self.amount - other.amount, self.currency)
