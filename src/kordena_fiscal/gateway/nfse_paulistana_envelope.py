"""Offline SOAP preparation for São Paulo's non-issuing TesteEnvioLoteRPS."""
from __future__ import annotations

import base64
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from functools import lru_cache
from importlib.resources import files

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from lxml import etree

from kordena_fiscal.domain import Cnpj, ExecutionScope, FiscalEnvironment, FiscalValidationError
from kordena_fiscal.signing.nfse_xmldsig import append_nfse_signature
from kordena_fiscal.vault import EphemeralCertificateMaterial
from kordena_fiscal.vault.a1_preflight import validate_a1_for_issuer
from kordena_fiscal.xml.schema import SchemaResource, SchemaSet, XmlSchemaValidator

_NFE = "http://www.prefeitura.sp.gov.br/nfe"
_SOAP = "http://schemas.xmlsoap.org/soap/envelope/"
_DS = "http://www.w3.org/2000/09/xmldsig#"
_SCHEMA_SOURCE = "https://notadomilhao.sf.prefeitura.sp.gov.br/schemas-reformatributaria-v02-7/"
_SCHEMA_HASHES = {
    "PedidoEnvioLoteRPS_v02.xsd":
        "a3317ef2e2a82b7a484b5c8681543f34fa7c9069e3866a408cc6b267fbd8699c",
    "TiposNFe_v02.xsd": "d2ea0e8ff29450ea70c6acea88a343355f7e46a64f6cea84e7b01de1e1889525",
    "xmldsig-core-schema_v02.xsd":
        "a4d2873908765c0d856ba94f549524e70eefb0e2d1a7d28a691ab3a9b0a7f60c",
}


@dataclass(frozen=True, slots=True)
class PaulistanaServiceFacts:
    date_issued: str
    municipal_service_code: str
    service_municipality: str | None
    taxation: str
    iss_rate: str
    iss_withheld: bool


@dataclass(frozen=True, slots=True)
class PaulistanaTestEnvelope:
    body: bytes
    soap_action: str = f'"{_NFE}/TesteEnvioLoteRPS"'
    content_type: str = "text/xml; charset=utf-8"


@lru_cache(maxsize=1)
def _validator() -> XmlSchemaValidator:
    directory = files("kordena_fiscal.xml").joinpath("official", "NFSE_PAULISTANA_02_7")
    return XmlSchemaValidator(SchemaSet(
        version="Nota Paulistana 02-7",
        root_schema="PedidoEnvioLoteRPS_v02.xsd",
        resources=tuple(
            SchemaResource(name, directory.joinpath(name).read_bytes(), digest)
            for name, digest in _SCHEMA_HASHES.items()
        ),
        source_uri=_SCHEMA_SOURCE,
    ))


def _digits(value: str, width: int) -> str:
    if not re.fullmatch(r"[0-9]+", value) or len(value) > width:
        raise FiscalValidationError("Invalid Paulistana numeric signature field")
    return value.zfill(width)


def _cents(value: str) -> str:
    if not re.fullmatch(r"[0-9]{1,13}(?:\.[0-9]{1,2})?", value):
        raise FiscalValidationError("Invalid Paulistana amount")
    return _digits(str(int(Decimal(value) * 100)), 15)


def _retained(value: str) -> str:
    if value in {"true", "1"}:
        return "S"
    if value in {"false", "0"}:
        return "N"
    raise FiscalValidationError("Invalid Paulistana ISS retention")


def _party(node: etree._Element | None) -> tuple[str, str]:
    if node is None:
        return "3" + "0" * 14, ""
    if len(node) != 1 or not node[0].text:
        raise FiscalValidationError("Invalid Paulistana party identity")
    kind, value = node[0].tag, node[0].text
    if kind == "CPF" and re.fullmatch(r"[0-9]{11}", value):
        return "1" + value.zfill(14), ""
    if kind == "CNPJ" and re.fullmatch(r"[0-9]{14}", value):
        return "2" + value, ""
    if kind == "NIF" and 0 < len(value.strip()) <= 40 and value.isascii():
        return "4" + "0" * 14, value.strip()
    if kind == "NaoNIF" and value in {"0", "1", "2"}:
        return "4" + "0" * 14, value
    raise FiscalValidationError("Invalid Paulistana party identity")


