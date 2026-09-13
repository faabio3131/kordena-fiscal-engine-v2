"""Commercial identity, editions and entitlement catalog for FM Fiscal.

Pricing is deliberately absent. The catalog describes commercial capabilities and
can be loaded from configuration without changing fiscal-domain code.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Mapping, Sequence


class ProductCatalogError(ValueError):
    """Raised when commercial product configuration is invalid."""


def _token(value: str, field_name: str) -> str:
    normalized = value.strip().lower()
    if not normalized or len(normalized) > 128:
        raise ProductCatalogError(f"{field_name} must be a non-blank token <= 128 chars")
    allowed = set("abcdefghijklmnopqrstuvwxyz0123456789._-")
    if any(character not in allowed for character in normalized):
        raise ProductCatalogError(f"{field_name} contains invalid characters")
    return normalized


def _text(value: str, field_name: str, max_length: int = 512) -> str:
    normalized = value.strip()
    if not normalized or len(normalized) > max_length:
        raise ProductCatalogError(
            f"{field_name} must be non-blank and <= {max_length} chars"
        )
    return normalized


class CommercialModule(StrEnum):
    CORE = "core"
    BRIDGE_API = "bridge_api"
    NFE = "nfe"
    NFCE = "nfce"
    NFSE = "nfse"
    WEBHOOKS = "webhooks"
    RECONCILIATION = "reconciliation"
    ARCHIVE = "archive"
    CONTROL_PLANE = "control_plane"
    OBSERVABILITY = "observability"
    SDK_ACCESS = "sdk_access"
    PREMIUM_SUPPORT = "premium_support"


@dataclass(frozen=True, slots=True)
class ProductIdentity:
    product_id: str
    name: str
    company: str
    value_proposition: str
    target_audience: tuple[str, ...]
    differentiators: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "product_id", _token(self.product_id, "product_id"))
        object.__setattr__(self, "name", _text(self.name, "name", 128))
        object.__setattr__(self, "company", _text(self.company, "company", 128))
        object.__setattr__(
            self,
            "value_proposition",
            _text(self.value_proposition, "value_proposition", 1000),
        )
        if not self.target_audience:
            raise ProductCatalogError("target_audience must not be empty")
        if not self.differentiators:
            raise ProductCatalogError("differentiators must not be empty")
        object.__setattr__(
            self,
            "target_audience",
            tuple(_text(item, "target_audience item", 256) for item in self.target_audience),
        )
        object.__setattr__(
            self,
            "differentiators",
            tuple(_text(item, "differentiator", 256) for item in self.differentiators),
        )


@dataclass(frozen=True, slots=True)
class EntitlementDefinition:
    entitlement_id: str
    description: str
    metered: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "entitlement_id",
            _token(self.entitlement_id, "entitlement_id"),
        )
        object.__setattr__(self, "description", _text(self.description, "description"))
        if not isinstance(self.metered, bool):
            raise ProductCatalogError("metered must be bool")


@dataclass(frozen=True, slots=True)
class EditionBlueprint:
    edition_id: str
    display_name: str
    modules: tuple[CommercialModule, ...]
    entitlement_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "edition_id", _token(self.edition_id, "edition_id"))
        object.__setattr__(
            self,
            "display_name",
            _text(self.display_name, "display_name", 128),
        )
        if not self.modules:
            raise ProductCatalogError("edition modules must not be empty")
        if len(self.modules) != len(set(self.modules)):
            raise ProductCatalogError("edition modules must be unique")
        if not all(isinstance(module, CommercialModule) for module in self.modules):
            raise ProductCatalogError("modules must contain CommercialModule values")
        normalized_entitlements = tuple(
            _token(item, "entitlement_id") for item in self.entitlement_ids
        )
        if len(normalized_entitlements) != len(set(normalized_entitlements)):
            raise ProductCatalogError("edition entitlement ids must be unique")
        object.__setattr__(self, "entitlement_ids", normalized_entitlements)


@dataclass(frozen=True, slots=True)
class CommercialCatalog:
    identity: ProductIdentity
    entitlements: tuple[EntitlementDefinition, ...]
    editions: tuple[EditionBlueprint, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.identity, ProductIdentity):
            raise ProductCatalogError("identity must be ProductIdentity")
        entitlement_ids = tuple(item.entitlement_id for item in self.entitlements)
        edition_ids = tuple(item.edition_id for item in self.editions)
        if not entitlement_ids or len(entitlement_ids) != len(set(entitlement_ids)):
            raise ProductCatalogError("entitlements must be non-empty and uniquely identified")
        if not edition_ids or len(edition_ids) != len(set(edition_ids)):
            raise ProductCatalogError("editions must be non-empty and uniquely identified")
        known = set(entitlement_ids)
        for edition in self.editions:
            unknown = set(edition.entitlement_ids) - known
            if unknown:
                raise ProductCatalogError(
                    "edition references unknown entitlements: " + ", ".join(sorted(unknown))
                )

    def edition(self, edition_id: str) -> EditionBlueprint:
        wanted = _token(edition_id, "edition_id")
        for edition in self.editions:
            if edition.edition_id == wanted:
                return edition
        raise ProductCatalogError(f"unknown edition: {wanted}")

    def entitlement(self, entitlement_id: str) -> EntitlementDefinition:
        wanted = _token(entitlement_id, "entitlement_id")
        for entitlement in self.entitlements:
            if entitlement.entitlement_id == wanted:
                return entitlement
        raise ProductCatalogError(f"unknown entitlement: {wanted}")

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> CommercialCatalog:
        identity_payload = _mapping(payload.get("identity"), "identity")
        audience = _string_sequence(identity_payload.get("target_audience"), "target_audience")
        differentiators = _string_sequence(
            identity_payload.get("differentiators"),
            "differentiators",
        )
        identity = ProductIdentity(
            product_id=_string(identity_payload.get("product_id"), "product_id"),
            name=_string(identity_payload.get("name"), "name"),
            company=_string(identity_payload.get("company"), "company"),
            value_proposition=_string(
                identity_payload.get("value_proposition"),
                "value_proposition",
            ),
            target_audience=tuple(audience),
            differentiators=tuple(differentiators),
        )

        entitlement_payloads = _mapping_sequence(payload.get("entitlements"), "entitlements")
        entitlements = tuple(
            EntitlementDefinition(
                entitlement_id=_string(item.get("entitlement_id"), "entitlement_id"),
                description=_string(item.get("description"), "description"),
                metered=_boolean(item.get("metered", False), "metered"),
            )
            for item in entitlement_payloads
        )

        edition_payloads = _mapping_sequence(payload.get("editions"), "editions")
        editions: list[EditionBlueprint] = []
        for item in edition_payloads:
            modules = tuple(
                CommercialModule(value)
                for value in _string_sequence(item.get("modules"), "modules")
            )
            editions.append(
                EditionBlueprint(
                    edition_id=_string(item.get("edition_id"), "edition_id"),
                    display_name=_string(item.get("display_name"), "display_name"),
                    modules=modules,
                    entitlement_ids=tuple(
                        _string_sequence(item.get("entitlement_ids"), "entitlement_ids")
                    ),
                )
            )
        return cls(identity=identity, entitlements=entitlements, editions=tuple(editions))


def _mapping(value: object, field_name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ProductCatalogError(f"{field_name} must be a mapping")
    return value


def _mapping_sequence(value: object, field_name: str) -> Sequence[Mapping[str, object]]:
    if not isinstance(value, (list, tuple)):
        raise ProductCatalogError(f"{field_name} must be a sequence")
    return tuple(_mapping(item, f"{field_name} item") for item in value)


def _string(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise ProductCatalogError(f"{field_name} must be string")
    return value


def _string_sequence(value: object, field_name: str) -> Sequence[str]:
    if not isinstance(value, (list, tuple)):
        raise ProductCatalogError(f"{field_name} must be a sequence")
    if not all(isinstance(item, str) for item in value):
        raise ProductCatalogError(f"{field_name} must contain only strings")
    return tuple(value)


def _boolean(value: object, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ProductCatalogError(f"{field_name} must be bool")
    return value


_DEFAULT_ENTITLEMENTS = (
    EntitlementDefinition("documents.issue", "Submit governed fiscal document operations"),
    EntitlementDefinition("documents.query", "Query fiscal lifecycle and provider state"),
    EntitlementDefinition("webhooks.delivery", "Receive signed fiscal webhooks"),
    EntitlementDefinition("reconciliation", "Use fiscal reconciliation workflows"),
    EntitlementDefinition("archive.reference", "Resolve governed archive references"),
    EntitlementDefinition("usage.documents", "Meter accepted document operations", metered=True),
    EntitlementDefinition("support.premium", "Eligible for premium support workflows"),
)

DEFAULT_COMMERCIAL_CATALOG = CommercialCatalog(
    identity=ProductIdentity(
        product_id="fm-fiscal",
        name="FM Fiscal",
        company="FM Tecnologia",
        value_proposition=(
            "Uma camada fiscal brasileira independente, multiproduto e governada para integrar "
            "SaaS e operações digitais sem duplicar regras fiscais em cada produto."
        ),
        target_audience=(
            "SaaS e plataformas digitais que precisam de NF-e, NFC-e ou NFS-e",
            "Operações multiproduto que exigem isolamento por tenant, unidade e ambiente",
            "Times técnicos que precisam de contratos fiscais versionados e auditáveis",
        ),
        differentiators=(
            "Core fiscal host-neutral com Bridge/API versionada",
            "Readiness e capabilities fail-closed por jurisdição e ambiente",
            "Idempotência, reconciliação, archive e trilha de auditoria ponta a ponta",
            "Arquitetura multiproduto sem banco compartilhado entre SaaS consumidores",
        ),
    ),
    entitlements=_DEFAULT_ENTITLEMENTS,
    editions=(
        EditionBlueprint(
            edition_id="foundation",
            display_name="Foundation",
            modules=(
                CommercialModule.CORE,
                CommercialModule.BRIDGE_API,
                CommercialModule.NFE,
                CommercialModule.NFCE,
                CommercialModule.NFSE,
            ),
            entitlement_ids=("documents.issue", "documents.query", "usage.documents"),
        ),
        EditionBlueprint(
            edition_id="growth",
            display_name="Growth",
            modules=(
                CommercialModule.CORE,
                CommercialModule.BRIDGE_API,
                CommercialModule.NFE,
                CommercialModule.NFCE,
                CommercialModule.NFSE,
                CommercialModule.WEBHOOKS,
                CommercialModule.RECONCILIATION,
                CommercialModule.ARCHIVE,
            ),
            entitlement_ids=(
                "documents.issue",
                "documents.query",
                "usage.documents",
                "webhooks.delivery",
                "reconciliation",
                "archive.reference",
            ),
        ),
        EditionBlueprint(
            edition_id="enterprise",
            display_name="Enterprise",
            modules=tuple(CommercialModule),
            entitlement_ids=tuple(item.entitlement_id for item in _DEFAULT_ENTITLEMENTS),
        ),
    ),
)
