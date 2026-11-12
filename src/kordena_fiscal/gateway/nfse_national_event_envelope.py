"""Trusted, size-bounded SEFIN event JSON envelope; no network or state promotion.

The national API accepts signed pedRegEvento as gzip+base64 in
pedidoRegistroEventoXmlGZipB64. This module does not send the message.
"""
from __future__ import annotations

import base64
import gzip
import json

from kordena_fiscal.domain import FiscalValidationError
from kordena_fiscal.issuance.nfse_national_events import (
    NationalEventIntent,
    build_signed_national_event,
)
from kordena_fiscal.vault import EphemeralCertificateMaterial

_MAX_SIGNED_XML = 2_097_152


def build_national_event_post_body(
    intent: NationalEventIntent, certificate_material: EphemeralCertificateMaterial,
) -> bytes:
    """Build only a ready-to-transmit event message from a governed intent."""
    signed = build_signed_national_event(intent, certificate_material)
    if not signed or len(signed) > _MAX_SIGNED_XML:
        raise FiscalValidationError("National event signed XML exceeds transport limits")
    packed = base64.b64encode(gzip.compress(signed, mtime=0)).decode("ascii")
    return json.dumps(
        {"pedidoRegistroEventoXmlGZipB64": packed},
        sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
