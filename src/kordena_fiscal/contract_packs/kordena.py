"""Kordena Product Contract Pack.

This module declares Kordena's host-facing fiscal use cases without importing
Kordena's private domain models. It is an integration contract only: jurisdiction
readiness and production approval remain authority of the common FM Fiscal Core.
"""

from __future__ import annotations

from dataclasses import dataclass

from kordena_fiscal.compliance import FiscalActionCapability
from kordena_fiscal.domain import FiscalDocumentKind
from kordena_fiscal.operations import FiscalOperationKind

from .base import ProductContractPackDescriptor, ProductUseCaseDescriptor

KORDENA_HOST_NAMESPACE = "fm.kordena"
KORDENA_PACK_ID = "kordena"

_DOCUMENT_EVENTS = (
    "fiscal.document.authorized",
    "fiscal.document.rejected",
    "fiscal.document.cancelled",
    "fiscal.issuance.updated",
    "fiscal.reconciliation.updated",
    "fiscal.archive.reference.created",
)

_RESTAURANT_CAPABILITIES = frozenset(
    {
        "tax.restaurant.supply-classification",
        "tax.restaurant.base-adjustments",
    }
)

_COMMON_DOCUMENT_ACTIONS = frozenset(
    {
        FiscalActionCapability.ISSUE,
        FiscalActionCapability.QUERY,
        FiscalActionCapability.CANCEL,
        FiscalActionCapability.RECONCILE,
        FiscalActionCapability.ARCHIVE_REFERENCE,
    }
)

KORDENA_RESTAURANT_POS_SALE = ProductUseCaseDescriptor(
    use_case_id="restaurant-pos-sale",
    operation_kinds=frozenset({FiscalOperationKind.SALE}),
    document_kinds=frozenset({FiscalDocumentKind.NFCE}),
    fiscal_actions=_COMMON_DOCUMENT_ACTIONS
    | frozenset({FiscalActionCapability.CONTINGENCY}),
    vertical_module_id="restaurant",
    required_vertical_capabilities=_RESTAURANT_CAPABILITIES,
    inbound_event_types=_DOCUMENT_EVENTS,
    description=(
        "Restaurant point-of-sale sale mapped to the canonical sale operation and "
        "NFC-e contract family. Fiscal readiness remains external to this pack."
    ),
)

KORDENA_RESTAURANT_INVOICE_SALE = ProductUseCaseDescriptor(
    use_case_id="restaurant-invoice-sale",
    operation_kinds=frozenset({FiscalOperationKind.SALE}),
    document_kinds=frozenset({FiscalDocumentKind.NFE}),
    fiscal_actions=_COMMON_DOCUMENT_ACTIONS
    | frozenset(
        {
            FiscalActionCapability.INUTILIZE,
            FiscalActionCapability.CONTINGENCY,
        }
    ),
    vertical_module_id="restaurant",
    required_vertical_capabilities=_RESTAURANT_CAPABILITIES,
    inbound_event_types=_DOCUMENT_EVENTS,
    description=(
        "Restaurant invoiced sale mapped to the canonical sale operation and NF-e "
        "contract family. Availability is decided by Capability & Readiness."
    ),
)

KORDENA_CONTRACT_DESCRIPTOR = ProductContractPackDescriptor(
    pack_id=KORDENA_PACK_ID,
    host_namespace=KORDENA_HOST_NAMESPACE,
    version="1",
    use_cases=(
        KORDENA_RESTAURANT_POS_SALE,
        KORDENA_RESTAURANT_INVOICE_SALE,
    ),
    description=(
        "Kordena restaurant sales contract pack. Contains no private Kordena models "
        "and grants no fiscal readiness."
    ),
)


@dataclass(frozen=True, slots=True)
class KordenaFiscalContractPack:
    """Concrete declaration required by the V2-10 multiproduct boundary."""

    @property
    def descriptor(self) -> ProductContractPackDescriptor:
        return KORDENA_CONTRACT_DESCRIPTOR


KORDENA_FISCAL_CONTRACT_PACK = KordenaFiscalContractPack()

__all__ = [
    "KORDENA_CONTRACT_DESCRIPTOR",
    "KORDENA_FISCAL_CONTRACT_PACK",
    "KORDENA_HOST_NAMESPACE",
    "KORDENA_PACK_ID",
    "KORDENA_RESTAURANT_INVOICE_SALE",
    "KORDENA_RESTAURANT_POS_SALE",
    "KordenaFiscalContractPack",
]
