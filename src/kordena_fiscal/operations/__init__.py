"""Public fiscal operation and document-operation surfaces."""

from .contract import (
    FiscalOperationKind,
    FiscalOperationPayment,
    FiscalOperationSnapshot,
    FiscalOperationTotals,
)
from .events import (
    CancellationOutcome,
    CancellationRequest,
    CancellationResult,
    FiscalCancellationService,
    FiscalEventStatus,
    FiscalOperationsClient,
    FiscalOperationsContractError,
    FiscalOperationsGateway,
    FiscalQueryRequest,
    FiscalQueryResult,
    FiscalQueryStatus,
    InutilizationRequest,
    InutilizationResult,
)
from .fake import FakeFiscalOperationsGateway, MutatingFiscalOperationsGateway

__all__ = [
    "CancellationOutcome",
    "CancellationRequest",
    "CancellationResult",
    "FakeFiscalOperationsGateway",
    "FiscalCancellationService",
    "FiscalEventStatus",
    "FiscalOperationKind",
    "FiscalOperationPayment",
    "FiscalOperationSnapshot",
    "FiscalOperationTotals",
    "FiscalOperationsClient",
    "FiscalOperationsContractError",
    "FiscalOperationsGateway",
    "FiscalQueryRequest",
    "FiscalQueryResult",
    "FiscalQueryStatus",
    "InutilizationRequest",
    "InutilizationResult",
    "MutatingFiscalOperationsGateway",
]
