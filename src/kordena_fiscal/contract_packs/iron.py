"""Iron Fit Product Contract Pack.

The pack declares fitness, membership and recurring-service fiscal use cases using
only canonical FM Fiscal contracts. It imports no Iron Fit private domain model and
does not promote jurisdiction readiness or production approval.
"""

from __future__ import annotations

from dataclasses import dataclass

from kordena_fiscal.compliance import FiscalActionCapability
from kordena_fiscal.domain import FiscalDocumentKind
from kordena_fiscal.operations import FiscalOperationKind

from .base import ProductContractPackDescriptor, ProductUseCaseDescriptor

IRON_HOST_NAMESPACE = "fm.iron"
IRON_PACK_ID = "iron"

_DOCUMENT_EVENTS = (
    "fiscal.document.authorized",
    "fiscal.document.rejected",
    "fiscal.document.cancelled",
    "fiscal.issuance.updated",
    "fiscal.reconciliation.updated",
    "fiscal.archive.reference.created",
)

_NFSE_ACTIONS = frozenset(
    {
        FiscalActionCapability.ISSUE,
        FiscalActionCapability.QUERY,
        FiscalActionCapability.CANCEL,
        FiscalActionCapability.RECONCILE,
        FiscalActionCapability.ARCHIVE_REFERENCE,
    }
)

IRON_MEMBERSHIP_BILLING = ProductUseCaseDescriptor(
    use_case_id="membership-billing",
    operation_kinds=frozenset({FiscalOperationKind.MEMBERSHIP}),
    document_kinds=frozenset({FiscalDocumentKind.NFSE}),
    fiscal_actions=_NFSE_ACTIONS,
    vertical_module_id="fitness",
    required_vertical_capabilities=frozenset({"operation.membership"}),
    inbound_event_types=_DOCUMENT_EVENTS,
    description=(
        "Fitness membership billing mapped to the canonical membership operation "
        "and NFS-e contract family. Readiness is decided by FM Fiscal Core."
    ),
)

IRON_RECURRING_MEMBERSHIP_BILLING = ProductUseCaseDescriptor(
    use_case_id="recurring-membership-billing",
    operation_kinds=frozenset({FiscalOperationKind.RECURRING_CHARGE}),
    document_kinds=frozenset({FiscalDocumentKind.NFSE}),
    fiscal_actions=_NFSE_ACTIONS,
    vertical_module_id="fitness",
    required_vertical_capabilities=frozenset({"operation.recurring"}),
    inbound_event_types=_DOCUMENT_EVENTS,
    description=(
        "Recurring fitness charge mapped to the canonical recurring-charge operation "
        "and NFS-e contract family without inferring settlement or readiness."
    ),
)

IRON_SERVICE_BILLING = ProductUseCaseDescriptor(
    use_case_id="fitness-service-billing",
    operation_kinds=frozenset({FiscalOperationKind.SERVICE}),
    document_kinds=frozenset({FiscalDocumentKind.NFSE}),
    fiscal_actions=_NFSE_ACTIONS,
    vertical_module_id="fitness",
    required_vertical_capabilities=frozenset({"operation.service"}),
    inbound_event_types=_DOCUMENT_EVENTS,
    description=(
        "Standalone fitness service mapped to the canonical service operation and "
        "NFS-e contract family."
    ),
)

IRON_CONTRACT_DESCRIPTOR = ProductContractPackDescriptor(
    pack_id=IRON_PACK_ID,
    host_namespace=IRON_HOST_NAMESPACE,
    version="1",
    use_cases=(
        IRON_MEMBERSHIP_BILLING,
        IRON_RECURRING_MEMBERSHIP_BILLING,
        IRON_SERVICE_BILLING,
    ),
    description=(
        "Iron Fit membership/service contract pack. Contains no private Iron Fit "
        "models and grants no fiscal readiness."
    ),
)


@dataclass(frozen=True, slots=True)
class IronFiscalContractPack:
    """Concrete Iron Fit declaration for the V2-10 multiproduct boundary."""

    @property
    def descriptor(self) -> ProductContractPackDescriptor:
        return IRON_CONTRACT_DESCRIPTOR


IRON_FISCAL_CONTRACT_PACK = IronFiscalContractPack()

__all__ = [
    "IRON_CONTRACT_DESCRIPTOR",
    "IRON_FISCAL_CONTRACT_PACK",
    "IRON_HOST_NAMESPACE",
    "IRON_MEMBERSHIP_BILLING",
    "IRON_PACK_ID",
    "IRON_RECURRING_MEMBERSHIP_BILLING",
    "IRON_SERVICE_BILLING",
    "IronFiscalContractPack",
]
