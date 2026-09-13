from __future__ import annotations

from datetime import UTC, datetime

from kordena_fiscal.domain import (
    BrazilianJurisdiction,
    ExecutionScope,
    FiscalDocumentKind,
    FiscalEnvironment,
)
from kordena_fiscal.gateway import (
    ProviderGatewayService,
    ProviderOperation,
    ProviderRequest,
    ProviderResponse,
    ProviderResponseStatus,
)


class _Readiness:
    def require_action(self, **kwargs: object) -> None:
        self.kwargs = kwargs


class _Selector:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def resolve_provider_id(self, **kwargs: object) -> str:
        self.calls.append(dict(kwargs))
        return "provider-from-config"


class _Adapter:
    def execute(self, request: ProviderRequest) -> ProviderResponse:
        return ProviderResponse(
            provider_id="provider-from-config",
            operation=request.operation,
            status=ProviderResponseStatus.FOUND,
            correlation_id=request.correlation_id,
        )


class _Registry:
    def __init__(self) -> None:
        self.provider_id: str | None = None

    def resolve(self, **kwargs: object) -> _Adapter:
        provider_id = kwargs.get("provider_id")
        assert isinstance(provider_id, str)
        self.provider_id = provider_id
        return _Adapter()


class _Clock:
    def now(self) -> datetime:
        return datetime(2026, 9, 13, 15, tzinfo=UTC)


def test_gateway_uses_injected_customer_configuration_for_provider_selection() -> None:
    selector = _Selector()
    registry = _Registry()
    gateway = ProviderGatewayService(
        registry=registry,  # type: ignore[arg-type]
        readiness=_Readiness(),  # type: ignore[arg-type]
        clock=_Clock(),
        provider_selector=selector,
    )
    jurisdiction = BrazilianJurisdiction("SP")
    scope = ExecutionScope(
        host_namespace="fm.kordena",
        tenant_id="tenant-config",
        unit_id="unit-config",
        environment=FiscalEnvironment.HOMOLOGATION,
        correlation_id="corr-provider-selection",
    )
    request = ProviderRequest(
        scope=scope,
        document_kind=FiscalDocumentKind.NFE,
        jurisdiction=jurisdiction,
        operation=ProviderOperation.QUERY,
        payload=b"synthetic-query",
        correlation_id=scope.correlation_id,
        workload_id="fiscal-runtime",
    )

    response = gateway.execute(request)

    assert response.provider_id == "provider-from-config"
    assert registry.provider_id == "provider-from-config"
    assert selector.calls == [
        {
            "scope": scope,
            "document_kind": FiscalDocumentKind.NFE,
            "jurisdiction": jurisdiction,
            "operation": "query",
        }
    ]
