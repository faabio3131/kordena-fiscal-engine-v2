import hashlib
from datetime import UTC, datetime

import pytest

from kordena_fiscal.domain import Cnpj, ElectronicInvoiceModel, FiscalValidationError
from kordena_fiscal.xml import (
    AccessKeyInput,
    NfceXmlPayload,
    SchemaIntegrityError,
    SchemaResource,
    SchemaSet,
    XmlSchemaValidationError,
    XmlSchemaValidator,
    build_access_key,
)

_NAMESPACE = "http://www.portalfiscal.inf.br/nfe"

_ROOT_XSD = f"""<?xml version="1.0" encoding="UTF-8"?>
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"
           targetNamespace="{_NAMESPACE}"
           xmlns="{_NAMESPACE}"
           elementFormDefault="qualified">
  <xs:include schemaLocation="types/common.xsd"/>
  <xs:element name="NFe">
    <xs:complexType>
      <xs:sequence>
        <xs:element name="infNFe" type="TInfNFe"/>
      </xs:sequence>
    </xs:complexType>
  </xs:element>
</xs:schema>
""".encode()

_COMMON_XSD = f"""<?xml version="1.0" encoding="UTF-8"?>
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"
           targetNamespace="{_NAMESPACE}"
           xmlns="{_NAMESPACE}"
           elementFormDefault="qualified">
  <xs:complexType name="TInfNFe">
    <xs:sequence>
      <xs:element name="synthetic">
        <xs:simpleType>
          <xs:restriction base="xs:string">
            <xs:enumeration value="ok"/>
          </xs:restriction>
        </xs:simpleType>
      </xs:element>
    </xs:sequence>
    <xs:attribute name="Id" type="xs:string" use="required"/>
  </xs:complexType>
</xs:schema>
""".encode()


def _key():
    return build_access_key(
        AccessKeyInput(
            state_ibge_code="35",
            issued_at=datetime(2026, 9, 1, tzinfo=UTC),
            issuer_cnpj=Cnpj("AB.C12.345/0001-10"),
            model=ElectronicInvoiceModel.NFCE,
            series=1,
            invoice_number=1,
            emission_type=1,
            numeric_code=12345678,
        )
    )


def _schema_set() -> SchemaSet:
    return SchemaSet(
        version="synthetic-1",
        root_schema="nfe.xsd",
        resources=(
            SchemaResource.from_bytes("nfe.xsd", _ROOT_XSD),
            SchemaResource.from_bytes("types/common.xsd", _COMMON_XSD),
        ),
        source_uri="https://example.invalid/synthetic-schema-package",
    )


def _xml(value: str = "ok") -> bytes:
    key = _key()
    return (
        f'<NFe xmlns="{_NAMESPACE}"><infNFe Id="NFe{key.value}">'
        f"<synthetic>{value}</synthetic></infNFe></NFe>"
    ).encode()


def test_xsd_include_is_resolved_from_pinned_memory_bundle_without_network() -> None:
    payload = NfceXmlPayload(access_key=_key(), xml=_xml())

    result = XmlSchemaValidator(_schema_set()).validate(payload)

    assert result.schema_version == "synthetic-1"
    assert len(result.schema_package_sha256) == 64
    assert result.xml_sha256 == hashlib.sha256(payload.xml).hexdigest()


def test_schema_validation_rejects_semantically_invalid_xml() -> None:
    payload = NfceXmlPayload(access_key=_key(), xml=_xml("invalid"))

    with pytest.raises(XmlSchemaValidationError, match="pinned XSD"):
        XmlSchemaValidator(_schema_set()).validate(payload)


def test_nfce_payload_requires_access_key_to_match_infnfe_id() -> None:
    other_key = build_access_key(
        AccessKeyInput(
            state_ibge_code="35",
            issued_at=datetime(2026, 9, 1, tzinfo=UTC),
            issuer_cnpj=Cnpj("AB.C12.345/0001-10"),
            model=ElectronicInvoiceModel.NFCE,
            series=1,
            invoice_number=2,
            emission_type=1,
            numeric_code=12345678,
        )
    )

    with pytest.raises(XmlSchemaValidationError, match="does not match"):
        NfceXmlPayload(access_key=other_key, xml=_xml())


def test_nfce_payload_requires_official_fiscal_namespace_and_root() -> None:
    key = _key()
    xml = f'<NFe xmlns="urn:wrong"><infNFe Id="NFe{key.value}"/></NFe>'.encode()

    with pytest.raises(XmlSchemaValidationError, match="fiscal namespace"):
        NfceXmlPayload(access_key=key, xml=xml)


def test_doctype_is_rejected_before_xml_processing() -> None:
    key = _key()
    xml_text = (
        '<!DOCTYPE NFe [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>'
        f'<NFe xmlns="{_NAMESPACE}"><infNFe Id="NFe{key.value}">'
        "<synthetic>&xxe;</synthetic></infNFe></NFe>"
    )

    with pytest.raises(XmlSchemaValidationError, match="DOCTYPE"):
        NfceXmlPayload(access_key=key, xml=xml_text.encode())


def test_schema_resource_digest_mismatch_fails_closed() -> None:
    with pytest.raises(SchemaIntegrityError, match="digest mismatch"):
        SchemaResource(name="nfe.xsd", content=_ROOT_XSD, sha256="0" * 64)


def test_schema_set_requires_unique_resources_and_existing_root() -> None:
    resource = SchemaResource.from_bytes("nfe.xsd", _ROOT_XSD)

    with pytest.raises(FiscalValidationError, match="unique"):
        SchemaSet(
            version="v1",
            root_schema="nfe.xsd",
            resources=(resource, resource),
            source_uri="https://example.invalid/package",
        )
    with pytest.raises(FiscalValidationError, match="root_schema"):
        SchemaSet(
            version="v1",
            root_schema="missing.xsd",
            resources=(resource,),
            source_uri="https://example.invalid/package",
        )
