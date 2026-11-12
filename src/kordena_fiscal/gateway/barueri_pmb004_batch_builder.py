"""Barueri PMB004 official January/2026 fixed-width batch assembler.

The owner of fiscal mapping builds a 1970-byte Type 2 RPS and its 531-byte
RTC/ADN Type 4 companion from the existing tax domain. This assembler
constructs the exact 25-byte header and fiscal Type 9 checksums, with source
RPS identity and amount reconciliation, without replacing the field-by-field
official RPS 4.2 XSD/position validator.

Reference: Barueri RPS_Layout-v4.2.pdf, January/2026. No network calls.
"""
from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from kordena_fiscal.domain import FiscalValidationError, TaxRegimeCode
from kordena_fiscal.gateway.barueri_pmb004_homologation import BarueriRpsBatch
from kordena_fiscal.gateway.sp4_municipal_canonical import Sp4OriginalRps


class BarueriBatchBuilderError(FiscalValidationError):
    """The prepared municipal RPS record disagrees with its durable authority."""


def _row(value: bytes, name: str, prefix: bytes, length: int) -> bytes:
    if (
        not isinstance(value, bytes)
        or len(value) != length
        or not value.startswith(prefix)
        or not value.isascii()
        or b"\r" in value or b"\n" in value
    ):
        raise BarueriBatchBuilderError(f"Invalid official Barueri {name} record")
    return value


def build_barueri_single_rps_batch(
    *, source: Sp4OriginalRps, regime: TaxRegimeCode,
    municipal_registration: str,
    rps_detail: bytes, rtc_adn_detail: bytes,
    retained_tax_record: bytes | None = None,
    optional_record_5: Sequence[bytes] = (),
) -> BarueriRpsBatch:
    """Assemble one immutable, source-scoped PMB004 fiscal remittance.

    No value is invented: the 2026 RPS/RTC records come from the tax engine.
    The builder supplies a fixed-width header/footer and checks original RPS.
    """
    if (
        not isinstance(source, Sp4OriginalRps)
        or source.issuer_ibge != "3505708"
        or not isinstance(regime, TaxRegimeCode)
        or source.municipal_batch_id is None
        or len(source.municipal_batch_id) != 11
        or not isinstance(municipal_registration, str)
        or len(municipal_registration) != 7
        or not municipal_registration.isascii()
        or not municipal_registration.isalnum()
    ):
        raise BarueriBatchBuilderError("Original Barueri municipal RPS authority unavailable")
    detail = _row(rps_detail, "RPS", b"2RPS  ", 1970)
    companion = _row(rtc_adn_detail, "RTC/ADN", b"4", 531)
    if retained_tax_record is not None:
        retention = _row(retained_tax_record, "retention", b"3", 18)
    else:
        retention = None
    extra = [
        _row(item, "optional VAT", b"5", 697)
        for item in optional_record_5
    ]
    number = detail[15:25]
    series = detail[6:10].decode("ascii").strip()
    if (
        not number.isdigit()
        or int(number) != int(source.rps_number)
        or series != source.rps_series
        or detail[39:40] != b"E"
        or not detail[457:463].isdigit()
        or not detail[463:478].isdigit()
    ):
        raise BarueriBatchBuilderError("Barueri RPS detail differs from original")
    quantity = int(detail[457:463])
    unit_cents = int(detail[463:478])
    if quantity < 1 or unit_cents < 1:
        raise BarueriBatchBuilderError("Barueri RPS service quantity/value invalid")
    cents = quantity * unit_cents
    if Decimal(cents) / 100 != source.gross_amount or cents >= 10**15:
        raise BarueriBatchBuilderError("Official Barueri service total differs from source")
    retained_cents = (
        int(retention[3:18]) if retention is not None and retention[3:18].isdigit()
        else 0
    )
    if retained_cents >= 10**15:
        raise BarueriBatchBuilderError("Barueri retention total overflow")
    header = (
        b"1" + municipal_registration.encode("ascii")
        + b"PMB004" + source.municipal_batch_id.encode("ascii")
    )
    rows = [header, detail]
    if retention is not None:
        rows.append(retention)
    rows.append(companion)
    rows.extend(extra)
    line_count = len(rows) + 1
    if line_count > 9_999_999:
        raise BarueriBatchBuilderError("Barueri batch line count overflow")
    footer = (
        b"9" + f"{line_count:07d}".encode("ascii")
        + f"{cents:015d}".encode("ascii")
        + f"{retained_cents:015d}".encode("ascii")
    )
    content = b"\r\n".join((*rows, footer)) + b"\r\n"
    return BarueriRpsBatch(
        scope=source.scope, issuer_cnpj=source.issuer_cnpj,
        municipal_registration=municipal_registration,
        tax_regime=regime, competence_date=source.competence_date,
        remittance=source.municipal_batch_id,
        file_name=source.municipal_batch_id + ".txt",
        rps_bytes=content,
    )
