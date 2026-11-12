"""NFS-e National query returns official XML to the canonical archive boundary."""
from __future__ import annotations

import base64
import gzip
import json

import pytest

from kordena_fiscal.domain import ExecutionScope, FiscalEnvironment, FiscalValidationError
from kordena_fiscal.gateway.authorization import AuthorizationStatus, GatewayProviderMetadata
from kordena_fiscal.gateway.nfse_national_homologation import OfficialNfseTransportError
from kordena_fiscal.gateway.nfse_national_query import _validate_official_nfse
from kordena_fiscal.issuance.nfe_nfse import NfseAuthorizationResult
from kordena_fiscal.lifecycle import IdempotencyKey

_KEY = "35" + "0" * 48
_NS = "http://www.sped.fazenda.gov.br/nfse"


def _response(xml: bytes) -> bytes:
    return json.dumps(
        {"nfseXmlGZipB64": base64.b64encode(gzip.compress(xml)).decode("ascii")}
    ).encode("utf-8")


def _receipt(key: str = _KEY) -> bytes:
    return (
        f'<NFSe xmlns="{_NS}"><infNFSe Id="NFS{key}"/></NFSe>'
    ).encode("utf-8")


def test_query_preserves_original_authorized_receipt_bytes() -> None:
    receipt = _receipt()
    assert _validate_official_nfse(_response(receipt), _KEY) == receipt


def test_query_does_not_accept_an_unrelated_document_or_a_bare_key() -> None:
    with pytest.raises(OfficialNfseTransportError, match="different access key"):
        _validate_official_nfse(_response(_receipt("99" + "0" * 48)), _KEY)
    with pytest.raises(OfficialNfseTransportError):
        _validate_official_nfse(json.dumps({"chaveAcesso": _KEY}).encode(), _KEY)


def _result(
    status: AuthorizationStatus,
    xml: bytes | None,
) -> NfseAuthorizationResult:
    return NfseAuthorizationResult(
        status=status,
        scope=ExecutionScope(
            tenant_id="test-tenant", unit_id="test-unit",
            environment=FiscalEnvironment.HOMOLOGATION,
            correlation_id="test-nfse-receipt", host_namespace="test-host",
        ),
        document_id="test-document",
        idempotency_key=IdempotencyKey("c" * 64),
        request_fingerprint="d" * 64,
        provider=GatewayProviderMetadata("synthetic-nfse", "1"),
        invoice_reference=_KEY if status is AuthorizationStatus.AUTHORIZED else None,
        authorized_xml=xml,
        rejection_code="REJECTED" if status is AuthorizationStatus.REJECTED else None,
        rejection_message="synthetic rejection" if status is AuthorizationStatus.REJECTED else None,
    )


def test_authorization_contract_carries_bounded_official_xml_only_when_authorized() -> None:
    payload = _receipt()
    assert _result(AuthorizationStatus.AUTHORIZED, payload).authorized_xml == payload
    with pytest.raises(FiscalValidationError, match="cannot contain invoice metadata"):
        _result(AuthorizationStatus.PENDING, payload)
    with pytest.raises(FiscalValidationError, match="cannot contain invoice metadata"):
        _result(AuthorizationStatus.REJECTED, payload)
    with pytest.raises(FiscalValidationError, match="Invalid authorized NFS-e XML evidence"):
        _result(AuthorizationStatus.AUTHORIZED, b"x" * (2 * 1024 * 1024 + 1))
