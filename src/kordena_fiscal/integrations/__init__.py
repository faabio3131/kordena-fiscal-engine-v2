"""FM product integration boundaries for the fiscal core."""

from .contract import (
    CAPABILITIES_ENDPOINT,
    FM_FISCAL_API_VERSION,
    IDEMPOTENCY_HEADER,
    ISSUANCES_ENDPOINT,
    QUERIES_ENDPOINT,
    RECONCILIATIONS_ENDPOINT,
    REQUIRED_SCOPE_HEADERS,
    ProductIntegrationContract,
    resolve_product_integration_contract,
)

__all__ = [
    "CAPABILITIES_ENDPOINT",
    "FM_FISCAL_API_VERSION",
    "IDEMPOTENCY_HEADER",
    "ISSUANCES_ENDPOINT",
    "ProductIntegrationContract",
    "QUERIES_ENDPOINT",
    "RECONCILIATIONS_ENDPOINT",
    "REQUIRED_SCOPE_HEADERS",
    "resolve_product_integration_contract",
]