def _rps_input(rps: etree._Element, issuer_ccm: str) -> tuple[bytes, PaulistanaServiceFacts]:
    ccm = _digits(rps.findtext("ChaveRPS/InscricaoPrestador", ""), 12)
    if ccm != issuer_ccm:
        raise FiscalValidationError("Paulistana RPS issuer CCM mismatch")
    series = rps.findtext("ChaveRPS/SerieRPS", "")
    issued = rps.findtext("DataEmissao", "")
    status = rps.findtext("StatusRPS", "")
    taxation = rps.findtext("TributacaoRPS", "")
    if (
        not re.fullmatch(r"[ -~]{0,5}", series)
        or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", issued)
        or status not in {"N", "C"}
        or taxation not in set("TFABDMNRSXVP")
    ):
        raise FiscalValidationError("Invalid Paulistana RPS signature fields")
    try:
        date.fromisoformat(issued)
    except ValueError:
        raise FiscalValidationError("Invalid Paulistana RPS issue date") from None
    retained = _retained(rps.findtext("ISSRetido", ""))
    amount = rps.findtext("ValorInicialCobrado") or rps.findtext("ValorFinalCobrado", "")
    service = _digits(rps.findtext("CodigoServico", ""), 5)
    taxpayer, nif = _party(rps.find("CPFCNPJTomador"))
    intermediary = rps.find("CPFCNPJIntermediario")
    intermediary_input = ""
    if intermediary is not None:
        intermediary_id, intermediary_nif = _party(intermediary)
        if intermediary_nif:
            raise FiscalValidationError("Invalid Paulistana intermediary identity")
        intermediary_input = intermediary_id + _retained(rps.findtext("ISSRetidoIntermediario", ""))
    elif rps.find("ISSRetidoIntermediario") is not None:
        raise FiscalValidationError("Paulistana retention requires an intermediary")
    signed_fields = (
        ccm, series.ljust(5), _digits(rps.findtext("ChaveRPS/NumeroRPS", ""), 12),
        issued.replace("-", ""), taxation, status, retained, _cents(amount or ""),
        _cents(rps.findtext("ValorDeducoes", "")), service, taxpayer, intermediary_input, nif,
    )
    return "".join(signed_fields).encode("ascii"), PaulistanaServiceFacts(
        date_issued=issued,
        municipal_service_code=service,
        service_municipality=rps.findtext("cLocPrestacao") or rps.findtext("MunicipioPrestacao"),
        taxation=taxation,
        iss_rate=rps.findtext("AliquotaServicos", ""),
        iss_withheld=retained == "S",
    )


def prepare_paulistana_test_batch(
    *,
    xml: bytes,
    scope: ExecutionScope,
    issuer_cnpj: Cnpj,
    issuer_ccm: str,
    resolve_certificate: Callable[[ExecutionScope, str], EphemeralCertificateMaterial],
    preaudit: Callable[[tuple[PaulistanaServiceFacts, ...]], None],
) -> PaulistanaTestEnvelope:
    """Build a municipal test request from trusted issuer data and an unsigned batch."""
    if scope.environment is not FiscalEnvironment.HOMOLOGATION:
        raise FiscalValidationError("Paulistana test batch requires homologation scope")
    if not isinstance(xml, bytes) or not 0 < len(xml) <= 500_000:
        raise FiscalValidationError("Invalid Paulistana payload size")
    try:
        root = etree.fromstring(xml, parser=etree.XMLParser(
            no_network=True, resolve_entities=False, remove_pis=True, remove_comments=True,
        ))
    except etree.XMLSyntaxError:
        raise FiscalValidationError("Invalid Paulistana XML") from None
    if (
        root.tag != f"{{{_NFE}}}PedidoEnvioLoteRPS"
        or getattr(root.getroottree().docinfo, "doctype", None)
        or root.find(f".//{{{_DS}}}Signature") is not None
        or root.find(".//Assinatura") is not None
    ):
        raise FiscalValidationError("Unexpected Paulistana batch root or existing signature")
    header = root.find("Cabecalho")
    if (
        header is None or header.get("Versao") != "2"
        or header.findtext("CPFCNPJRemetente/CNPJ") != issuer_cnpj.value
    ):
        raise FiscalValidationError("Paulistana sender or layout mismatch")
    items = root.findall("RPS")
    if not 1 <= len(items) <= 50 or _digits(header.findtext("QtdRPS", ""), 2) != f"{len(items):02}":
        raise FiscalValidationError("Paulistana RPS count mismatch")
    ccm = _digits(issuer_ccm, 12)
    signing_inputs = [_rps_input(rps, ccm) for rps in items]
    preaudit(tuple(facts for _, facts in signing_inputs))
    material = resolve_certificate(scope, issuer_cnpj.value)
    validate_a1_for_issuer(
        material.pkcs12_bytes, material.password, issuer_cnpj=issuer_cnpj, at=datetime.now(UTC),
    )
    key, cert, _ = pkcs12.load_key_and_certificates(material.pkcs12_bytes, material.password)
    if not isinstance(key, rsa.RSAPrivateKey) or cert is None:
        raise FiscalValidationError("Paulistana signature requires an RSA A1")
    for rps, (signed_fields, _) in zip(items, signing_inputs, strict=True):
        signature = etree.Element("Assinatura")
        signature.text = base64.b64encode(
            key.sign(signed_fields, padding.PKCS1v15(), hashes.SHA1())
        ).decode("ascii")
        rps.insert(0, signature)
    append_nfse_signature(root, root, key, cert, legacy_abrasf=True, whole_document=True)
    signed = etree.tostring(root, encoding="utf-8", xml_declaration=True)
    _validator().validate_document(signed)
    envelope = etree.Element(f"{{{_SOAP}}}Envelope", nsmap={"soap": _SOAP})
    body = etree.SubElement(envelope, f"{{{_SOAP}}}Body")
    request = etree.SubElement(body, f"{{{_NFE}}}TesteEnvioLoteRPSRequest", nsmap={"ws": _NFE})
    etree.SubElement(request, f"{{{_NFE}}}VersaoSchema").text = "2"
    etree.SubElement(request, f"{{{_NFE}}}MensagemXML").text = signed.decode("utf-8")
    return PaulistanaTestEnvelope(etree.tostring(envelope, encoding="utf-8", xml_declaration=True))
