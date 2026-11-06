"""Fiscal dependency indicators and NFS-e gateway boundary (offline only)."""
from __future__ import annotations

from typing import cast

import pytest

from kordena_fiscal.gateway.nfse_nacional_homologation import (
    NfseNacionalHomologationGateway,
)
from kordena_fiscal.issuance import NfseAuthorizationRequest
from kordena_fiscal.runtime.canonical_fiscal_composition import (
    build_runtime_fiscal_handler_factory,
    fiscal_external_dependency_snapshot,
)
from kordena_fiscal.vault import EphemeralCertificateMaterial
from kordena_fiscal.vault.encrypted_a1 import EncryptedA1Vault


def _builder(
    _request: NfseAuthorizationRequest, _certificate: EphemeralCertificateMaterial
) -> bytes:
    # A sentinel in an offline configuration test: never used for transmission.
    raise AssertionError("Unsigned or synthetic DPS must never be transmitted")


def test_unprovisioned_profile_is_fail_closed() -> None:
    status = fiscal_external_dependency_snapshot(certificate_vault=None)
    assert status == {
        "fiscal_provider_transport_real_configured": False,
        "fiscal_external_secret_client_configured": False,
        "fiscal_signer_configured": False,
        "fiscal_runtime_external_execution_ready": False,
    }


def test_vault_configured_does_not_claim_nfse_execution_ready(tmp_path: object) -> None:
    vault = EncryptedA1Vault(directory=cast("str", str(tmp_path)), master_key=b"k" * 32)
    status = fiscal_external_dependency_snapshot(certificate_vault=vault)
    assert status["fiscal_provider_transport_real_configured"]
    assert status["fiscal_external_secret_client_configured"]
    assert status["fiscal_signer_configured"]
    assert status["fiscal_runtime_external_execution_ready"] is False
    assert callable(build_runtime_fiscal_handler_factory(certificate_vault=vault))


def _preaudit(_request: NfseAuthorizationRequest) -> None:
    raise AssertionError("Configuration tests do not run the auditor")


def test_trusted_signed_dps_requires_preaudit(tmp_path: object) -> None:
    vault = EncryptedA1Vault(directory=str(tmp_path), master_key=b"k" * 32)
    status = fiscal_external_dependency_snapshot(
        certificate_vault=vault, trusted_signed_dps_builder=_builder,
    )
    assert status["fiscal_runtime_external_execution_ready"] is False
    with pytest.raises(ValueError, match="pre-audit"):
        build_runtime_fiscal_handler_factory(
            certificate_vault=vault, trusted_signed_dps_builder=_builder,
        )


def test_trusted_signed_dps_port_can_be_composed(tmp_path: object) -> None:
    vault = EncryptedA1Vault(directory=cast("str", str(tmp_path)), master_key=b"k" * 32)
    status = fiscal_external_dependency_snapshot(
        certificate_vault=vault, trusted_signed_dps_builder=_builder, nfse_preaudit=_preaudit,
    )
    assert status["fiscal_runtime_external_execution_ready"]
    assert callable(build_runtime_fiscal_handler_factory(
        certificate_vault=vault, trusted_signed_dps_builder=_builder, nfse_preaudit=_preaudit,
    ))


def test_dual_nfse_provider_configuration_is_forbidden() -> None:
    from kordena_fiscal.issuance import NfseGatewayClient
    with pytest.raises(ValueError, match="either"):
        build_runtime_fiscal_handler_factory(
            nfse_gateway=cast(NfseGatewayClient, object()),
            trusted_signed_dps_builder=_builder,
        )


def test_national_gateway_will_not_be_used_as_unsigned_fallback() -> None:
    assert hasattr(NfseNacionalHomologationGateway, "authorize")
    assert fiscal_external_dependency_snapshot(
        certificate_vault=None, trusted_signed_dps_builder=_builder
    )["fiscal_runtime_external_execution_ready"] is False
