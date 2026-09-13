"""FM product integration boundaries for the fiscal core."""

from .contract import (
    CAPABILITIES_ENDPOINT,
    FM_FISCAL_API_VERSION,
    IDEMPOTENCY_HEADER,
    ISSUANCES_ENDPOINT,
    OPERATIONS_ENDPOINT_TEMPLATE,
    RECONCILIATION_ENDPOINT,
    REQUIRED_SCOPE_HEADERS,
    WEBHOOKS_ENDPOINT,
    ProductIntegrationContract,
    resolve_product_integration_contract,
)

__all__ = [
    "CAPABILITIES_ENDPOINT",
    "FM_FISCAL_API_VERSION",
    "IDEMPOTENCY_HEADER",
    "ISSUANCES_ENDPOINT",
    "OPERATIONS_ENDPOINT_TEMPLATE",
    "ProductIntegrationContract",
    "RECONCILIATION_ENDPOINT",
    "REQUIRED_SCOPE_HEADERS",
    "WEBHOOKS_ENDPOINT",
    "resolve_product_integration_contract",
]
