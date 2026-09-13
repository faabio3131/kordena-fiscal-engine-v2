"""Governed product-to-FM-Fiscal integration boundary for V2-16.

This module binds certified Product Contract Packs to the public FM Fiscal Bridge
without turning a declared mapping into a readiness or homologation claim. Runtime
capability/readiness remains authoritative and must be checked before mutation.
"""

from __future__ import annotations

from dataclasses import dataclass

from kordena_fiscal.compliance import FiscalActionCapability
from kordena_fiscal.contract_packs.catalog import FM_PRODUCT_CONTRACT_REGISTRY
from kordena_fiscal.domain import FiscalDocumentKind
from kordena_fiscal.operations import FiscalOperationKind

FM_FISCAL_API_VERSION = "v1"
CAPABILITIES_ENDPOINT = "/v1/fiscal/capabilities"
ISSUANCES_ENDPOINT = "/v1/fiscal/issuances"
OPERATIONS_ENDPOINT_TEMPLATE = "/v1/fiscal/operations/{operation_id}"
RECONCILIATION_ENDPOINT = "/v1/fiscal/reconciliation"
WEBHOOKS_ENDPOINT = "/v1/fiscal/webhooks"

REQUIRED_SCOPE_HEADERS: tuple[str, ...] = (
    "X-Tenant-Id",
    "X-Unit-Id",
    "X-Correlation-Id",
    "X-Host-System-Id",
)
IDEMPOTENCY_HEADER = "Idempotency-Key"


@dataclass(frozen=True, slots=True)
class ProductIntegrationContract:
    """Resolved product use-case contract at the FM Fiscal Bridge boundary.

    The object is intentionally descriptive. It grants neither jurisdictional
    support nor production readiness. Consumers must consult ``capabilities_endpoint``
    before any mutating fiscal request.
    """

    pack_id: str
    pack_version: str
    host_namespace: str
    use_case_id: str
    operation_kinds: frozenset[FiscalOperationKind]
    document_kinds: frozenset[FiscalDocumentKind]
    fiscal_actions: frozenset[FiscalActionCapability]
    outbound_event_types: tuple[str, ...]
    inbound_event_types: tuple[str, ...]
    api_version: str = FM_FISCAL_API_VERSION
    capabilities_endpoint: str = CAPABILITIES_ENDPOINT
    issuance_endpoint: str = ISSUANCES_ENDPOINT
    operation_endpoint_template: str = OPERATIONS_ENDPOINT_TEMPLATE
    reconciliation_endpoint: str = RECONCILIATION_ENDPOINT
    webhooks_endpoint: str = WEBHOOKS_ENDPOINT
    required_scope_headers: tuple[str, ...] = REQUIRED_SCOPE_HEADERS
    idempotency_header: str = IDEMPOTENCY_HEADER
    readiness_required_before_mutation: bool = True


def resolve_product_integration_contract(
    pack_id: str,
    use_case_id: str,
) -> ProductIntegrationContract:
    """Resolve a certified pack/use-case onto the public bridge contract.

    Unknown packs/use cases fail closed through the existing Product Contract Pack
    registry. No fallback, readiness inference or production approval is performed.
    """

    pack = FM_PRODUCT_CONTRACT_REGISTRY.require(pack_id)
    descriptor = pack.descriptor
    use_case = descriptor.require_use_case(use_case_id)
    return ProductIntegrationContract(
        pack_id=descriptor.pack_id,
        pack_version=descriptor.version,
        host_namespace=descriptor.host_namespace,
        use_case_id=use_case.use_case_id,
        operation_kinds=use_case.operation_kinds,
        document_kinds=use_case.document_kinds,
        fiscal_actions=use_case.fiscal_actions,
        outbound_event_types=use_case.outbound_event_types,
        inbound_event_types=use_case.inbound_event_types,
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
