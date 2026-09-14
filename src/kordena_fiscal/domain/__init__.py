"""Public canonical domain surface for FM Fiscal Core."""

from .binding import (
    FiscalAccountBinding,
    FiscalAccountId,
    FiscalBindingRegistry,
    FiscalUnitId,
    HostNamespace,
    HostScope,
)
from .errors import FiscalDomainError, FiscalValidationError
from .events import FiscalDomainEvent
from .identifiers import CnaeCode, Cnpj
from .primitives import (
    BrazilianJurisdiction,
    ElectronicInvoiceModel,
    ExecutionScope,
    FiscalDocumentKind,
    FiscalEnvironment,
    Money,
    SourceReference,
)
from .product import (
    CestCode,
    FiscalProductProfile,
    FiscalUnitCode,
    Gtin,
    NcmCode,
    ProductOrigin,
    TaxClassificationHints,
)
from .profile import (
    FiscalAddress,
    FiscalProfile,
    MunicipalRegistration,
    StateRegistration,
    TaxRegimeCode,
)

__all__ = [
    "BrazilianJurisdiction",
    "CestCode",
    "CnaeCode",
    "Cnpj",
    "ElectronicInvoiceModel",
    "ExecutionScope",
    "FiscalAccountBinding",
    "FiscalAccountId",
    "FiscalAddress",
    "FiscalBindingRegistry",
    "FiscalDocumentKind",
    "FiscalDomainError",
    "FiscalDomainEvent",
    "FiscalEnvironment",
    "FiscalProductProfile",
    "FiscalProfile",
    "FiscalUnitCode",
    "FiscalUnitId",
    "FiscalValidationError",
    "Gtin",
    "HostNamespace",
    "HostScope",
    "Money",
    "MunicipalRegistration",
    "NcmCode",
    "ProductOrigin",
    "SourceReference",
    "StateRegistration",
    "TaxClassificationHints",
    "TaxRegimeCode",
]
