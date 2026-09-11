"""Host namespace and fiscal-account binding contracts.

This module isolates external SaaS identities from the internal fiscal execution
scope. It intentionally contains no authentication, persistence or host-specific
business objects.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .errors import FiscalValidationError
from .primitives import ExecutionScope, FiscalEnvironment, _required_text

_NAMESPACE_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9._-]{0,62}[a-z0-9])?$")


@dataclass(frozen=True, slots=True)
class HostNamespace:
    """Stable namespace that identifies one external consumer/application."""

    value: str

    def __post_init__(self) -> None:
        value = _required_text(self.value, "host_namespace", max_length=64).lower()
        if not _NAMESPACE_PATTERN.fullmatch(value):
            raise FiscalValidationError(
                "host_namespace must use lowercase letters, digits, '.', '_' or '-' "
                "and must start/end with an alphanumeric character"
            )
        object.__setattr__(self, "value", value)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class HostScope:
    """Exact external SaaS scope before it is mapped into FM Fiscal."""

    namespace: HostNamespace
    tenant_id: str
    unit_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.namespace, HostNamespace):
            raise FiscalValidationError("namespace must be a HostNamespace")
        object.__setattr__(
            self,
            "tenant_id",
            _required_text(self.tenant_id, "external_tenant_id", max_length=128),
        )
        object.__setattr__(
            self,
            "unit_id",
            _required_text(self.unit_id, "external_unit_id", max_length=128),
        )

    @property
    def canonical_key(self) -> tuple[str, str, str]:
        """Collision-safe external identity key."""

        return (self.namespace.value, self.tenant_id, self.unit_id)


@dataclass(frozen=True, slots=True)
class FiscalAccountId:
    """Opaque canonical identifier for an FM Fiscal account."""

    value: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "value",
            _required_text(self.value, "fiscal_account_id", max_length=128),
        )

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class FiscalUnitId:
    """Opaque canonical identifier for an FM Fiscal unit/establishment."""

    value: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "value",
            _required_text(self.value, "fiscal_unit_id", max_length=128),
        )

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class FiscalAccountBinding:
    """Exact mapping from one external host scope to an internal fiscal scope."""

    binding_id: str
    host_scope: HostScope
    fiscal_account_id: FiscalAccountId
    fiscal_unit_id: FiscalUnitId

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "binding_id",
            _required_text(self.binding_id, "binding_id", max_length=128),
        )
        if not isinstance(self.host_scope, HostScope):
            raise FiscalValidationError("host_scope must be a HostScope")
        if not isinstance(self.fiscal_account_id, FiscalAccountId):
            raise FiscalValidationError("fiscal_account_id must be a FiscalAccountId")
        if not isinstance(self.fiscal_unit_id, FiscalUnitId):
            raise FiscalValidationError("fiscal_unit_id must be a FiscalUnitId")

    @property
    def host_key(self) -> tuple[str, str, str]:
        return self.host_scope.canonical_key

    def to_execution_scope(
        self,
        *,
        environment: FiscalEnvironment,
        correlation_id: str,
    ) -> ExecutionScope:
        """Create the internal scope without promoting external IDs to fiscal authority."""

        if not isinstance(environment, FiscalEnvironment):
            raise FiscalValidationError("environment must be a FiscalEnvironment")
        return ExecutionScope(
            tenant_id=self.fiscal_account_id.value,
            unit_id=self.fiscal_unit_id.value,
            environment=environment,
            correlation_id=correlation_id,
        )


class FiscalBindingRegistry:
    """Pure in-memory resolver used to define exact binding semantics.

    Durable storage, lifecycle management and authorization are intentionally out
    of scope for V2-02. This resolver exists to make collision and fallback rules
    executable and testable.
    """

    def __init__(self, bindings: tuple[FiscalAccountBinding, ...]) -> None:
        by_host_key: dict[tuple[str, str, str], FiscalAccountBinding] = {}
        binding_ids: set[str] = set()

        for binding in bindings:
            if not isinstance(binding, FiscalAccountBinding):
                raise FiscalValidationError("all bindings must be FiscalAccountBinding instances")
            if binding.binding_id in binding_ids:
                raise FiscalValidationError(f"duplicate binding_id: {binding.binding_id}")
            if binding.host_key in by_host_key:
                raise FiscalValidationError(
                    "duplicate fiscal binding for host scope: "
                    f"{binding.host_scope.namespace.value}/"
                    f"{binding.host_scope.tenant_id}/"
                    f"{binding.host_scope.unit_id}"
                )
            binding_ids.add(binding.binding_id)
            by_host_key[binding.host_key] = binding

        self._by_host_key = by_host_key

    def resolve(self, host_scope: HostScope) -> FiscalAccountBinding:
        """Resolve only the exact host namespace + tenant + unit key."""

        if not isinstance(host_scope, HostScope):
            raise FiscalValidationError("host_scope must be a HostScope")
        try:
            return self._by_host_key[host_scope.canonical_key]
        except KeyError as exc:
            raise FiscalValidationError(
                "no fiscal account binding exists for the exact host scope"
            ) from exc

    def execution_scope(
        self,
        host_scope: HostScope,
        *,
        environment: FiscalEnvironment,
        correlation_id: str,
    ) -> ExecutionScope:
        """Resolve an external host scope into an internal fiscal execution scope."""

        binding = self.resolve(host_scope)
        return binding.to_execution_scope(
            environment=environment,
            correlation_id=correlation_id,
        )
