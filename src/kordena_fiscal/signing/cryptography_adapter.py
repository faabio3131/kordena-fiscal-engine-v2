"""Cryptography-backed detached signer over caller-provided canonical fiscal bytes.

This adapter deliberately does not implement XML canonicalization or signature embedding.
Document/provider adapters own those format-specific concerns and pass the exact bytes that
must be signed. Secret material is obtained only through the certified Vault boundary.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol

from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa
from cryptography.hazmat.primitives.serialization import pkcs12

from kordena_fiscal.control_plane import SecretReferenceKind
from kordena_fiscal.domain import FiscalDocumentKind, FiscalValidationError
from kordena_fiscal.vault import (
    EphemeralCertificateMaterial,
    SecretResolutionContext,
    SecretResolutionError,
    SecretResolutionService,
    SecretUsagePurpose,
)

from .contracts import (
    CertificateUnavailableError,
    FiscalSignatureRequest,
    FiscalSignatureResult,
    InvalidCertificateMaterialError,
    SignatureAlgorithm,
    SignatureVerificationError,
    SignerUnavailableError,
    SigningFailedError,
    UnsupportedSignatureCapabilityError,
)


class SigningClock(Protocol):
    def now(self) -> datetime: ...


class SystemSigningClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


class CryptographyFiscalDocumentSigner:
    """Runtime signer for canonical bytes using a PKCS#12 identity resolved from Vault."""

    def __init__(
        self,
        *,
        secret_resolution: SecretResolutionService,
        supported_document_kinds: frozenset[FiscalDocumentKind] = frozenset(
            {FiscalDocumentKind.NFE, FiscalDocumentKind.NFCE}
        ),
        clock: SigningClock | None = None,
        available: bool = True,
    ) -> None:
        if not isinstance(supported_document_kinds, frozenset):
            raise FiscalValidationError("supported_document_kinds must be frozenset")
        if not supported_document_kinds:
            raise FiscalValidationError("supported_document_kinds must not be empty")
        if not all(isinstance(kind, FiscalDocumentKind) for kind in supported_document_kinds):
            raise FiscalValidationError("supported_document_kinds contain invalid values")
        self._secret_resolution = secret_resolution
        self._supported_document_kinds = supported_document_kinds
        self._clock = clock or SystemSigningClock()
        self._available = available

    def sign(self, request: FiscalSignatureRequest) -> FiscalSignatureResult:
        self._require_request(request)
        self._require_available()
        self._require_document_kind(request.document_kind)
        material = self._resolve_certificate(request)
        private_key, certificate = self._load_identity(material)

        try:
            if isinstance(private_key, rsa.RSAPrivateKey):
                signature = private_key.sign(
                    request.canonical_content,
                    padding.PKCS1v15(),
                    hashes.SHA256(),
                )
                algorithm = SignatureAlgorithm.RSA_SHA256
            elif isinstance(private_key, ec.EllipticCurvePrivateKey):
                signature = private_key.sign(
                    request.canonical_content,
                    ec.ECDSA(hashes.SHA256()),
                )
                algorithm = SignatureAlgorithm.ECDSA_SHA256
            else:
                raise UnsupportedSignatureCapabilityError(
                    "certificate private key algorithm is not supported"
                )
        except UnsupportedSignatureCapabilityError:
            raise
        except Exception:
            raise SigningFailedError("fiscal signing failed") from None

        return FiscalSignatureResult(
            signed_content=request.canonical_content,
            signature=signature,
            algorithm=algorithm,
            certificate_reference_id=material.reference_id,
            certificate_fingerprint_sha256=certificate.fingerprint(hashes.SHA256()).hex(),
            signed_at=self._clock.now(),
            document_kind=request.document_kind,
        )

    def verify(
        self,
        request: FiscalSignatureRequest,
        result: FiscalSignatureResult,
    ) -> None:
        self._require_request(request)
        if not isinstance(result, FiscalSignatureResult):
            raise FiscalValidationError("result must be FiscalSignatureResult")
        self._require_available()
        self._require_document_kind(request.document_kind)
        if result.document_kind is not request.document_kind:
            raise SignatureVerificationError("signature document kind mismatch")
        if result.signed_content != request.canonical_content:
            raise SignatureVerificationError("signed content does not match request")
        if result.certificate_reference_id != request.certificate_reference.reference_id:
            raise SignatureVerificationError("signature certificate reference mismatch")

        material = self._resolve_certificate(request)
        _, certificate = self._load_identity(material)
        fingerprint = certificate.fingerprint(hashes.SHA256()).hex()
        if fingerprint != result.certificate_fingerprint_sha256:
            raise SignatureVerificationError("signature certificate fingerprint mismatch")

        public_key = certificate.public_key()
        try:
            if result.algorithm is SignatureAlgorithm.RSA_SHA256 and isinstance(
                public_key, rsa.RSAPublicKey
            ):
                public_key.verify(
                    result.signature,
                    request.canonical_content,
                    padding.PKCS1v15(),
                    hashes.SHA256(),
                )
                return
            if result.algorithm is SignatureAlgorithm.ECDSA_SHA256 and isinstance(
                public_key, ec.EllipticCurvePublicKey
            ):
                public_key.verify(
                    result.signature,
                    request.canonical_content,
                    ec.ECDSA(hashes.SHA256()),
                )
                return
            raise SignatureVerificationError("signature algorithm does not match certificate")
        except SignatureVerificationError:
            raise
        except InvalidSignature:
            raise SignatureVerificationError("signature verification failed") from None
        except Exception:
            raise SignatureVerificationError("signature verification failed") from None

    def _resolve_certificate(
        self,
        request: FiscalSignatureRequest,
    ) -> EphemeralCertificateMaterial:
        context = SecretResolutionContext(
            scope=request.scope,
            purpose=SecretUsagePurpose.DOCUMENT_SIGNING,
            kind=SecretReferenceKind.CERTIFICATE,
            workload_id=request.workload_id,
        )
        try:
            material = self._secret_resolution.resolve(context)
        except SecretResolutionError:
            raise CertificateUnavailableError("signing certificate is unavailable") from None
        if not isinstance(material, EphemeralCertificateMaterial):
            raise InvalidCertificateMaterialError("resolved signing material is not a certificate")
        if material.reference_id != request.certificate_reference.reference_id:
            raise CertificateUnavailableError("requested certificate reference is unavailable")
        return material

    @staticmethod
    def _load_identity(
        material: EphemeralCertificateMaterial,
    ) -> tuple[object, x509.Certificate]:
        try:
            private_key, certificate, _ = pkcs12.load_key_and_certificates(
                material.pkcs12_bytes,
                material.password,
            )
        except (TypeError, ValueError):
            raise InvalidCertificateMaterialError("certificate material is invalid") from None
        if private_key is None or certificate is None:
            raise InvalidCertificateMaterialError(
                "certificate material lacks signing identity"
            )
        return private_key, certificate

    def _require_available(self) -> None:
        if not self._available:
            raise SignerUnavailableError("fiscal signer is unavailable")

    def _require_document_kind(self, document_kind: FiscalDocumentKind) -> None:
        if document_kind not in self._supported_document_kinds:
            raise UnsupportedSignatureCapabilityError(
                f"signature capability is not configured for {document_kind.value}"
            )

    @staticmethod
    def _require_request(request: FiscalSignatureRequest) -> None:
        if not isinstance(request, FiscalSignatureRequest):
            raise FiscalValidationError("request must be FiscalSignatureRequest")
