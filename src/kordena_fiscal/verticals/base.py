"""Host-neutral extension contract for optional fiscal vertical modules."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol

from kordena_fiscal.domain import FiscalDomainError, FiscalValidationError

_VERTICAL_TOKEN = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")


class VerticalModuleError(FiscalDomainError):
    """Base error for vertical module registration and resolution."""


class VerticalRegistrationError(VerticalModuleError):
    """Raised when a module registration would make the registry ambiguous."""


class VerticalModuleNotFoundError(VerticalModuleError):
    """Raised when a requested vertical module was not explicitly registered."""


class VerticalCapabilityError(VerticalModuleError):
    """Raised when a registered module does not declare a required capability."""


def _token(value: str, field_name: str) -> str:
    normalized = value.strip().lower()
    if not normalized:
        raise FiscalValidationError(f"{field_name} must not be blank")
    if not _VERTICAL_TOKEN.fullmatch(normalized):
        raise FiscalValidationError(
            f"{field_name} must use lowercase alphanumeric tokens separated by '.', '_' or '-'"
        )
    return normalized


@dataclass(frozen=True, slots=True)
class VerticalModuleDescriptor:
    """Stable identity and declared capabilities of one optional vertical module."""

    module_id: str
    capabilities: frozenset[str]
    version: str = "1"
    description: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "module_id", _token(self.module_id, "module_id"))
        if not isinstance(self.capabilities, frozenset):
            raise FiscalValidationError("capabilities must be a frozenset")
        normalized = frozenset(
            _token(capability, "capability") for capability in self.capabilities
        )
        if not normalized:
            raise FiscalValidationError("vertical module must declare at least one capability")
        object.__setattr__(self, "capabilities", normalized)
        version = self.version.strip()
        if not version:
            raise FiscalValidationError("version must not be blank")
        object.__setattr__(self, "version", version)
        object.__setattr__(self, "description", self.description.strip())

    def supports(self, capability: str) -> bool:
        return _token(capability, "capability") in self.capabilities


class VerticalModule(Protocol):
    """Minimal extension point implemented by every vertical module."""

    @property
    def descriptor(self) -> VerticalModuleDescriptor:
        """Return immutable module metadata and declared capabilities."""
        ...


@dataclass(frozen=True, slots=True)
class CapabilityVerticalModule:
    """Declarative module for verticals that need no sector-specific classifier."""

    descriptor: VerticalModuleDescriptor

    def __post_init__(self) -> None:
        if not isinstance(self.descriptor, VerticalModuleDescriptor):
            raise FiscalValidationError("descriptor must be VerticalModuleDescriptor")


class VerticalModuleRegistry:
    """Explicit fail-closed registry; the Core never infers a vertical silently."""

    def __init__(self, modules: Iterable[VerticalModule] = ()) -> None:
        self._modules: dict[str, VerticalModule] = {}
        for module in modules:
            self.register(module)

    def register(self, module: VerticalModule) -> None:
        descriptor = module.descriptor
        if not isinstance(descriptor, VerticalModuleDescriptor):
            raise FiscalValidationError("vertical module descriptor is invalid")
        existing = self._modules.get(descriptor.module_id)
        if existing is not None:
            raise VerticalRegistrationError(
                f"vertical module already registered: {descriptor.module_id}"
            )
        self._modules[descriptor.module_id] = module

    def get(self, module_id: str) -> VerticalModule | None:
        return self._modules.get(_token(module_id, "module_id"))

    def require(self, module_id: str) -> VerticalModule:
        normalized = _token(module_id, "module_id")
        module = self._modules.get(normalized)
        if module is None:
            raise VerticalModuleNotFoundError(
                f"vertical module is not registered: {normalized}"
            )
        return module

    def require_capability(self, module_id: str, capability: str) -> VerticalModule:
        normalized_capability = _token(capability, "capability")
        module = self.require(module_id)
        if normalized_capability not in module.descriptor.capabilities:
            raise VerticalCapabilityError(
                f"vertical module {module.descriptor.module_id} does not declare capability "
                f"{normalized_capability}"
            )
        return module

    def modules_for(self, capability: str) -> tuple[VerticalModule, ...]:
        normalized = _token(capability, "capability")
        matching = [
            module
            for module in self._modules.values()
            if normalized in module.descriptor.capabilities
        ]
        return tuple(sorted(matching, key=lambda module: module.descriptor.module_id))

    @property
    def module_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._modules))
