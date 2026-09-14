"""Public signer boundary for FM Fiscal V2."""

from .contracts import (
    CertificateUnavailableError,
    FiscalDocumentSigner,
    FiscalSignatureRequest,
    FiscalSignatureResult,
    FiscalSigningError,
    InvalidCertificateMaterialError,
    SignatureAlgorithm,
    SignatureVerificationError,
    SignerUnavailableError,
    SigningFailedError,
    UnsupportedSignatureCapabilityError,
)
from .cryptography_adapter import (
    CryptographyFiscalDocumentSigner,
    SigningClock,
    SystemSigningClock,
)

__all__ = [
    "CertificateUnavailableError",
    "CryptographyFiscalDocumentSigner",
    "FiscalDocumentSigner",
    "FiscalSignatureRequest",
    "FiscalSignatureResult",
    "FiscalSigningError",
    "InvalidCertificateMaterialError",
    "SignatureAlgorithm",
    "SignatureVerificationError",
    "SignerUnavailableError",
    "SigningClock",
    "SigningFailedError",
    "SystemSigningClock",
    "UnsupportedSignatureCapabilityError",
]
