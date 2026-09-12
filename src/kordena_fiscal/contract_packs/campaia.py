"""CampaIA Product Contract Pack.

CampaIA is modeled only for its own taxable service/SaaS billing facts. The pack
imports no private CampaIA domain model and never infers tax, payment, settlement,
jurisdiction readiness or production approval from product identity alone.
"""

from __future__ import annotations

from dataclasses import dataclass

from kordena_fiscal.compliance import FiscalActionCapability
from kordena_fiscal.domain import FiscalDocumentKind
from kordena_fiscal.operations import FiscalOperationKind

from .base import ProductContractPackDescriptor, ProductUseCaseDescriptor

CAMPAIA_HOST_NAMESPACE = "fm.campaia"
CAMPAIA_PACK_ID = "campaia"

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

CAMPAIA_SERVICE_BILLING = ProductUseCaseDescriptor(
    use_case_id="service-billing",
    operation_kinds=frozenset({FiscalOperationKind.SERVICE}),
    document_kinds=frozenset({FiscalDocumentKind.NFSE}),
    fiscal_actions=_NFSE_ACTIONS,
    vertical_module_id="service",
    required_vertical_capabilities=frozenset({"operation.service"}),
    inbound_event_types=_DOCUMENT_EVENTS,
    description=(
        "CampaIA own taxable service billing mapped to canonical SERVICE + NFS-e. "
        "The pack does not infer service tax facts, jurisdiction or readiness."
    ),
)

CAMPAIA_SAAS_BILLING = ProductUseCaseDescriptor(
    use_case_id="saas-billing",
    operation_kinds=frozenset({FiscalOperationKind.SAAS_BILLING}),
    document_kinds=frozenset({FiscalDocumentKind.NFSE}),
    fiscal_actions=_NFSE_ACTIONS,
    vertical_module_id="saas",
    required_vertical_capabilities=frozenset(
        {
            "operation.service",
            "operation.subscription",
        }
    ),
    inbound_event_types=_DOCUMENT_EVENTS,
    description=(
        "CampaIA own SaaS billing mapped to canonical SAAS_BILLING + NFS-e using "
        "the neutral SaaS vertical. Payment and fiscal sufficiency remain explicit."
    ),
)

CAMPAIA_CONTRACT_DESCRIPTOR = ProductContractPackDescriptor(
    pack_id=CAMPAIA_PACK_ID,
    host_namespace=CAMPAIA_HOST_NAMESPACE,
    version="1",
    use_cases=(CAMPAIA_SERVICE_BILLING, CAMPAIA_SAAS_BILLING),
    description=(
        "CampaIA own service/SaaS billing contract pack. Contains no private CampaIA "
        "models and grants no fiscal readiness."
    ),
)


@dataclass(frozen=True, slots=True)
class CampaiaFiscalContractPack:
    """Concrete CampaIA declaration for the V2-10 multiproduct boundary."""

    @property
    def descriptor(self) -> ProductContractPackDescriptor:
        return CAMPAIA_CONTRACT_DESCRIPTOR


CAMPAIA_FISCAL_CONTRACT_PACK = CampaiaFiscalContractPack()

__all__ = [
    "CAMPAIA_CONTRACT_DESCRIPTOR",
    "CAMPAIA_FISCAL_CONTRACT_PACK",
    "CAMPAIA_HOST_NAMESPACE",
    "CAMPAIA_PACK_ID",
    "CAMPAIA_SAAS_BILLING",
    "CAMPAIA_SERVICE_BILLING",
    "CampaiaFiscalContractPack",
]
