"""R16 composition: reuse canonical provider registry, readiness and durable bindings.

This factory does not initialize separate credentials, a second provider
registry, or a new API. Call it only from an authorized fiscal deployment
composition with the canonical UOW and preconfigured provider adapters.
"""
from __future__ import annotations

from kordena_fiscal.compliance import CapabilityReadinessService
from kordena_fiscal.control_plane.commercial import DurableProviderBindingResolver
from kordena_fiscal.gateway.municipal_sp_routing import GovernedSpMunicipalProviderResolver
from kordena_fiscal.gateway.provider import ProviderGatewayService, ProviderRegistry
from kordena_fiscal.persistence.ports import FiscalUnitOfWorkFactory


def build_governed_sp_municipal_gateway(
    *,
    unit_of_work_factory: FiscalUnitOfWorkFactory,
    registry: ProviderRegistry,
    readiness: CapabilityReadinessService,
) -> ProviderGatewayService:
    """Compose R16 on the existing durable provider-selection authority."""
    return ProviderGatewayService(
        registry=registry,
        readiness=readiness,
        provider_selector=GovernedSpMunicipalProviderResolver(
            canonical_resolver=DurableProviderBindingResolver(unit_of_work_factory)
        ),
    )
