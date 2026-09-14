"""Vendedor IA / generic sales Product Contract Pack.

This pack maps explicit sales use cases onto canonical FM Fiscal contracts without
importing Vendedor IA private domain models. It intentionally does not infer
payment authority, settlement, vertical-specific tax rules or jurisdiction
readiness from the product context.
"""

from __future__ import annotations

from dataclasses import dataclass

from kordena_fiscal.compliance import FiscalActionCapability
from kordena_fiscal.domain import FiscalDocumentKind
from kordena_fiscal.operations import FiscalOperationKind

from .base import ProductContractPackDescriptor, ProductUseCaseDescriptor

SALES_HOST_NAMESPACE = "fm.vendedor-ia"
SALES_PACK_ID = "sales"

_DOCUMENT_EVENTS = (
    "fiscal.document.authorized",
    "fiscal.document.rejected",
    "fiscal.document.cancelled",
    "fiscal.issuance.updated",
    "fiscal.reconciliation.updated",
    "fiscal.archive.reference.created",
)

_COMMON_SALE_ACTIONS = frozenset(
    {
        FiscalActionCapability.ISSUE,
        FiscalActionCapability.QUERY,
        FiscalActionCapability.CANCEL,
        FiscalActionCapability.RECONCILE,
        FiscalActionCapability.ARCHIVE_REFERENCE,
    }
)

SALES_NFCE_SALE = ProductUseCaseDescriptor(
    use_case_id="nfce-sale",
    operation_kinds=frozenset({FiscalOperationKind.SALE}),
    document_kinds=frozenset({FiscalDocumentKind.NFCE}),
    fiscal_actions=_COMMON_SALE_ACTIONS
    | frozenset({FiscalActionCapability.CONTINGENCY}),
    inbound_event_types=_DOCUMENT_EVENTS,
    description=(
        "Generic sale mapped to the NFC-e contract family. The host must provide "
        "sufficient fiscal facts; payment and settlement are never inferred by the pack."
    ),
)

SALES_NFE_SALE = ProductUseCaseDescriptor(
    use_case_id="nfe-sale",
    operation_kinds=frozenset({FiscalOperationKind.SALE}),
    document_kinds=frozenset({FiscalDocumentKind.NFE}),
    fiscal_actions=_COMMON_SALE_ACTIONS
    | frozenset(
        {
            FiscalActionCapability.INUTILIZE,
            FiscalActionCapability.CONTINGENCY,
        }
    ),
    inbound_event_types=_DOCUMENT_EVENTS,
    description=(
        "Generic sale mapped to the NF-e contract family. Availability, jurisdiction "
        "readiness and production approval remain external to this pack."
    ),
)

SALES_CONTRACT_DESCRIPTOR = ProductContractPackDescriptor(
    pack_id=SALES_PACK_ID,
    host_namespace=SALES_HOST_NAMESPACE,
    version="1",
    use_cases=(SALES_NFCE_SALE, SALES_NFE_SALE),
    description=(
        "Vendedor IA generic sales contract pack. Contains no private Vendedor IA "
        "models, vertical-specific rules or implicit payment authority."
    ),
)


@dataclass(frozen=True, slots=True)
class SalesFiscalContractPack:
    """Concrete Vendedor IA declaration for the V2-10 multiproduct boundary."""

    @property
    def descriptor(self) -> ProductContractPackDescriptor:
        return SALES_CONTRACT_DESCRIPTOR


SALES_FISCAL_CONTRACT_PACK = SalesFiscalContractPack()

__all__ = [
    "SALES_CONTRACT_DESCRIPTOR",
    "SALES_FISCAL_CONTRACT_PACK",
    "SALES_HOST_NAMESPACE",
    "SALES_NFCE_SALE",
    "SALES_NFE_SALE",
    "SALES_PACK_ID",
    "SalesFiscalContractPack",
]
