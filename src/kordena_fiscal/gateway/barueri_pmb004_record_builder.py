"""Barueri PMB004 v4.2: position-accurate RPS Type 2 and RTC Type 4.

Per official Barueri Financas layout (06 Jan 2026). The tax engine supplies
reviewed service, recipient and IBS/CBS classifications. The two serializers
use the same immutable original RPS; they do NOT calculate any taxes, allocate
numbers, resolve identities from browser data or call municipal services.
Optional Type 3/5 records are separate specialist tax-engine ports.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from kordena_fiscal.domain import FiscalValidationError, TaxRegimeCode
from kordena_fiscal.gateway.barueri_pmb004_batch_builder import (
    build_barueri_single_rps_batch,
)
from kordena_fiscal.gateway.barueri_pmb004_homologation import BarueriRpsBatch
from kordena_fiscal.gateway.sp4_municipal_canonical import Sp4OriginalRps
from kordena_fiscal.issuance.nfe_nfse import NfseAuthorizationRequest


class BarueriPmb004RecordError(FiscalValidationError):
    """Original Barueri fiscal facts or 2026 fixed-width field layout differ."""


@dataclass(frozen=True, slots=True)
class BarueriPmb004Recipient:
    tax_id: str
    legal_name: str
    street: str
    street_number: str
    district: str
    city: str
    state: str
    postal_code: str
    city_ibge: str
    email: str = ""
    complement: str = ""


@dataclass(frozen=True, slots=True)
class BarueriPmb004IssueFields:
    """Municipal service and RTC code correlations resolved by the tax engine."""

    service_code: str
    service_location_code: str
    public_way_code: str
    street: str
    street_number: str
    district: str
    city: str
    state: str
    postal_code: str
    recipient: BarueriPmb004Recipient
    nbs_code: str
    operation_indicator: str
    tax_classification: str
    ibs_cbs_status: str
    simples_status: str = "1"
    simples_assessment: str = ""
    personal_use: str = "0"
    recipient_differs: str = "0"
    municipal_note_series: str = ""
    street_complement: str = ""
    # Reviewed retained taxes: IRRF, PIS, COFINS, CSLL, INSS.
    federal_retentions: tuple[tuple[str, Decimal], ...] = ()
    # Type 5 is created by the separate fiscal-special-cases rule component.


def _ascii(value: str, name: str, max_len: int, *, required: bool = True) -> bytes:
    if (
        not isinstance(value, str)
        or len(value) > max_len
        or (required and not value.strip())
        or not value.isascii()
        or any(ord(x) < 32 for x in value)
    ):
        raise BarueriPmb004RecordError(f"Invalid PMB004 {name}")
    return value.encode("ascii")


def _digits(value: str, name: str, width: int) -> bytes:
    b = _ascii(value, name, width)
    if not value.isdecimal() or not value.isascii():
        raise BarueriPmb004RecordError(f"PMB004 {name} must contain decimal digits")
    return b


def _cents(value: Decimal, name: str) -> int:
    if (
        not isinstance(value, Decimal) or not value.is_finite() or value < 0
        or value * 100 != (value * 100).to_integral_value()
    ):
        raise BarueriPmb004RecordError(f"Invalid PMB004 {name}")
    result = int(value * 100)
    if result >= 10**15:
        raise BarueriPmb004RecordError(f"PMB004 {name} overflow")
    return result


def _write(
    row: bytearray, first: int, last: int, value: bytes, *,
    numeric: bool = False,
) -> None:
    """One-based, inclusive official positions. No silent field truncation."""
    width = last - first + 1
    if len(value) > width or any(x in value for x in (b"\r", b"\n")):
        raise BarueriPmb004RecordError("PMB004 layout field length invalid")
    if numeric and not value.isdigit():
        raise BarueriPmb004RecordError("PMB004 numeric field not decimal")
    padded = value.rjust(width, b"0") if numeric else value.ljust(width, b" ")
    row[first - 1:last] = padded


def _source(
    request: NfseAuthorizationRequest, original: Sp4OriginalRps,
    fields: BarueriPmb004IssueFields,
) -> None:
    if (
        not isinstance(request, NfseAuthorizationRequest)
        or not isinstance(original, Sp4OriginalRps)
        or not isinstance(fields, BarueriPmb004IssueFields)
    ):
        raise BarueriPmb004RecordError("Barueri canonical RPS/RTC facts required")
    doc = request.document
    if (
        original.issuer_ibge != "3505708"
        or original.scope.identity_partition_key != doc.scope.identity_partition_key
        or original.document_id != doc.document_id
        or original.request_fingerprint != request.request_fingerprint
        or original.issuer_cnpj != doc.issuer.cnpj
        or original.competence_date != doc.competence_date
        or original.gross_amount != doc.totals.gross_amount.amount
        or len(doc.services) != 1
        or doc.services[0].gross_amount.amount != original.gross_amount
        or not original.rps_number.isascii()
        or not original.rps_number.isdecimal()
        or not 1 <= len(original.rps_number) <= 7
        or int(original.rps_number) < 1
        or not original.municipal_batch_id
        or len(original.municipal_batch_id) != 11
    ):
        raise BarueriPmb004RecordError("Barueri record differs from persisted RPS")
    if doc.service_jurisdiction.state_code != fields.state:
        raise BarueriPmb004RecordError("Barueri service state differs from canonical source")
    _digits(fields.service_code, "service code", 9)
    _digits(fields.nbs_code, "NBS", 9)
    _digits(fields.operation_indicator, "operation indicator", 6)
    _digits(fields.tax_classification, "IBS/CBS classification", 6)
    _digits(fields.ibs_cbs_status, "IBS/CBS CST", 3)
    if (
        len(fields.nbs_code) != 9
        or len(fields.operation_indicator) != 6
        or len(fields.tax_classification) != 6
        or len(fields.ibs_cbs_status) != 3
        or fields.tax_classification[:3] != fields.ibs_cbs_status
    ):
        raise BarueriPmb004RecordError("Barueri NBS/IBS/CBS code correlation incomplete")
    if (
        fields.service_location_code not in ("1", "2")
        or fields.public_way_code not in ("1", "2")
        or fields.personal_use not in ("0", "1")
        or fields.recipient_differs not in ("0", "1")
        or fields.recipient_differs != "0"
        or fields.simples_status not in ("1", "2", "3")
        or fields.simples_assessment not in ("", "1", "2", "3")
    ):
        raise BarueriPmb004RecordError("Barueri fiscal conditional special cases unsupported")
    expected = {
        TaxRegimeCode.MEI: "2",
        TaxRegimeCode.SIMPLES_NACIONAL: "3",
        TaxRegimeCode.SIMPLES_NACIONAL_EXCESS_SUBLIMIT: "3",
    }.get(doc.issuer.tax_regime, "1")
    if (
        fields.simples_status != expected
        or (expected == "3" and not fields.simples_assessment)
        or (expected != "3" and fields.simples_assessment)
    ):
        raise BarueriPmb004RecordError("Barueri original taxpayer classification differs")
    p = fields.recipient
    if not isinstance(p, BarueriPmb004Recipient):
        raise BarueriPmb004RecordError("Barueri recipient missing")
    if (
        len(_digits(p.tax_id, "recipient tax ID", 14)) not in (11, 14)
        or len(_digits(p.postal_code, "recipient CEP", 8)) != 8
        or len(_digits(p.city_ibge, "recipient IBGE", 7)) != 7
        or len(_digits(fields.postal_code, "service CEP", 8)) != 8
        or len(_ascii(p.state, "recipient UF", 2)) != 2
        or len(_ascii(fields.state, "service UF", 2)) != 2
    ):
        raise BarueriPmb004RecordError("Barueri domestic address/recipient invalid")
    if len(p.tax_id) == 14 and not p.email:
        raise BarueriPmb004RecordError("Barueri business recipient email required")
    for value, name, length in (
        (p.legal_name, "recipient name", 60), (p.street, "recipient street", 75),
        (p.street_number, "recipient number", 9),
        (p.complement, "recipient complement", 30),
        (p.district, "recipient district", 40),
        (p.city, "recipient city", 40), (p.email, "recipient email", 152),
        (fields.street, "service street", 75),
        (fields.street_number, "service number", 9),
        (fields.street_complement, "service complement", 30),
        (fields.district, "service district", 40),
        (fields.city, "service city", 40),
    ):
        _ascii(value, name, length, required=name not in (
            "recipient complement", "service complement", "recipient email",
        ))
    if not isinstance(fields.federal_retentions, tuple):
        raise BarueriPmb004RecordError("Barueri federal withholdings must be reviewed")
    seen: set[str] = set()
    total = 0
    for item in fields.federal_retentions:
        if not isinstance(item, tuple) or len(item) != 2:
            raise BarueriPmb004RecordError("Barueri withholding entry invalid")
        code, amount = item
        if not isinstance(code, str) or code not in {"01", "02", "03", "04", "05"}:
            raise BarueriPmb004RecordError("Barueri unsupported federal withholding code")
        if code in seen:
            raise BarueriPmb004RecordError("Barueri duplicate federal withholding")
        seen.add(code)
        cents = _cents(amount, "federal withholding")
        if cents <= 0:
            raise BarueriPmb004RecordError("Barueri withholding must be positive")
        total += cents
    if total >= 10**15:
        raise BarueriPmb004RecordError("Barueri withholding total overflow")
    if Decimal(total) / 100 > original.gross_amount:
        raise BarueriPmb004RecordError("Barueri withholdings exceed service value")
    if doc.services[0].deduction_amount.amount != Decimal("0"):
        # Existing municipal special tax rules must supply Type 3/VN to
        # represent deductions, not silently omit them from the remittance.
        raise BarueriPmb004RecordError("Barueri deduction needs reviewed VN record")


def build_barueri_rps_type2(
    *, request: NfseAuthorizationRequest, original: Sp4OriginalRps,
    fields: BarueriPmb004IssueFields,
) -> bytes:
    """1970-byte Type 2; every field occupies its official one-based position."""
    _source(request, original, fields)
    doc = request.document
    p = fields.recipient
    detail = bytearray(b" " * 1970)
    _write(detail, 1, 6, b"2RPS  ")
    _write(detail, 7, 10, _ascii(original.rps_series, "RPS series", 4, required=False))
    _write(detail, 11, 15, _ascii(fields.municipal_note_series, "NF series", 5, required=False))
    _write(detail, 16, 25, _digits(original.rps_number, "RPS number", 7), numeric=True)
    _write(detail, 26, 33, doc.issued_at.strftime("%Y%m%d").encode("ascii"))
    _write(detail, 34, 39, doc.issued_at.strftime("%H%M%S").encode("ascii"))
    _write(detail, 40, 40, b"E")
    _write(detail, 243, 251, _digits(fields.service_code, "service code", 9), numeric=True)
    _write(detail, 252, 252, fields.service_location_code.encode("ascii"))
    _write(detail, 253, 253, fields.public_way_code.encode("ascii"))
    for start, end, value in (
        (254, 328, fields.street), (329, 337, fields.street_number),
        (338, 367, fields.street_complement), (368, 407, fields.district),
        (408, 447, fields.city), (448, 449, fields.state),
    ):
        _write(detail, start, end, value.encode("ascii"))
    _write(detail, 450, 457, fields.postal_code.encode("ascii"))
    _write(detail, 458, 463, b"1", numeric=True)
    unit_cents = _cents(original.gross_amount, "service gross")
    _write(detail, 464, 478, str(unit_cents).encode("ascii"), numeric=True)
    withheld_cents = sum(
        _cents(amount, "withheld federal tax")
        for _, amount in fields.federal_retentions
    )
    _write(detail, 484, 498, str(withheld_cents).encode("ascii"), numeric=True)
    _write(detail, 499, 499, b"2")  # domestic buyer
    _write(detail, 503, 503, b"2")  # non-exported service
    _write(detail, 504, 504, b"1" if len(p.tax_id) == 11 else b"2")
    _write(detail, 505, 518, p.tax_id.encode("ascii"), numeric=True)
    for start, end, value in (
        (519, 578, p.legal_name), (579, 653, p.street),
        (654, 662, p.street_number), (663, 692, p.complement),
        (693, 732, p.district), (733, 772, p.city),
        (773, 774, p.state), (783, 934, p.email),
    ):
        _write(detail, start, end, value.encode("ascii"))
    _write(detail, 775, 782, p.postal_code.encode("ascii"))
    _write(detail, 971, 1970, _ascii(doc.services[0].description, "service description", 1000))
    return bytes(detail)


def build_barueri_rtc_type4(
    *, request: NfseAuthorizationRequest, original: Sp4OriginalRps,
    fields: BarueriPmb004IssueFields,
) -> bytes:
    """531-byte RTC/ADN Type 4, matched to the source and 2026 classification."""
    _source(request, original, fields)
    rtc = bytearray(b" " * 531)
    _write(rtc, 1, 1, b"4")
    _write(rtc, 2, 2, fields.simples_status.encode("ascii"))
    if fields.simples_status == "3":
        _write(rtc, 3, 3, fields.simples_assessment.encode("ascii"))
    service_ibge = request.document.service_jurisdiction.municipality_ibge_code
    if service_ibge is None or len(_digits(service_ibge, "service IBGE", 7)) != 7:
        raise BarueriPmb004RecordError("Missing official Barueri service IBGE")
    _write(rtc, 7, 13, service_ibge.encode("ascii"))
    _write(rtc, 14, 20, fields.recipient.city_ibge.encode("ascii"))
    _write(rtc, 61, 69, fields.nbs_code.encode("ascii"))
    _write(rtc, 515, 520, fields.operation_indicator.encode("ascii"))
    _write(rtc, 521, 526, fields.tax_classification.encode("ascii"))
    _write(rtc, 527, 529, fields.ibs_cbs_status.encode("ascii"))
    _write(rtc, 530, 530, fields.personal_use.encode("ascii"))
    _write(rtc, 531, 531, fields.recipient_differs.encode("ascii"))
    return bytes(rtc)


def build_barueri_federal_retention_type3(
    *, request: NfseAuthorizationRequest, original: Sp4OriginalRps,
    fields: BarueriPmb004IssueFields,
) -> tuple[bytes, ...]:
    """PMB004 Type 3 records, one per reviewed withheld federal tax.

    VN (other values outside the service base) is separate, not a retention.
    """
    _source(request, original, fields)
    return tuple(
        b"3" + code.encode("ascii")
        + f"{_cents(amount, 'withheld tax'):015d}".encode("ascii")
        for code, amount in fields.federal_retentions
    )


def build_barueri_reviewed_issue_batch(
    *, request: NfseAuthorizationRequest, original: Sp4OriginalRps,
    fields: BarueriPmb004IssueFields,
    municipal_registration: str,
) -> BarueriRpsBatch:
    """Connect the verified Type 2/4 to existing PMB004 1/9 batch builder."""
    if (
        not isinstance(municipal_registration, str)
        or len(municipal_registration) != 7
        or not municipal_registration.isascii()
        or not municipal_registration.isalnum()
    ):
        raise BarueriPmb004RecordError("Unreviewed Barueri municipal registration")
    detail = build_barueri_rps_type2(
        request=request, original=original, fields=fields,
    )
    rtc = build_barueri_rtc_type4(
        request=request, original=original, fields=fields,
    )
    retentions = build_barueri_federal_retention_type3(
        request=request, original=original, fields=fields,
    )
    return build_barueri_single_rps_batch(
        source=original, regime=request.document.issuer.tax_regime,
        municipal_registration=municipal_registration,
        rps_detail=detail, rtc_adn_detail=rtc,
        retained_tax_records=retentions,
    )
