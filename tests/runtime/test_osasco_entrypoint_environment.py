"""Osasco operator provisioning through the executable canonical API path.

Synthetic local WSDL/XSD/keys only. This fixture cannot establish official
municipal SOAP parity or production readiness.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from kordena_fiscal.application.service import FiscalApplicationService
from kordena_fiscal.domain import FiscalValidationError
from kordena_fiscal.persistence import SqliteFiscalDatabase
from kordena_fiscal.runtime import api
from kordena_fiscal.runtime.config import RuntimeConfigurationError, RuntimeSettings
from kordena_fiscal.runtime.osasco_environment import (
    OsascoReviewedStartup,
    build_osasco_port_builder_from_environ,
)
from kordena_fiscal.vault.contracts import SecretResolutionService


def _fixture(root: Path) -> Path:
    wsdl = b'''<?xml version="1.0" encoding="utf-8"?>
    <wsdl:definitions xmlns:wsdl="http://schemas.xmlsoap.org/wsdl/"
      xmlns:soap="http://schemas.xmlsoap.org/wsdl/soap/"
      targetNamespace="http://tempuri.org/">
      <wsdl:binding name="BasicHttpBinding_Synthetic" type="tns:ITest">
        <soap:binding transport="http://schemas.xmlsoap.org/soap/http"
          style="document"/>
        <wsdl:operation name="RTC_EmitirNFE">
          <soap:operation soapAction="http://tempuri.org/ITest/RTC_EmitirNFE"/>
        </wsdl:operation>
        <wsdl:operation name="ConsultarNotaCompleta">
          <soap:operation soapAction="http://tempuri.org/ITest/ConsultarNotaCompleta"/>
        </wsdl:operation>
        <wsdl:operation name="Cancelar">
          <soap:operation soapAction="http://tempuri.org/ITest/Cancelar"/>
        </wsdl:operation>
      </wsdl:binding>
    </wsdl:definitions>'''
    methods = (
        "RTC_EmitirNFE", "ConsultarNotaCompleta", "Cancelar",
        "ConsultarNotaCompletaResponse", "CancelarResponse",
    )
    xsd = (
        '<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" '
        'xmlns:tem="http://tempuri.org/" targetNamespace="http://tempuri.org/" '
        'elementFormDefault="qualified">'
        + "".join(f'<xs:element name="{name}" type="xs:anyType"/>' for name in methods)
        + "</xs:schema>"
    ).encode()
    (root / "synthetic.wsdl").write_bytes(wsdl)
    (root / "synthetic.xsd").write_bytes(xsd)
    manifest = {
        "mode": "reviewed-homologation",
        "wsdl_file": "synthetic.wsdl",
        "wsdl_sha256": hashlib.sha256(wsdl).hexdigest(),
        "binding_name": "BasicHttpBinding_Synthetic",
        "xsd_resources": {"synthetic.xsd": hashlib.sha256(xsd).hexdigest()},
        "xsd_roots": dict.fromkeys(methods, "synthetic.xsd"),
        "issuers": [{
            "tenant_id": "tenant-test", "unit_id": "unit-test",
            "issuer_cnpj": "11222333000181", "profile_id": "reviewed-profile",
            "profile_version": 1, "tax_regime": 3,
            "policy": {
                "source_normative": "https://nfe.osasco.sp.gov.br/",
                "rule_version": 1, "effective_from": "2026-01-01",
                "effective_through": None,
                "municipal_service_code": "0101",
                "national_taxation_code": "010101",
                "activity": "101",
                "class_trib": "000001",
                "nbs_code": "1.0101.01.01",
                "incidence_location": "1", "operation_indicator": "000001",
                "service_city": "Osasco", "service_city_ibge": "3534401",
                "service_state": "SP", "recipient_street_type": "Rua",
                "iss_rate": "2.00",
                "pis": "0.00", "cofins": "0.00", "csll": "0.00",
                "income_tax": "0.00", "inss": "0.00", "other_taxes": "0.00",
                "test_only": True,
            },
        }],
        "gsm": {
            "project_id": "nfcore-test-project",
            "project_number": "123456789012",
            "resources": ["projects/nfcore-test-project/secrets/osasco-provider-key"],
            "workload_id": "nfcore-api",
        },
    }
    path = root / "reviewed.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


def _secrets(
    _startup: OsascoReviewedStartup, factory: object,
) -> SecretResolutionService:
    # Construction exercises composition but intentionally never fetches a key.
    return SecretResolutionService(unit_of_work_factory=factory, vault=object())  # type: ignore[arg-type]


def test_osasco_off_by_default_and_contract_loads_with_hashes(tmp_path: Path) -> None:
    assert build_osasco_port_builder_from_environ({}) is None
    path = _fixture(tmp_path)
    config = OsascoReviewedStartup.load(str(path))
    assert config.wsdl.contract_for_method("Cancelar").action.endswith("/Cancelar")
    assert len(config.issuers) == 1
    assert config.issuers[0].tax_regime == 3
    assert config.workload_id == "nfcore-api"
    assert set(config.validators) == {
        "RTC_EmitirNFE", "ConsultarNotaCompleta", "Cancelar",
        "ConsultarNotaCompletaResponse", "CancelarResponse",
    }


def test_osasco_schema_validates_method_and_never_receives_browser_key(
    tmp_path: Path,
) -> None:
    config = OsascoReviewedStartup.load(str(_fixture(tmp_path)))
    validators = config.schema_ports()
    xml = (
        b'<tem:RTC_EmitirNFE xmlns:tem="http://tempuri.org/" '
        b'xmlns:eis="http://schemas.datacontract.org/2004/07/Eissnfe.Negocio.WebServices.Mensagem">'
        b'<tem:request><eis:ChaveAutenticacao/></tem:request></tem:RTC_EmitirNFE>'
    )
    validators.validate_issuance(xml)
    with pytest.raises(FiscalValidationError, match="secret"):
        validators.validate_issuance(
            xml.replace(b"<eis:ChaveAutenticacao/>",
                        b"<eis:ChaveAutenticacao>browser-key</eis:ChaveAutenticacao>"),
        )
    with pytest.raises(FiscalValidationError, match="root"):
        validators.validate_issuance(
            xml.replace(b"RTC_EmitirNFE", b"Cancelar"),
        )


def test_osasco_manifest_denies_digest_tampering_duplicate_scope_and_simples(
    tmp_path: Path,
) -> None:
    manifest = _fixture(tmp_path)
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["wsdl_sha256"] = "f" * 64
    manifest.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(RuntimeConfigurationError, match="SHA-256"):
        OsascoReviewedStartup.load(str(manifest))

    data["wsdl_sha256"] = hashlib.sha256(
        (tmp_path / "synthetic.wsdl").read_bytes(),
    ).hexdigest()
    data["wsdl_file"] = "../outside.wsdl"
    manifest.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(RuntimeConfigurationError, match="resource"):
        OsascoReviewedStartup.load(str(manifest))

    data["wsdl_file"] = "synthetic.wsdl"
    data["issuers"].append(dict(data["issuers"][0]))
    manifest.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(RuntimeConfigurationError, match="Duplicate"):
        OsascoReviewedStartup.load(str(manifest))

    data["issuers"].pop()
    data["issuers"][0]["tax_regime"] = 1
    manifest.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(RuntimeConfigurationError, match="issuer"):
        OsascoReviewedStartup.load(str(manifest))


def test_osasco_is_bound_to_one_canonical_api_factory_and_database(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = _fixture(tmp_path)
    environ = {
        "NFCORE_OSASCO_RTC_CONFIG_PATH": str(manifest),
        "NFCORE_ENVIRONMENT": "staging",
    }
    reviewed = build_osasco_port_builder_from_environ(
        environ, secrets_factory=_secrets,
    )
    assert reviewed is not None
    db = SqliteFiscalDatabase(tmp_path / "one.sqlite")
    db.initialize()
    fiscal_application = FiscalApplicationService(db)
    ports = reviewed(fiscal_application)
    assert ports.transport is not None

    # The production api:app constructor must obtain exactly these same ports,
    # not register an alternate service or another database connection.
    monkeypatch.setattr(
        api, "build_osasco_port_builder_from_environ",
        lambda env: build_osasco_port_builder_from_environ(
            env, secrets_factory=_secrets,
        ),
    )
    settings = RuntimeSettings.from_mapping({
        "NFCORE_ENVIRONMENT": "staging",
        "NFCORE_PERSISTENCE_BACKEND": "postgres",
        "DATABASE_URL": "postgresql://fake:fake@db/nfcore",
        "NFCORE_SECRET_BACKEND": "external",
    })
    factory = api.build_entrypoint_fiscal_handler_factory(
        settings, environ, None,
    )
    assert factory is not None
    handlers = factory(fiscal_application)
    assert {
        "issueFiscalDocument", "queryFiscalDocument",
        "cancelOsascoNfse", "reviewOsascoSubstitution",
    } <= set(handlers)
    assert "cancelCajamarNfse" not in handlers

    disabled = api.build_entrypoint_fiscal_handler_factory(
        settings, {"NFCORE_ENVIRONMENT": "staging"}, None,
    )
    assert disabled is not None
    assert "cancelOsascoNfse" not in disabled(fiscal_application)

    dev = RuntimeSettings.from_mapping({"NFCORE_ENVIRONMENT": "development"})
    with pytest.raises(RuntimeConfigurationError, match="staging/production"):
        api.build_entrypoint_fiscal_handler_factory(dev, environ, None)


def test_osasco_manifest_does_not_contain_taxpayer_secret(tmp_path: Path) -> None:
    manifest = _fixture(tmp_path)
    data = json.loads(manifest.read_text(encoding="utf-8"))
    assert "ChaveAutenticacao" not in manifest.read_text(encoding="utf-8")
    data["municipal_key"] = "not-allowed"
    manifest.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(RuntimeConfigurationError, match="manifest"):
        OsascoReviewedStartup.load(str(manifest))
