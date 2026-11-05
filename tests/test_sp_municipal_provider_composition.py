"""Integration contract: R16 factory delegates to existing durable Control Plane."""
from __future__ import annotations

from typing import Any, cast

from kordena_fiscal.compliance import CapabilityReadinessService
from kordena_fiscal.control_plane.commercial import (
    ConfiguredFiscalOperation,
    ProviderBinding,
)
from kordena_fiscal.domain import (
    BrazilianJurisdiction,
    ExecutionScope,
    FiscalDocumentKind,
    FiscalEnvironment,
)
from kordena_fiscal.gateway.provider import (
    ProviderGatewayService,
    ProviderRegistry,
)
from kordena_fiscal.persistence.ports import FiscalUnitOfWorkFactory
from kordena_fiscal.runtime.sp_municipal_provider_composition import (
    build_governed_sp_municipal_gateway,
)


class _CommercialState:
    def resolve_provider_binding(self, **kwargs: Any) -> ProviderBinding | None:
        assert kwargs["tenant_id"] == "tenant-1"
        assert kwargs["unit_id"] == "unit-1"
        assert kwargs["document_kind"] is FiscalDocumentKind.NFSE
        assert kwargs["jurisdiction"].municipality_ibge_code == "3550308"
        assert kwargs["operation"] is ConfiguredFiscalOperation.AUTHORIZE
        return ProviderBinding(
            binding_id="r16-sp-approved",
            tenant_id="tenant-1",
            unit_id="unit-1",
            environment=FiscalEnvironment.HOMOLOGATION,
            document_kind=FiscalDocumentKind.NFSE,
            jurisdiction=BrazilianJurisdiction("SP", "3550308"),
            operation=ConfiguredFiscalOperation.AUTHORIZE,
            provider_id="nota-paulistana",
        )


class _Uow:
    def __init__(self) -> None:
        self.commercial = _CommercialState()

    def __enter__(self) -> _Uow:
        return self

    def __exit__(self, *_args: object) -> None:
        return None


def test_factory_delegates_to_control_plane_persisted_provider_binding() -> None:
    service = build_governed_sp_municipal_gateway(
        unit_of_work_factory=cast(FiscalUnitOfWorkFactory, lambda: _Uow()),
        registry=cast(ProviderRegistry, object()),
        readiness=cast(CapabilityReadinessService, object()),
    )
    assert isinstance(service, ProviderGatewayService)
    selector = service._provider_selector
    assert selector is not None
    scope = ExecutionScope(
        host_namespace="nfcore", tenant_id="tenant-1", unit_id="unit-1",
        environment=FiscalEnvironment.HOMOLOGATION, correlation_id="r16",
    )
    assert selector.resolve_provider_id(
        scope=scope,
        document_kind=FiscalDocumentKind.NFSE,
        jurisdiction=BrazilianJurisdiction("SP", "3550308"),
        operation="authorize",
    ) == "nota-paulistana"
