"""Existing durable resolver is the only authority for five pilot cities."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

import pytest

from kordena_fiscal.control_plane.commercial import (
    ConfiguredFiscalOperation,
    DurableProviderBindingResolver,
    ProviderBinding,
)
from kordena_fiscal.control_plane.national_priority_inventory import NAT_PRIORITY_PILOTS
from kordena_fiscal.domain import (
    BrazilianJurisdiction,
    ExecutionScope,
    FiscalDocumentKind,
    FiscalEnvironment,
)
from kordena_fiscal.persistence.ports import FiscalUnitOfWorkFactory


@dataclass
class _Commercial:
    approved: ProviderBinding | None

    def resolve_provider_binding(self, **kwargs: Any) -> ProviderBinding | None:
        binding = self.approved
        if binding is None:
            return None
        if (
            kwargs["tenant_id"], kwargs["unit_id"], kwargs["environment"],
            kwargs["document_kind"], kwargs["jurisdiction"], kwargs["operation"]
        ) != (
            binding.tenant_id, binding.unit_id, binding.environment,
            binding.document_kind, binding.jurisdiction, binding.operation
        ):
            return None
        return binding


class _Uow:
    def __init__(self, binding: ProviderBinding | None) -> None:
        self.commercial = _Commercial(binding)

    def __enter__(self) -> _Uow:
        return self

    def __exit__(self, *_args: object) -> None:
        return None


def _scope(
    *, tenant: str = "tenant-mg", unit: str = "unit-a",
    environment: FiscalEnvironment = FiscalEnvironment.HOMOLOGATION,
) -> ExecutionScope:
    return ExecutionScope(
        host_namespace="nfcore", tenant_id=tenant, unit_id=unit,
        environment=environment, correlation_id="nat-priority-resolver",
    )


@pytest.mark.parametrize("pilot", NAT_PRIORITY_PILOTS, ids=lambda pilot: pilot.uf)
def test_pilot_needs_explicit_durable_binding_before_any_route(pilot: Any) -> None:
    jurisdiction = BrazilianJurisdiction(pilot.uf, pilot.municipality_ibge)
    approved = ProviderBinding(
        binding_id=f"pilot-{pilot.uf.lower()}-approved",
        tenant_id="tenant-mg",
        unit_id="unit-a",
        environment=FiscalEnvironment.HOMOLOGATION,
        document_kind=FiscalDocumentKind.NFSE,
        jurisdiction=jurisdiction,
        operation=ConfiguredFiscalOperation.AUTHORIZE,
        provider_id=f"provider-{pilot.uf.lower()}-contract-tested",
    )
    from kordena_fiscal.control_plane.service import ControlPlaneNotFoundError

    blocked = DurableProviderBindingResolver(
        cast(FiscalUnitOfWorkFactory, lambda: _Uow(None))
    )
    with pytest.raises(ControlPlaneNotFoundError):
        blocked.resolve_provider_id(
            scope=_scope(), document_kind=FiscalDocumentKind.NFSE,
            jurisdiction=jurisdiction, operation="authorize",
        )
    resolver = DurableProviderBindingResolver(
        cast(FiscalUnitOfWorkFactory, lambda: _Uow(approved))
    )
    assert resolver.resolve_provider_id(
        scope=_scope(), document_kind=FiscalDocumentKind.NFSE,
        jurisdiction=jurisdiction, operation="authorize",
    ) == approved.provider_id
    for modified_scope in (
        _scope(tenant="other-tenant"), _scope(unit="other-unit"),
        _scope(environment=FiscalEnvironment.PRODUCTION),
    ):
        with pytest.raises(ControlPlaneNotFoundError):
            resolver.resolve_provider_id(
                scope=modified_scope, document_kind=FiscalDocumentKind.NFSE,
                jurisdiction=jurisdiction, operation="authorize",
            )
    with pytest.raises(ControlPlaneNotFoundError):
        resolver.resolve_provider_id(
            scope=_scope(), document_kind=FiscalDocumentKind.NFE,
            jurisdiction=jurisdiction, operation="authorize",
        )


def test_non_pilot_mg_city_can_join_by_governed_binding_without_code_deploy() -> None:
    """The same authority serves any MG IBGE; the initial catalog is not an allowlist."""
    assert all(pilot.municipality_ibge != "3170206" for pilot in NAT_PRIORITY_PILOTS)
    approved = ProviderBinding(
        binding_id="pilot-uberlandia-mg",
        tenant_id="tenant-mg", unit_id="unit-a",
        environment=FiscalEnvironment.HOMOLOGATION,
        document_kind=FiscalDocumentKind.NFSE,
        jurisdiction=BrazilianJurisdiction("MG", "3170206"),
        operation=ConfiguredFiscalOperation.AUTHORIZE,
        provider_id="provider-contrato-validado",
    )
    resolver = DurableProviderBindingResolver(
        cast(FiscalUnitOfWorkFactory, lambda: _Uow(approved))
    )
    assert resolver.resolve_provider_id(
        scope=_scope(), document_kind=FiscalDocumentKind.NFSE,
        jurisdiction=BrazilianJurisdiction("MG", "3170206"),
        operation="authorize",
    ) == "provider-contrato-validado"
