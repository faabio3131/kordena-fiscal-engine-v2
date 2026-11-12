"""Osasco WCF RTC_EmitirNFE (manual municipal v2.1, Apr/2026).

Maps only canonical service figures and tax-engine-reviewed RTC classifications.
Authentication key is never accepted here: OsascoRtcHomologationTransport inserts
the active tenant-scoped key into the empty ChaveAutenticacao WCF DTO field.
WSDL/schema validation remains an injected port. No I/O, RPS reservation or
parallel fiscal engine is implemented in this serializer.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal

from lxml import etree

from kordena_fiscal.domain import FiscalValidationError, TaxRegimeCode
from kordena_fiscal.gateway.osasco_rtc_homologation import OsascoPreparedOperation
from kordena_fiscal.gateway.sp4_municipal_canonical import Sp4OriginalRps
from kordena_fiscal.issuance.nfe_nfse import NfseAuthorizationRequest

_WCF = "http://tempuri.org/"
_MSG = "http://schemas.datacontract.org/2004/07/Eissnfe.Negocio.WebServices.Mensagem"
_ISS = "http://schemas.datacontract.org/2004/07/Eissnfe.Dominio.DataTransferObject.Prestador"
_TAKER = "http://schemas.datacontract.org/2004/07/Eissnfe.Dominio.DataTransferObject.Contribuinte"
_MAX = 2_097_152


class OsascoRtcIssueError(FiscalValidationError):
    """Osasco RTC metadata is inconsistent with the original canonical RPS."""


@dataclass(frozen=True, slots=True)
class OsascoRtcRecipient:
    """Reviewed recipient identity and complete domestic municipal address."""

    tax_id: str
    name: str
    street: str
    street_type: str
    number: str
    neighborhood: str
    postal_code: str
    city: str
    city_ibge: str
    state: str
    country: str = "BRASIL"


@dataclass(frozen=True, slots=True)
class OsascoRtcTaxFields:
    """RTC classifications and tax options resolved by existing fiscal policies."""

    activity: str
    class_trib: str
    nbs_code: str
    incidence_location: str
    operation_indicator: str
    service_city: str
    service_city_ibge: str
    service_state: str
    recipient: OsascoRtcRecipient
    iss_rate: Decimal = Decimal("0")
    iss_withheld: bool = False
    no_iss_incidence: bool = False
    # The municipality has per-tax fields; do not derive them from gross value.
    pis: Decimal = Decimal("0")
    cofins: Decimal = Decimal("0")
    csll: Decimal = Decimal("0")
    income_tax: Decimal = Decimal("0")
    inss: Decimal = Decimal("0")
    other_taxes: Decimal = Decimal("0")
    additional_info: str = ""


def _str(value: str, field: str, max_len: int, *, numeric: bool = False) -> str:
    if (
        not isinstance(value, str)
        or not 0 < len(value.strip()) <= max_len
        or any(ord(c) < 32 for c in value)
    ):
        raise OsascoRtcIssueError(f"Invalid Osasco {field}")
    value = value.strip()
    if numeric and (not value.isascii() or not value.isdecimal()):
        raise OsascoRtcIssueError(f"Invalid Osasco numeric {field}")
    return value


def _decimal(value: Decimal, field: str) -> str:
    if (
        not isinstance(value, Decimal) or not value.is_finite()
        or value < 0 or value >= Decimal("1000000000000")
        or value * 100 != (value * 100).to_integral_value()
    ):
        raise OsascoRtcIssueError(f"Invalid Osasco {field}")
    return format(value, ".2f")


def _append(parent: etree._Element, namespace: str, name: str, value: str) -> None:
    etree.SubElement(parent, f"{{{namespace}}}{name}").text = value


def _validate_fields(fields: OsascoRtcTaxFields) -> None:
    if not isinstance(fields, OsascoRtcTaxFields):
        raise OsascoRtcIssueError("Osasco fiscal RTC metadata unavailable")
    _str(fields.activity, "activity", 5)
    _str(fields.class_trib, "RTC classification", 16)
    _str(fields.nbs_code, "NBS", 20)
    _str(fields.incidence_location, "incidence location", 12, numeric=True)
    _str(fields.operation_indicator, "operation indicator", 12)
    _str(fields.service_city, "service city", 100)
    _str(fields.service_city_ibge, "service IBGE", 7, numeric=True)
    if len(fields.service_city_ibge) != 7:
        raise OsascoRtcIssueError("Invalid service municipality code")
    if (
        not isinstance(fields.service_state, str)
        or len(fields.service_state) != 2
        or not fields.service_state.isascii()
        or not fields.service_state.isalpha()
        or not fields.service_state.isupper()
        or not isinstance(fields.iss_withheld, bool)
        or not isinstance(fields.no_iss_incidence, bool)
    ):
        raise OsascoRtcIssueError("Invalid Osasco service location/tax attributes")
    if (
        not isinstance(fields.iss_rate, Decimal) or not fields.iss_rate.is_finite()
        or fields.iss_rate < 0 or fields.iss_rate > 5
    ):
        raise OsascoRtcIssueError("Osasco ISS rate must follow municipal legal policy")
    for key in ("pis", "cofins", "csll", "income_tax", "inss", "other_taxes"):
        _decimal(getattr(fields, key), key)
    if not isinstance(fields.recipient, OsascoRtcRecipient):
        raise OsascoRtcIssueError("Osasco recipient missing")
    p = fields.recipient
    if (
        len(_str(p.tax_id, "recipient tax ID", 14, numeric=True)) not in (11, 14)
        or len(_str(p.postal_code, "postal code", 8, numeric=True)) != 8
        or len(_str(p.city_ibge, "recipient IBGE", 7, numeric=True)) != 7
        or len(_str(p.state, "recipient UF", 2)) != 2
    ):
        raise OsascoRtcIssueError("Invalid recipient registration/address")
    for name, maximum in (
        ("name", 100), ("street", 200), ("street_type", 5), ("number", 10),
        ("neighborhood", 60), ("city", 100), ("country", 100),
    ):
        _str(getattr(p, name), name, maximum)
    if not isinstance(fields.additional_info, str) or len(fields.additional_info) > 2000:
        raise OsascoRtcIssueError("Osasco additional information exceeds limit")


def build_osasco_rtc_issue_xml(
    *, request: NfseAuthorizationRequest, original: Sp4OriginalRps,
    fields: OsascoRtcTaxFields,
) -> bytes:
    """One source-scoped WCF method (SOAP envelope added by the city transport)."""
    if (
        not isinstance(request, NfseAuthorizationRequest)
        or not isinstance(original, Sp4OriginalRps)
    ):
        raise OsascoRtcIssueError("Canonical Osasco authorization request required")
    doc = request.document
    if (
        original.issuer_ibge != "3534401"
        or doc.scope.identity_partition_key != original.scope.identity_partition_key
        or doc.document_id != original.document_id
        or request.request_fingerprint != original.request_fingerprint
        or doc.issuer.cnpj != original.issuer_cnpj
        or doc.competence_date != original.competence_date
        or doc.totals.gross_amount.amount != original.gross_amount
        or doc.competence_date.year < 2026
        or doc.issuer.tax_regime in (
            TaxRegimeCode.MEI,
            TaxRegimeCode.SIMPLES_NACIONAL,
            TaxRegimeCode.SIMPLES_NACIONAL_EXCESS_SUBLIMIT,
        )
        or len(doc.services) != 1
        or not original.rps_number.isascii()
        or not original.rps_number.isdecimal()
        or not 1 <= len(original.rps_number) <= 20
        or int(original.rps_number) < 1
    ):
        raise OsascoRtcIssueError("Osasco RTC requires matching normal-regime 2026 source")
    _validate_fields(fields)
    if (
        doc.service_jurisdiction.municipality_ibge_code != fields.service_city_ibge
        or doc.service_jurisdiction.state_code != fields.service_state
        or doc.services[0].gross_amount.amount != original.gross_amount
    ):
        raise OsascoRtcIssueError("Osasco legal service location or amount mismatch")
    service = doc.services[0]
    p = fields.recipient
    nss = {"tem": _WCF, "eis": _MSG, "iss": _ISS, "con": _TAKER}
    root = etree.Element(f"{{{_WCF}}}RTC_EmitirNFE", nsmap=nss)
    wrapped = etree.SubElement(root, f"{{{_WCF}}}request")
    note = etree.SubElement(wrapped, f"{{{_MSG}}}NotaFiscal_RTC")
    issue = lambda name, value: _append(note, _ISS, name, value)

    # Official request layout, manual v2.1 pp.5-6: WCF field ordering.
    issue("Aliquota", _decimal(fields.iss_rate, "ISS rate"))
    issue("Atividade", fields.activity)
    issue("ChaveAutenticacao", "")  # scoped credential inserted by transport
    issue("CidadePrestacaoServico", fields.service_city)
    issue("CodigoCidadeIBGEPrestacaoServico", fields.service_city_ibge)
    issue("DataRecibo", doc.issued_at.date().isoformat())
    issue("DeduzirRepasse", "false")
    issue("EstadoPrestacaoServico", fields.service_state)
    issue("Homologacao", "true")  # synthetic/homologation-mode invoice only
    if fields.additional_info:
        issue("InformacoesAdicionais", fields.additional_info)
    issue("NotificarTomadorPorEmail", "false")
    issue("NumeroRecibo", original.rps_number)
    issue("SemIncidenciaISS", "true" if fields.no_iss_incidence else "false")
    issue("SimplesNacional", "false")
    issue("SubstituicaoTributaria", "true" if fields.iss_withheld else "false")

    recipient = etree.SubElement(note, f"{{{_ISS}}}Tomador")
    if len(p.tax_id) == 14:
        _append(recipient, _TAKER, "CNPJ", p.tax_id)
    else:
        _append(recipient, _TAKER, "CPF", p.tax_id)
    address = etree.SubElement(recipient, f"{{{_TAKER}}}Endereco")
    for key, value in (
        ("Bairro", p.neighborhood), ("CEP", p.postal_code),
        ("Cidade", p.city), ("CodigoCidadeIBGE", p.city_ibge),
        ("Estado", p.state), ("Logradouro", p.street),
        ("Numero", p.number), ("Pais", p.country),
        ("TipoLogradouro", p.street_type),
    ):
        _append(address, _TAKER, key, value)
    _append(recipient, _TAKER, "Nome", p.name)

    issue("TomadorEstrangeiro", "false")
    issue("Valor", _decimal(original.gross_amount, "original gross amount"))
    issue("ValorCSLL", _decimal(fields.csll, "CSLL"))
    issue("ValorCofins", _decimal(fields.cofins, "COFINS"))
    issue("ValorDeducao", _decimal(service.deduction_amount.amount, "deduction"))
    issue("ValorINSS", _decimal(fields.inss, "INSS"))
    issue("ValorIR", _decimal(fields.income_tax, "IR"))
    issue("ValorOutrosImpostos", _decimal(fields.other_taxes, "other taxes"))
    issue("ValorPisPasep", _decimal(fields.pis, "PIS"))
    issue("nrExercicioReferencia", str(original.competence_date.year))
    issue("nrMesReferencia", f"{original.competence_date.month:02d}")
    issue("ClassTrib", fields.class_trib)
    issue("CodigoNBS", fields.nbs_code)
    issue("IdLocalIncidencia", fields.incidence_location)
    issue("IndOperacao", fields.operation_indicator)
    raw = etree.tostring(root, xml_declaration=True, encoding="utf-8")
    if len(raw) > _MAX:
        raise OsascoRtcIssueError("Osasco RTC signed request exceeds maximum payload")
    return raw


def prepare_osasco_rtc_issue(
    *, request: NfseAuthorizationRequest, original: Sp4OriginalRps,
    fields: OsascoRtcTaxFields, validate_request: Callable[[bytes], None],
) -> OsascoPreparedOperation:
    """Send the canonical WCF payload to the existing schema validation port."""
    if not callable(validate_request):
        raise OsascoRtcIssueError("Osasco reviewed WCF schema validator missing")
    raw = build_osasco_rtc_issue_xml(
        request=request, original=original, fields=fields,
    )
    validate_request(raw)
    return OsascoPreparedOperation(
        scope=original.scope, issuer_cnpj=original.issuer_cnpj,
        tax_regime=request.document.issuer.tax_regime,
        competence_date=original.competence_date,
        method="RTC_EmitirNFE", request_xml=raw,
    )
