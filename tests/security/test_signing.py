import hashlib
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from kordena_fiscal.domain import ExecutionScope, FiscalEnvironment, FiscalValidationError
from kordena_fiscal.security import (
    CertificateReference,
    CertificateStatus,
    CertificateValidityError,
    FiscalSignerKind,
    FiscalSigningService,
    SignatureEnvelope,
    SignerContractError,
    SigningRequest,
)


class _FakeSigner:
    def sign(self, request: SigningRequest) -> SignatureEnvelope:
        fake_signature = hashlib.sha256(
            request.payload + request.certificate.reference_id.encode()
        ).digest()
        return SignatureEnvelope(
            certificate_reference_id=request.certificate.reference_id,
            signer_kind=request.certificate.signer_kind,
            algorithm=request.algorithm,
            signature_value=fake_signature,
            payload_sha256=request.payload_sha256,
            signed_at=request.signing_time,
        )


class _WrongDigestSigner(_FakeSigner):
    def sign(self, request: SigningRequest) -> SignatureEnvelope:
        return replace(super().sign(request), payload_sha256="0" * 64)


class _WrongCertificateSigner(_FakeSigner):
    def sign(self, request: SigningRequest) -> SignatureEnvelope:
        return replace(super().sign(request), certificate_reference_id="other-ref")


def _scope(*, tenant: str = "tenant-a", unit: str = "unit-a") -> ExecutionScope:
    return ExecutionScope(
        tenant_id=tenant,
        unit_id=unit,
        environment=FiscalEnvironment.HOMOLOGATION,
        correlation_id="corr-sign-1",
    )


def _certificate(**overrides: object) -> CertificateReference:
    values: dict[str, object] = {
        "tenant_id": "tenant-a",
        "unit_id": "unit-a",
        "reference_id": "vault://fiscal/certificate/unit-a/current",
        "signer_kind": FiscalSignerKind.A1_PFX,
        "not_before": datetime(2026, 1, 1, tzinfo=UTC),
        "expires_at": datetime(2027, 1, 1, tzinfo=UTC),
        "subject_identifier": "synthetic-subject",
    }
    values.update(overrides)
    return CertificateReference(**values)  # type: ignore[arg-type]


def _request(**overrides: object) -> SigningRequest:
    values: dict[str, object] = {
        "scope": _scope(),
        "certificate": _certificate(),
        "payload": b"synthetic-fiscal-payload",
        "algorithm": "urn:test:signature-algorithm",
        "signing_time": datetime(2026, 6, 1, tzinfo=UTC),
    }
    values.update(overrides)
    return SigningRequest(**values)  # type: ignore[arg-type]


def test_certificate_status_tracks_not_yet_valid_valid_expiring_and_expired() -> None:
    certificate = _certificate()

    assert certificate.status_at(datetime(2025, 12, 31, tzinfo=UTC)) is (
        CertificateStatus.NOT_YET_VALID
    )
    assert certificate.status_at(datetime(2026, 6, 1, tzinfo=UTC)) is CertificateStatus.VALID
    assert certificate.status_at(datetime(2026, 12, 15, tzinfo=UTC)) is (
        CertificateStatus.EXPIRING
    )
    assert certificate.status_at(datetime(2027, 1, 1, tzinfo=UTC)) is CertificateStatus.EXPIRED


def test_signing_service_delegates_without_exposing_secret_material() -> None:
    request = _request()
    result = FiscalSigningService(_FakeSigner()).sign(request)

    assert result.certificate_reference_id == request.certificate.reference_id
    assert result.payload_sha256 == hashlib.sha256(request.payload).hexdigest()
    assert result.signature_value


def test_certificate_scope_is_enforced() -> None:
    request = _request(scope=_scope(unit="unit-b"))

    with pytest.raises(CertificateValidityError, match="does not belong"):
        FiscalSigningService(_FakeSigner()).sign(request)


def test_not_yet_valid_and_expired_certificates_fail_closed() -> None:
    not_yet_valid = _request(signing_time=datetime(2025, 12, 31, tzinfo=UTC))
    expired = _request(signing_time=datetime(2027, 1, 1, tzinfo=UTC))

    with pytest.raises(CertificateValidityError, match="not_yet_valid"):
        FiscalSigningService(_FakeSigner()).sign(not_yet_valid)
    with pytest.raises(CertificateValidityError, match="expired"):
        FiscalSigningService(_FakeSigner()).sign(expired)


def test_expiring_certificate_remains_usable_before_expiry() -> None:
    request = _request(signing_time=datetime(2026, 12, 20, tzinfo=UTC))

    result = FiscalSigningService(_FakeSigner()).sign(request)

    assert result.signature_value


def test_signer_result_digest_mismatch_is_rejected() -> None:
    with pytest.raises(SignerContractError, match="payload digest"):
        FiscalSigningService(_WrongDigestSigner()).sign(_request())


def test_signer_result_certificate_mismatch_is_rejected() -> None:
    with pytest.raises(SignerContractError, match="certificate reference"):
        FiscalSigningService(_WrongCertificateSigner()).sign(_request())


def test_empty_payload_and_naive_times_are_rejected() -> None:
    with pytest.raises(FiscalValidationError, match="payload"):
        _request(payload=b"")
    with pytest.raises(FiscalValidationError, match="timezone-aware"):
        _certificate(not_before=datetime(2026, 1, 1))


def test_certificate_interval_must_be_ordered() -> None:
    with pytest.raises(FiscalValidationError, match="after not_before"):
        _certificate(
            not_before=datetime(2027, 1, 1, tzinfo=UTC),
            expires_at=datetime(2026, 1, 1, tzinfo=UTC),
        )


def test_negative_expiry_warning_window_is_rejected() -> None:
    with pytest.raises(FiscalValidationError, match="non-negative"):
        _certificate().status_at(
            datetime(2026, 6, 1, tzinfo=UTC),
            expiring_within=timedelta(days=-1),
        )
