"""Official ExportaNFe v3 cancellation evidence, correlated to an immutable PMB004 event.

Barueri export record 2, position 67: A (active) or C (cancelled); positions
68-75: cancellation date. A SOAP OK200 or batch status is never this evidence.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from kordena_fiscal.domain import FiscalValidationError
from kordena_fiscal.gateway.barueri_pmb004_homologation import (
    BarueriReceipt,
    BarueriRpsBatch,
)
from kordena_fiscal.gateway.sp4_municipal_canonical import Sp4VerifiedInvoice


class BarueriCancellationProofError(FiscalValidationError):
    """The exported event cannot establish the cancellation of this specific NFS-e."""


@dataclass(frozen=True, slots=True)
class BarueriCancellationEvidence:
    cancelled_on: date
    event_remittance: str
    invoice_number: str
    official_return: bytes


def verify_barueri_cancellation_return(
    *, event: BarueriRpsBatch, issued: Sp4VerifiedInvoice, receipt: BarueriReceipt,
) -> BarueriCancellationEvidence:
    """Require a source-bound Type-2 C and validated ExportaNFe-v3 trailer."""
    if (
        not isinstance(event, BarueriRpsBatch)
        or not isinstance(issued, Sp4VerifiedInvoice)
        or not isinstance(receipt, BarueriReceipt)
        or receipt.operation != "NFeLoteBaixarArquivo"
        or receipt.code != "OK200"
        or receipt.situation not in (None, "1")
        or not isinstance(receipt.downloaded_file, bytes)
        or not 0 < len(receipt.downloaded_file) <= 2_097_152
    ):
        raise BarueriCancellationProofError("Official Barueri cancelled file is absent")
    raw = receipt.downloaded_file
    if b"\x00" in raw or b"\n" in raw.replace(b"\r\n", b""):
        raise BarueriCancellationProofError("Invalid Barueri cancellation file framing")
    rows = raw.replace(b"\r\n", b"\r").split(b"\r")
    if rows and not rows[-1]:
        rows.pop()
    if len(rows) < 4:
        raise BarueriCancellationProofError("Incomplete Barueri cancellation export")
    head, *details, footer = rows
    if (
        len(head) != 41
        or head[0:1] != b"1"
        or head[1:8] != event.municipal_registration.encode("ascii")
        or head[24:30] != b"PMB003"
        or head[30:41] != event.remittance.encode("ascii")
        or len(footer) != 38 or footer[:1] != b"9"
        or not footer[1:8].isdigit()
        or int(footer[1:8]) != len(rows)
        or not footer[8:38].isdigit()
        or len([row for row in details if row[:1] == b"2"]) != 1
        or not any(row[:1] == b"3" for row in details)
        or details[0][:1] != b"2"
        or any(
            row[:1] not in (b"2", b"3", b"4")
            or len(row) != {b"2": 1678, b"3": 95, b"4": 18}[row[:1]]
            for row in details
        )
    ):
        raise BarueriCancellationProofError("Barueri cancellation layout does not match event")
    note = details[0]
    event_records = event.rps_bytes.split(b"\r\n")
    if len(event_records) < 3 or len(event_records[1]) != 1970:
        raise BarueriCancellationProofError("Missing approved event RPS record")
    event_detail = event_records[1]
    if (
        event_detail[39:40] != b"C"
        or event_detail[40:42] not in (b"01", b"02", b"03")
        or not event_detail[42:49].isdigit()
        or not note[5:12].isdigit()
        or not note[54:64].isdigit()
        or int(event_detail[42:49]) != int(issued.invoice_number)
        or int(note[5:12]) != int(issued.invoice_number)
        or int(note[54:64]) != int(issued.rps_number)
        or note[50:54].decode("ascii", "strict").strip() != issued.rps_series
        or note[26:50].decode("ascii", "strict").strip() != issued.verification_code
        or note[1628:1678].decode("ascii", "strict").strip() != issued.invoice_reference
        or note[66:67] != b"C"
    ):
        raise BarueriCancellationProofError("Barueri cancelled note differs from original")
    when = note[67:75]
    try:
        if not when.isdigit():
            raise ValueError
        cancelled = datetime.strptime(when.decode("ascii"), "%Y%m%d").date()
    except ValueError:
        raise BarueriCancellationProofError("Invalid Barueri official cancellation date") from None
    service_cents = 0
    for detail in details[1:]:
        if detail[:1] != b"3":
            continue
        quantity, unit = detail[1:7], detail[76:91]
        if not quantity.isdigit() or not unit.isdigit() or int(quantity) < 1:
            raise BarueriCancellationProofError("Invalid Barueri cancelled service amount")
        service_cents += int(quantity) * int(unit)
    if (
        service_cents != int(footer[8:23])
        or Decimal(service_cents) / 100 != issued.gross_amount
    ):
        raise BarueriCancellationProofError("Barueri cancelled service total differs")
    return BarueriCancellationEvidence(
        cancelled_on=cancelled, event_remittance=event.remittance,
        invoice_number=issued.invoice_number, official_return=raw,
    )
