"""Pinned WCF v2.1 SOAP 1.1 operations are never guessed from a browser."""
from __future__ import annotations

import hashlib

import pytest

from kordena_fiscal.runtime.osasco_wsdl_contract import (
    OsascoWsdlIntegrityError,
    load_osasco_pinned_wsdl,
)


def _wsdl() -> bytes:
    return b'''<?xml version="1.0" encoding="utf-8"?>
    <wsdl:definitions
        xmlns:wsdl="http://schemas.xmlsoap.org/wsdl/"
        xmlns:soap="http://schemas.xmlsoap.org/wsdl/soap/"
        targetNamespace="http://tempuri.org/">
      <wsdl:binding name="BasicHttpBinding_Test" type="tns:INotaFiscalEletronica">
        <soap:binding transport="http://schemas.xmlsoap.org/soap/http"
                      style="document"/>
        <wsdl:operation name="RTC_EmitirNFE">
          <soap:operation soapAction="http://tempuri.org/INotaFiscalEletronica/RTC_EmitirNFE"/>
        </wsdl:operation>
        <wsdl:operation name="ConsultarNotaCompleta">
          <soap:operation
              soapAction="http://tempuri.org/INotaFiscalEletronica/ConsultarNotaCompleta"/>
        </wsdl:operation>
        <wsdl:operation name="Cancelar">
          <soap:operation soapAction="http://tempuri.org/INotaFiscalEletronica/Cancelar"/>
        </wsdl:operation>
      </wsdl:binding>
    </wsdl:definitions>'''


def _load(xml: bytes):
    return load_osasco_pinned_wsdl(
        document=xml,
        expected_sha256=hashlib.sha256(xml).hexdigest(),
        binding_name="BasicHttpBinding_Test",
    )


def test_pinned_osasco_wsdl_resolves_exact_contract_without_network() -> None:
    c = _load(_wsdl())
    assert set(c.operations) == {"RTC_EmitirNFE", "ConsultarNotaCompleta", "Cancelar"}
    assert c.contract_for_method("Cancelar").action.endswith("/Cancelar")
    assert c.contract_for_method("RTC_EmitirNFE").wsdl_sha256 == c.sha256
    with pytest.raises(TypeError):
        c.operations["Otro"] = c.contract_for_method("Cancelar")  # type: ignore[index]


def test_wsdl_binding_hash_and_method_are_mandatory() -> None:
    xml = _wsdl()
    with pytest.raises(OsascoWsdlIntegrityError, match="hash"):
        load_osasco_pinned_wsdl(
            document=xml, expected_sha256="a" * 64,
            binding_name="BasicHttpBinding_Test",
        )
    with pytest.raises(OsascoWsdlIntegrityError, match="binding"):
        load_osasco_pinned_wsdl(
            document=xml, expected_sha256=hashlib.sha256(xml).hexdigest(),
            binding_name="Unrelated",
        )
    with pytest.raises(OsascoWsdlIntegrityError, match="operation"):
        _load(xml.replace(b'<wsdl:operation name="Cancelar">', b'<wsdl:operation name="Other">'))


def test_wsdl_disallows_duplicate_soap_action_and_unapproved_protocol() -> None:
    xml = _wsdl()
    double = xml.replace(
        b'<wsdl:operation name="Cancelar">',
        b'<wsdl:operation name="Cancelar"><soap:operation soapAction="http://tempuri.org/dup"/>'
        b'</wsdl:operation><wsdl:operation name="Cancelar">',
    )
    with pytest.raises(OsascoWsdlIntegrityError, match="Duplicate"):
        _load(double)
    bad = xml.replace(
        b"http://schemas.xmlsoap.org/soap/http",
        b"http://invalid.example/wsdl/not-soap",
    )
    with pytest.raises(OsascoWsdlIntegrityError, match="SOAP 1.1"):
        _load(bad)
    no_action = xml.replace(
        b"http://tempuri.org/INotaFiscalEletronica/Cancelar",
        b"http://untrusted.example/Cancel",
    )
    with pytest.raises(OsascoWsdlIntegrityError, match="SOAPAction"):
        _load(no_action)


def test_wsdl_rejects_dtd_and_xml_entity_aliasing() -> None:
    xml = _wsdl().replace(
        b'<wsdl:definitions',
        b'<!DOCTYPE wsdl:definitions [<!ENTITY exploit SYSTEM "file:///etc/passwd">]>'
        b'<wsdl:definitions',
    )
    with pytest.raises(OsascoWsdlIntegrityError, match="DTD"):
        _load(xml)
