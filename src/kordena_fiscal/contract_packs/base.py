"""Host-neutral Product Contract Pack foundation.

Contract packs declare how one FM product maps its explicit use cases onto the
canonical fiscal contracts. They are integration declarations only: they never
promote fiscal readiness, jurisdiction support or production approval.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol

from kordena_fiscal.compliance import FiscalActionCapability
from kordena_fiscal.domain import FiscalDocumentKind, FiscalDomainError, FiscalValidationError
from kordena_fiscal.operations import FiscalOperationKind, FiscalOperationSnapshot
from kordena_fiscal.verticals import VerticalModuleRegistry

_TOKEN = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")


class ProductContractPackError(FiscalDomainError):
    """Base error for Product Contract Pack resolution and validation."""


class ProductContractPackRegistrationError(ProductContractPackError):
    """Raised when a registry registration would be ambiguous."""


class ProductContractPackNotFoundError(ProductContractPackError):
    """Raised when no pack is explicitly registered for a requested product."""


class ProductUseCaseNotFoundError(ProductContractPackError):
    """Raised when a product use case was not declared by its contract pack."""


class ProductOperationContractError(ProductContractPackError):
    """Raised when an operation violates the declared product contract."""


def _token(value: str, field_name: str) -> str:
    normalized = value.strip().lower()
    if not normalized:
        raise FiscalValidationError(f"{field_name} must not be blank")
    if not _TOKEN.fullmatch(normalized):
        raise FiscalValidationError(
            f"{field_name} must use lowercase alphanumeric tokens separated by '.', '_' or '-'"
        )
    return normalized


def _event_type(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise FiscalValidationError("event_type must not be blank")
    if len(normalized) > 128:
        raise FiscalValidationError("event_type exceeds max length 128")
    return normalized


@dataclass(frozen=True, slots=True)
class ProductUseCaseDescriptor:
    """One explicit product-to-fiscal mapping without runtime readiness claims."""

    use_case_id: str
    operation_kinds: frozenset[FiscalOperationKind]
    document_kinds: frozenset[FiscalDocumentKind]
    fiscal_actions: frozenset[FiscalActionCapability]
    vertical_module_id: str | None = None
    required_vertical_capabilities: frozenset[str] = frozenset()
    outbound_event_types: tuple[str, ...] = ()
    inbound_event_types: tuple[str, ...] = ()
    description: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "use_case_id", _token(self.use_case_id, "use_case_id"))
        if not isinstance(self.operation_kinds, frozenset) or not self.operation_kinds:
            raise FiscalValidationError("operation_kinds must be a non-empty frozenset")
        if not all(isinstance(kind, FiscalOperationKind) for kind in self.operation_kinds):
            raise FiscalValidationError("operation_kinds must contain FiscalOperationKind values")
        if not isinstance(self.document_kinds, frozenset) or not self.document_kinds:
            raise FiscalValidationError("document_kinds must be a non-empty frozenset")
        if not all(isinstance(kind, FiscalDocumentKind) for kind in self.document_kinds):
            raise FiscalValidationError("document_kinds must contain FiscalDocumentKind values")
        if not isinstance(self.fiscal_actions, frozenset) or not self.fiscal_actions:
            raise FiscalValidationError("fiscal_actions must be a non-empty frozenset")
        if not all(isinstance(action, FiscalActionCapability) for action in self.fiscal_actions):
            raise FiscalValidationError(
                "fiscal_actions must contain FiscalActionCapability values"
            )
        if not isinstance(self.required_vertical_capabilities, frozenset):
            raise FiscalValidationError("required_vertical_capabilities must be a frozenset")

        module_id = self.vertical_module_id
        capabilities = frozenset(
            _token(capability, "vertical_capability")
            for capability in self.required_vertical_capabilities
        )
        object.__setattr__(self, "required_vertical_capabilities", capabilities)
        if module_id is None:
            if capabilities:
                raise FiscalValidationError(
                    "required_vertical_capabilities require vertical_module_id"
                )
        else:
            object.__setattr__(self, "vertical_module_id", _token(module_id, "vertical_module_id"))

        outbound = tuple(_event_type(value) for value in self.outbound_event_types)
        inbound = tuple(_event_type(value) for value in self.inbound_event_types)
        if len(outbound) != len(set(outbound)):
            raise FiscalValidationError("outbound_event_types must not contain duplicates")
        if len(inbound) != len(set(inbound)):
            raise FiscalValidationError("inbound_event_types must not contain duplicates")
        object.__setattr__(self, "outbound_event_types", outbound)
        object.__setattr__(self, "inbound_event_types", inbound)
        object.__setattr__(self, "description", self.description.strip())

    def accepts_operation_kind(self, kind: FiscalOperationKind) -> bool:
        if not isinstance(kind, FiscalOperationKind):
            raise FiscalValidationError("kind must be FiscalOperationKind")
        return kind in self.operation_kinds

    def supports_document_kind(self, kind: FiscalDocumentKind) -> bool:
        if not isinstance(kind, FiscalDocumentKind):
            raise FiscalValidationError("kind must be FiscalDocumentKind")
        return kind in self.document_kinds


@dataclass(frozen=True, slots=True)
class ProductContractPackDescriptor:
    """Immutable versioned contract declaration for one product namespace."""

    pack_id: str
    host_namespace: str
    use_cases: tuple[ProductUseCaseDescriptor, ...]
    version: str = "1"
    description: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "pack_id", _token(self.pack_id, "pack_id"))
        object.__setattr__(
            self,
            "host_namespace",
            _token(self.host_namespace, "host_namespace"),
        )
        if not isinstance(self.use_cases, tuple) or not self.use_cases:
            raise FiscalValidationError("use_cases must be a non-empty tuple")
        if not all(isinstance(use_case, ProductUseCaseDescriptor) for use_case in self.use_cases):
            raise FiscalValidationError("use_cases must contain ProductUseCaseDescriptor values")
        use_case_ids = tuple(use_case.use_case_id for use_case in self.use_cases)
        if len(use_case_ids) != len(set(use_case_ids)):
            raise FiscalValidationError("use_case_id values must be unique within a pack")
        version = self.version.strip()
        if not version:
            raise FiscalValidationError("version must not be blank")
        object.__setattr__(self, "version", version)
        object.__setattr__(self, "description", self.description.strip())

    def get_use_case(self, use_case_id: str) -> ProductUseCaseDescriptor | None:
        normalized = _token(use_case_id, "use_case_id")
        return next(
            (use_case for use_case in self.use_cases if use_case.use_case_id == normalized),
            None,
        )

    def require_use_case(self, use_case_id: str) -> ProductUseCaseDescriptor:
        use_case = self.get_use_case(use_case_id)
        if use_case is None:
            raise ProductUseCaseNotFoundError(
                f"product use case is not declared by {self.pack_id}: "
                f"{_token(use_case_id, 'use_case_id')}"
            )
        return use_case

    def validate_operation(
        self,
        *,
        use_case_id: str,
        operation: FiscalOperationSnapshot,
    ) -> ProductUseCaseDescriptor:
        """Validate product namespace + operation kind; never infer fiscal readiness."""

        if not isinstance(operation, FiscalOperationSnapshot):
            raise FiscalValidationError("operation must be FiscalOperationSnapshot")
        if operation.scope.host_namespace != self.host_namespace:
            raise ProductOperationContractError(
                f"host namespace mismatch for {self.pack_id}: "
                f"expected {self.host_namespace!r}, got {operation.scope.host_namespace!r}"
            )
        use_case = self.require_use_case(use_case_id)
        if operation.operation_kind not in use_case.operation_kinds:
            raise ProductOperationContractError(
                f"operation kind {operation.operation_kind.value!r} is not declared for "
                f"{self.pack_id}/{use_case.use_case_id}"
            )
        return use_case

    def validate_vertical_contracts(self, registry: VerticalModuleRegistry) -> None:
        """Fail closed when a declared vertical module/capability is unavailable."""

        if not isinstance(registry, VerticalModuleRegistry):
            raise FiscalValidationError("registry must be VerticalModuleRegistry")
        for use_case in self.use_cases:
            module_id = use_case.vertical_module_id
            if module_id is None:
                continue
            registry.require(module_id)
            for capability in use_case.required_vertical_capabilities:
                registry.require_capability(module_id, capability)


class ProductFiscalContractPack(Protocol):
    """Minimal interface implemented by each product-specific declaration."""

    @property
    def descriptor(self) -> ProductContractPackDescriptor:
        ...


@dataclass(frozen=True, slots=True)
class DeclarativeProductFiscalContractPack:
    descriptor: ProductContractPackDescriptor

    def __post_init__(self) -> None:
        if not isinstance(self.descriptor, ProductContractPackDescriptor):
            raise FiscalValidationError("descriptor must be ProductContractPackDescriptor")


class ProductContractPackRegistry:
    """Explicit registry keyed by pack id and host namespace."""

    def __init__(self, packs: Iterable[ProductFiscalContractPack] = ()) -> None:
        self._by_pack_id: dict[str, ProductFiscalContractPack] = {}
        self._by_host_namespace: dict[str, ProductFiscalContractPack] = {}
        for pack in packs:
            self.register(pack)

    def register(self, pack: ProductFiscalContractPack) -> None:
        descriptor = pack.descriptor
        if not isinstance(descriptor, ProductContractPackDescriptor):
            raise FiscalValidationError("product contract pack descriptor is invalid")
        if descriptor.pack_id in self._by_pack_id:
            raise ProductContractPackRegistrationError(
                f"product contract pack already registered: {descriptor.pack_id}"
            )
        if descriptor.host_namespace in self._by_host_namespace:
            raise ProductContractPackRegistrationError(
                "host namespace already owned by another product contract pack: "
                f"{descriptor.host_namespace}"
            )
        self._by_pack_id[descriptor.pack_id] = pack
        self._by_host_namespace[descriptor.host_namespace] = pack

    def require(self, pack_id: str) -> ProductFiscalContractPack:
        normalized = _token(pack_id, "pack_id")
        pack = self._by_pack_id.get(normalized)
        if pack is None:
            raise ProductContractPackNotFoundError(
                f"product contract pack is not registered: {normalized}"
            )
        return pack

    def require_for_host(self, host_namespace: str) -> ProductFiscalContractPack:
        normalized = _token(host_namespace, "host_namespace")
        pack = self._by_host_namespace.get(normalized)
        if pack is None:
            raise ProductContractPackNotFoundError(
                f"product contract pack is not registered for host namespace: {normalized}"
            )
        return pack

    @property
    def pack_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._by_pack_id))

    @property
    def host_namespaces(self) -> tuple[str, ...]:
        return tuple(sorted(self._by_host_namespace))
