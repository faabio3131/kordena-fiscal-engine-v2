"""Protocol package invariants are independent from official authorization."""
import pytest

from kordena_fiscal.xml.official_operation_schema import (
    ROOTS,
    OfficialOperationXmlValidator,
    load_operation_schema,
)
from kordena_fiscal.xml.schema import SchemaIntegrityError, XmlSchemaValidationError


@pytest.mark.parametrize("service", tuple(ROOTS))
def test_all_operation_schema_roots_are_pinned_and_compile(service):
    schema = load_operation_schema(service)
    assert schema.root_schema == ROOTS[service]
    assert len(schema.resources) == 27
    validator = OfficialOperationXmlValidator((service,))
    with pytest.raises(XmlSchemaValidationError):
        validator(service, b"<invalid/>")


def test_unknown_schema_and_unconfigured_service_cannot_fallback():
    with pytest.raises(SchemaIntegrityError):
        load_operation_schema("unknown")
    validator = OfficialOperationXmlValidator(("NFeConsultaProtocolo4",))
    with pytest.raises(SchemaIntegrityError):
        validator("NFeInutilizacao4", b"<invalid/>")


@pytest.mark.parametrize("xml", [
    b"", b"<!DOCTYPE x><x/>", b"<broken", b"x" * 2_097_153,
], ids=["empty", "doctype", "malformed", "oversized"])
def test_malformed_or_oversized_xml_is_denied(xml):
    validator = OfficialOperationXmlValidator(("NFeConsultaProtocolo4",))
    with pytest.raises(XmlSchemaValidationError):
        validator("NFeConsultaProtocolo4", xml)
