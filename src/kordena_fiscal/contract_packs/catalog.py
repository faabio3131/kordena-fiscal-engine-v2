"""Governed FM Product Contract Pack catalog and generated matrix.

The catalog is the explicit multiproduct composition boundary for V2-10. Matrix
rows are derived from certified pack descriptors so contract documentation/tests do
not duplicate product mappings or become a second source of fiscal truth.
"""

from __future__ import annotations

from dataclasses import dataclass

from kordena_fiscal.compliance import FiscalActionCapability
from kordena_fiscal.domain import FiscalDocumentKind
from kordena_fiscal.operations import FiscalOperationKind

from .base import ProductContractPackRegistry, ProductFiscalContractPack
from .campaia import CAMPAIA_FISCAL_CONTRACT_PACK
from .iron import IRON_FISCAL_CONTRACT_PACK
from .kordena import KORDENA_FISCAL_CONTRACT_PACK
from .sales import SALES_FISCAL_CONTRACT_PACK

FM_PRODUCT_CONTRACT_PACKS: tuple[ProductFiscalContractPack, ...] = (
    KORDENA_FISCAL_CONTRACT_PACK,
    IRON_FISCAL_CONTRACT_PACK,
    SALES_FISCAL_CONTRACT_PACK,
    CAMPAIA_FISCAL_CONTRACT_PACK,
)

FM_PRODUCT_CONTRACT_REGISTRY = ProductContractPackRegistry(FM_PRODUCT_CONTRACT_PACKS)


@dataclass(frozen=True, slots=True)
class ProductContractMatrixRow:
    """One derived row in the versioned V2-10 multiproduct contract matrix."""

    pack_id: str
    pack_version: str
    host_namespace: str
    use_case_id: str
    operation_kinds: tuple[FiscalOperationKind, ...]
    document_kinds: tuple[FiscalDocumentKind, ...]
    fiscal_actions: tuple[FiscalActionCapability, ...]
    vertical_module_id: str | None
    required_vertical_capabilities: tuple[str, ...]
    inbound_event_types: tuple[str, ...]
    outbound_event_types: tuple[str, ...]


def build_product_contract_matrix(
    packs: tuple[ProductFiscalContractPack, ...] = FM_PRODUCT_CONTRACT_PACKS,
) -> tuple[ProductContractMatrixRow, ...]:
    """Derive a deterministic matrix directly from immutable pack descriptors."""

    rows: list[ProductContractMatrixRow] = []
    for pack in packs:
        descriptor = pack.descriptor
        for use_case in descriptor.use_cases:
            rows.append(
                ProductContractMatrixRow(
                    pack_id=descriptor.pack_id,
                    pack_version=descriptor.version,
                    host_namespace=descriptor.host_namespace,
                    use_case_id=use_case.use_case_id,
                    operation_kinds=tuple(
                        sorted(use_case.operation_kinds, key=lambda item: item.value)
                    ),
                    document_kinds=tuple(
                        sorted(use_case.document_kinds, key=lambda item: item.value)
                    ),
                    fiscal_actions=tuple(
                        sorted(use_case.fiscal_actions, key=lambda item: item.value)
                    ),
                    vertical_module_id=use_case.vertical_module_id,
                    required_vertical_capabilities=tuple(
                        sorted(use_case.required_vertical_capabilities)
                    ),
                    inbound_event_types=tuple(use_case.inbound_event_types),
                    outbound_event_types=tuple(use_case.outbound_event_types),
                )
            )
    return tuple(rows)


V2_10_PRODUCT_CONTRACT_MATRIX = build_product_contract_matrix()

__all__ = [
    "FM_PRODUCT_CONTRACT_PACKS",
    "FM_PRODUCT_CONTRACT_REGISTRY",
    "ProductContractMatrixRow",
    "V2_10_PRODUCT_CONTRACT_MATRIX",
    "build_product_contract_matrix",
]
