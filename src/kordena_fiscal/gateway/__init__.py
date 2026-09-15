"""Provider-neutral fiscal gateway surface."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .authorization import (
    AuthorizationRequest,
    AuthorizationResult,
    AuthorizationStatus,
    FiscalGateway,
    FiscalGatewayClient,
    GatewayContractError,
    GatewayProviderMetadata,
)
from .fake import FakeFiscalGateway, FakeGatewayMode

if TYPE_CHECKING:
    from .production_activation import (
        FiscalProductionActivationError,
        FiscalProductionActivationRequiredError,
        FiscalProductionActivationService,
        FiscalProductionApprovalError,
        GovernedProviderGatewayService,
        HumanProductionApproval,
        OfficialHomologationProof,
        ProductionActivationKey,
        ProductionActivationRecord,
        ProductionActivationState,
        ProductionExecutionAuthority,
    )
    from .provider import (
        ConfiguredProviderAdapter,
        CscUnavailableError,
        FiscalProviderTransport,
        MalformedProviderResponseError,
        ProviderAuthenticationError,
        ProviderCredentialsUnavailableError,
        ProviderDescriptor,
        ProviderGatewayError,
        ProviderGatewayService,
        ProviderOperation,
        ProviderRegistry,
        ProviderRejectedError,
        ProviderRequest,
        ProviderResponse,
        ProviderResponseStatus,
        ProviderSelectionResolver,
        ProviderTimeoutPolicy,
        ProviderTransportError,
        ProviderTransportResponse,
        ProviderUnavailableError,
        UnsupportedJurisdictionError,
        UnsupportedProviderError,
    )
    from .synthetic_transport import SyntheticProviderTransport, SyntheticTransportObservation

_PROVIDER_EXPORTS = {
    "ConfiguredProviderAdapter",
    "CscUnavailableError",
    "FiscalProviderTransport",
    "MalformedProviderResponseError",
    "ProviderAuthenticationError",
    "ProviderCredentialsUnavailableError",
    "ProviderDescriptor",
    "ProviderGatewayError",
    "ProviderGatewayService",
    "ProviderOperation",
    "ProviderRegistry",
    "ProviderRejectedError",
    "ProviderRequest",
    "ProviderResponse",
    "ProviderResponseStatus",
    "ProviderSelectionResolver",
    "ProviderTimeoutPolicy",
    "ProviderTransportError",
    "ProviderTransportResponse",
    "ProviderUnavailableError",
    "UnsupportedJurisdictionError",
    "UnsupportedProviderError",
}
_PRODUCTION_EXPORTS = {
    "FiscalProductionActivationError",
    "FiscalProductionActivationRequiredError",
    "FiscalProductionActivationService",
    "FiscalProductionApprovalError",
    "GovernedProviderGatewayService",
    "HumanProductionApproval",
    "OfficialHomologationProof",
    "ProductionActivationKey",
    "ProductionActivationRecord",
    "ProductionActivationState",
    "ProductionExecutionAuthority",
}
_SYNTHETIC_EXPORTS = {"SyntheticProviderTransport", "SyntheticTransportObservation"}


def __getattr__(name: str) -> Any:
    if name in _PROVIDER_EXPORTS:
        from . import provider

        return getattr(provider, name)
    if name in _PRODUCTION_EXPORTS:
        from . import production_activation

        return getattr(production_activation, name)
    if name in _SYNTHETIC_EXPORTS:
        from . import synthetic_transport

        return getattr(synthetic_transport, name)
    raise AttributeError(name)


__all__ = [
    "AuthorizationRequest",
    "AuthorizationResult",
    "AuthorizationStatus",
    "ConfiguredProviderAdapter",
    "CscUnavailableError",
    "FakeFiscalGateway",
    "FakeGatewayMode",
    "FiscalGateway",
    "FiscalGatewayClient",
    "FiscalProductionActivationError",
    "FiscalProductionActivationRequiredError",
    "FiscalProductionActivationService",
    "FiscalProductionApprovalError",
    "FiscalProviderTransport",
    "GatewayContractError",
    "GatewayProviderMetadata",
    "GovernedProviderGatewayService",
    "HumanProductionApproval",
    "MalformedProviderResponseError",
    "OfficialHomologationProof",
    "ProductionActivationKey",
    "ProductionActivationRecord",
    "ProductionActivationState",
    "ProductionExecutionAuthority",
    "ProviderAuthenticationError",
    "ProviderCredentialsUnavailableError",
    "ProviderDescriptor",
    "ProviderGatewayError",
    "ProviderGatewayService",
    "ProviderOperation",
    "ProviderRegistry",
    "ProviderRejectedError",
    "ProviderRequest",
    "ProviderResponse",
    "ProviderResponseStatus",
    "ProviderSelectionResolver",
    "ProviderTimeoutPolicy",
    "ProviderTransportError",
    "ProviderTransportResponse",
    "ProviderUnavailableError",
    "SyntheticProviderTransport",
    "SyntheticTransportObservation",
    "UnsupportedJurisdictionError",
    "UnsupportedProviderError",
]
