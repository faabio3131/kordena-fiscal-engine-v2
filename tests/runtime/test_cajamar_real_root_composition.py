"""Cajamar is attached once to the existing real fiscal operation factory.

This is a composition contract test, not a live municipality/credential claim.
"""
from __future__ import annotations

from unittest.mock import Mock

import pytest

from kordena_fiscal.application.service import FiscalApplicationService
from kordena_fiscal.control_plane.commercial import DurableProviderBindingResolver
from kordena_fiscal.gateway.cajamar_geisweb_homologation import (
    CajamarGeiswebHomologationTransport,
    CajamarGeiswebWsdl,
)
from kordena_fiscal.persistence import SqliteFiscalDatabase
from kordena_fiscal.runtime.cajamar_operational_composition import (
    CajamarTrustedRuntimePorts,
)
from kordena_fiscal.runtime.canonical_fiscal_composition import (
    build_runtime_fiscal_handler_factory,
)
from kordena_fiscal.runtime.fiscal_runtime import CanonicalFiscalOperationPath


def _trusted_fixture(db: SqliteFiscalDatabase) -> CajamarTrustedRuntimePorts:
    """All contract fields are synthetic and cannot contact a fiscal provider."""
    transport = CajamarGeiswebHomologationTransport(
        resolver=DurableProviderBindingResolver(db),
        resolve_certificate=Mock(side_effect=AssertionError("never load real A1")),
        signed_xml_validator=Mock(side_effect=AssertionError("no official XSD")),
        contract=CajamarGeiswebWsdl(
            endpoint=(
                "https://www.gerenciadecidades.com.br/homologacao/reforma/"
                "modelo/webservice/GeisWebServiceImpl.php"
            ),
            namespace="http://www.geisweb.com.br/",
            wsdl_sha256="1" * 64, xsd_package_sha256="2" * 64,
            method_actions={
                "EnviaLoteRps": "http://test.invalid/EnviaLoteRps",
                "ConsultaLoteRps": "http://test.invalid/ConsultaLoteRps",
                "ConsultaNfse": "http://test.invalid/ConsultaNfse",
                "CancelaNfse": "http://test.invalid/CancelaNfse",
            },
        ),
    )
    return CajamarTrustedRuntimePorts(
        transport=transport, build_signed_operation=Mock(),
        verify_signed_rps_identity=Mock(), fiscal_issuer_policy=Mock(),
        validate_prepared_rps=Mock(), verify_official_invoice_xml=Mock(),
        sign_cancel=Mock(), validate_signed_cancel=Mock(),
        verify_official_cancel=Mock(),
    )


def test_one_canonical_factory_exposes_cajamar_issue_query_cancel_and_review(
    tmp_path: object,
) -> None:
    from pathlib import Path

    assert isinstance(tmp_path, Path)
    db = SqliteFiscalDatabase(tmp_path / "cajamar-runtime.sqlite")
    db.initialize()
    application = FiscalApplicationService(db)
    factory = build_runtime_fiscal_handler_factory(
        cajamar_runtime_ports=_trusted_fixture(db),
    )
    first = factory(application)
    second = factory(application)
    operations = set(CanonicalFiscalOperationPath(
        application, handlers=first,
    ).configured_operations)
    assert {
        "issueFiscalDocument",
        "queryFiscalDocument",
        "reconcileFiscalOperation",
        "cancelCajamarNfse",
        "reviewCajamarSubstitution",
    } <= operations
    assert set(first) == set(second), "Composition cannot depend on a second authority"
    # The default build must never enable municipal SOAP without reviewed ports.
    base = build_runtime_fiscal_handler_factory()(application)
    assert "cancelCajamarNfse" not in base
    assert "reviewCajamarSubstitution" in base


def test_runtime_rejects_two_cajamar_authorities(tmp_path: object) -> None:
    from pathlib import Path

    assert isinstance(tmp_path, Path)
    db = SqliteFiscalDatabase(tmp_path / "cajamar-duplicate.sqlite")
    db.initialize()
    ports = _trusted_fixture(db)
    with pytest.raises(ValueError, match="Conflicting trusted Cajamar"):
        build_runtime_fiscal_handler_factory(
            cajamar_runtime_ports=ports,
            sp4_reviewed_municipalities={},
        )
    with pytest.raises(ValueError, match="Conflicting trusted Cajamar"):
        build_runtime_fiscal_handler_factory(
            cajamar_runtime_ports=ports,
            cajamar_verified_cancel=Mock(),
        )
    with pytest.raises(ValueError, match="Incomplete trusted Cajamar"):
        CajamarTrustedRuntimePorts(
            transport=ports.transport, build_signed_operation=None,  # type: ignore[arg-type]
            verify_signed_rps_identity=Mock(), fiscal_issuer_policy=Mock(),
            validate_prepared_rps=Mock(), verify_official_invoice_xml=Mock(),
            sign_cancel=Mock(), validate_signed_cancel=Mock(),
            verify_official_cancel=Mock(),
        )
