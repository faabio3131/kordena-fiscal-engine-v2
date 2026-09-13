"""Provider-neutral fiscal signing contracts for V2-12."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from kordena_fiscal.control_plane import SecretReference, SecretReferenceKind
from kordena_fiscal.domain import (
    ExecutionScope,
    FiscalDocumentKind,
    FiscalDomainError,
    FiscalValidationError,
)


class FiscalSigningError(FiscalDomainError):
    """Base error for signing boundary failures."""


class CertificateUnavailableError(FiscalSigningError):
    """Certificate reference or runtime certificate material is unavailable."""


class InvalidCertificateMaterialError(FiscalSigningError):
    """Runtime certificate material cannot be used by the signer."""


class SignerUnavailableError(FiscalSigningError):
    """Signer adapter is administratively unavailable."""


class SigningFailedError(FiscalSigningError):
    """Cryptographic signing failed without exposing secret internals."""


class SignatureVerificationError(FiscalSigningError):
    """Signature verification failed or signed content was tampered with."""


class UnsupportedSignatureCapabilityError(FiscalSigningError):
    """Document kind or key algorithm is not supported by this signer adapter."""


class SignatureAlgorithm(StrEnum):
    RSA_SHA256 = "rsa-sha256"
    ECDSA_SHA256 = "ecdsa-sha256"


@dataclass(frozen=True, slots=True, repr=False)
class FiscalSignatureRequest:
    """Explicit canonical bytes and governed certificate reference to sign."""

    scope: ExecutionScope
    document_kind: FiscalDocumentKind
    canonical_content: bytes
    certificate_reference: SecretReference
    workload_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.scope, ExecutionScope):
            raise FiscalValidationError("scope must be ExecutionScope")
        if self.scope.host_namespace is None:
            raise FiscalValidationError("fiscal signature requires host_namespace")
        if not isinstance(self.document_kind, FiscalDocumentKind):
            raise FiscalValidationError("document_kind must be FiscalDocumentKind")
        if not isinstance(self.canonical_content, bytes) or not self.canonical_content:
            raise FiscalValidationError("canonical_content must be non-empty bytes")
        if not isinstance(self.certificate_reference, SecretReference):
            raise FiscalValidationError("certificate_reference must be SecretReference")
        if self.certificate_reference.kind is not SecretReferenceKind.CERTIFICATE:
            raise FiscalValidationError("signing requires a certificate SecretReference")
        if self.certificate_reference.tenant_id != self.scope.tenant_id:
            raise FiscalValidationError("certificate reference tenant does not match scope")
        if self.certificate_reference.unit_id != self.scope.unit_id:
            raise FiscalValidationError("certificate reference unit does not match scope")
        if self.certificate_reference.environment is not self.scope.environment:
            raise FiscalValidationError("certificate reference environment does not match scope")
        workload = self.workload_id.strip()
        if not workload:
            raise FiscalValidationError("workload_id must not be blank")
        if len(workload) > 128:
            raise FiscalValidationError("workload_id exceeds max length 128")
        object.__setattr__(self, "workload_id", workload)

    def __repr__(self) -> str:
        return (
            "<FiscalSignatureRequest "
            f"document_kind={self.document_kind.value} "
            f"reference={self.certificate_reference.reference_id}>"
        )


@dataclass(frozen=True, slots=True, repr=False)
class FiscalSignatureResult:
    """Detached cryptographic result over canonical bytes; no private material."""

    signed_content: bytes
    signature: bytes
    algorithm: SignatureAlgorithm
    certificate_reference_id: str
    certificate_fingerprint_sha256: str
    signed_at: datetime
    document_kind: FiscalDocumentKind

    def __post_init__(self) -> None:
        if not isinstance(self.signed_content, bytes) or not self.signed_content:
            raise FiscalValidationError("signed_content must be non-empty bytes")
        if not isinstance(self.signature, bytes) or not self.signature:
            raise FiscalValidationError("signature must be non-empty bytes")
        if not isinstance(self.algorithm, SignatureAlgorithm):
            raise FiscalValidationError("algorithm must be SignatureAlgorithm")
        reference = self.certificate_reference_id.strip().lower()
        if not reference.startswith("ref:"):
            raise FiscalValidationError("certificate_reference_id must be opaque ref: identifier")
        object.__setattr__(self, "certificate_reference_id", reference)
        fingerprint = self.certificate_fingerprint_sha256.strip().lower()
        if len(fingerprint) != 64 or any(char not in "0123456789abcdef" for char in fingerprint):
            raise FiscalValidationError("certificate fingerprint must be lowercase SHA-256 hex")
        object.__setattr__(self, "certificate_fingerprint_sha256", fingerprint)
        if self.signed_at.tzinfo is None or self.signed_at.utcoffset() is None:
            raise FiscalValidationError("signed_at must be timezone-aware")
        if not isinstance(self.document_kind, FiscalDocumentKind):
            raise FiscalValidationError("document_kind must be FiscalDocumentKind")

    def __repr__(self) -> str:
        return (
            "<FiscalSignatureResult "
            f"document_kind={self.document_kind.value} "
            f"algorithm={self.algorithm.value} "
            f"reference={self.certificate_reference_id}>"
        )


class FiscalDocumentSigner(Protocol):
    def sign(self, request: FiscalSignatureRequest) -> FiscalSignatureResult: ...

    def verify(
        self,
        request: FiscalSignatureRequest,
        result: FiscalSignatureResult,
    ) -> None: ...
