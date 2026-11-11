"""Fail-closed Extrema WebISS homologation transport (SOAP 1.1, scoped A1).

No endpoint is guessed. A verified engineering-side homologation endpoint must
be installed before this client can be composed. The production ASMX address
is explicitly rejected here, including with a synthetic certificate.
"""
from __future__ import annotations

import re
import ssl
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPSHandler, Request, build_opener

from kordena_fiscal.domain import Cnpj, ExecutionScope, FiscalValidationError
from kordena_fiscal.gateway.fiscal_tls import RejectFiscalRedirects, build_fiscal_tls_context
from kordena_fiscal.gateway.nfse_webiss_extrema import (
    EXTREMA_WEBISS_PUBLIC_SERVICE,
    ExtremaWebissOperation,
    ExtremaWebissSchema,
    ExtremaWebissSoapRequest,
    ExtremaWebissSoapResponse,
    parse_extrema_webiss_soap,
    prepare_extrema_webiss_soap,
)
from kordena_fiscal.vault import EphemeralCertificateMaterial
from kordena_fiscal.vault.a1_preflight import validate_a1_for_issuer

_MAX_RESPONSE = 2 * 1024 * 1024
_MAX_TIMEOUT = 60


class ExtremaWebissTransportError(FiscalValidationError):
    """Sanitized municipal communication failure without upstream body or secrets."""


@dataclass(frozen=True, slots=True)
class VerifiedExtremaHomologationEndpoint:
    """Structurally safe destination bound to an immutable evidence reference.

    The registrar must still independently review the authenticity and
    applicability of the cited official source before activating a binding.
    """

    url: str
    evidence_source_url: str
    evidence_sha256: str

    def __post_init__(self) -> None:
        if not all(
            isinstance(part, str)
            for part in (self.url, self.evidence_source_url, self.evidence_sha256)
        ):
            raise FiscalValidationError("Extrema homologation evidence is incomplete")
        try:
            parsed = urlsplit(self.url)
            source = urlsplit(self.evidence_source_url)
            port = parsed.port
        except ValueError:
            raise FiscalValidationError("Invalid Extrema homologation URL") from None
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or not parsed.hostname.endswith(".webiss.com.br")
            or "extrema" not in parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or port not in (None, 443)
            or parsed.path != "/ws/nfse.asmx"
            or parsed.query or parsed.fragment
            or self.url == EXTREMA_WEBISS_PUBLIC_SERVICE
            or source.scheme != "https"
            or source.hostname not in {"extremamg.webiss.com.br", "extrema.mg.gov.br"}
            or not re.fullmatch(r"[0-9a-f]{64}", self.evidence_sha256)
        ):
            raise FiscalValidationError("Unverified or unsafe Extrema homologation endpoint")

def _exchange_webiss(
    request: ExtremaWebissSoapRequest, context: ssl.SSLContext,
    timeout: float, endpoint: VerifiedExtremaHomologationEndpoint,
) -> bytes:
    http_request = Request(
        endpoint.url, data=request.body, method="POST",
        headers={
            "Content-Type": request.content_type,
            "Accept": "text/xml",
            "SOAPAction": request.soap_action,
        },
    )
    try:
        opener = build_opener(HTTPSHandler(context=context), RejectFiscalRedirects())
        with opener.open(http_request, timeout=timeout) as response:
            body = response.read(_MAX_RESPONSE + 1)
        if len(body) > _MAX_RESPONSE:
            raise ExtremaWebissTransportError("Extrema SOAP response exceeds limit")
        return bytes(body)
    except (HTTPError, URLError, TimeoutError, OSError, ssl.SSLError):
        raise ExtremaWebissTransportError(
            "Extrema WebISS transport unavailable; consult state before resending"
        ) from None


class ExtremaWebissHomologationClient:
    """Transport-only, not fiscal authorization. Does not retry any mutation."""

    def __init__(
        self, *,
        endpoint: VerifiedExtremaHomologationEndpoint,
        schema: ExtremaWebissSchema,
        resolve_certificate: Callable[[ExecutionScope, str], EphemeralCertificateMaterial],
        exchange: Callable[
            [ExtremaWebissSoapRequest, ssl.SSLContext, float, VerifiedExtremaHomologationEndpoint],
            bytes,
        ] | None = None,
        timeout_seconds: float = 15,
    ) -> None:
        if not isinstance(endpoint, VerifiedExtremaHomologationEndpoint):
            raise FiscalValidationError("Approved Extrema homologation endpoint required")
        if not isinstance(schema, ExtremaWebissSchema) or not callable(resolve_certificate):
            raise FiscalValidationError("Extrema requires XSD manifest and scoped A1 resolver")
        if not isinstance(timeout_seconds, (int, float)) or not 0 < timeout_seconds <= _MAX_TIMEOUT:
            raise FiscalValidationError("Invalid Extrema homologation timeout")
        self._endpoint = endpoint
        self._schema = schema
        self._resolve_certificate = resolve_certificate
        self._exchange = exchange or _exchange_webiss
        self._timeout = float(timeout_seconds)

    def request(
        self, *, operation: ExtremaWebissOperation,
        signed_or_query_xml: bytes, scope: ExecutionScope,
        issuer_cnpj: Cnpj, issuer_municipality_ibge: str,
    ) -> ExtremaWebissSoapResponse:
        # Validate public/untrusted XML and jurisdiction BEFORE accessing the Vault.
        prepared = prepare_extrema_webiss_soap(
            operation=operation, signed_or_query_xml=signed_or_query_xml,
            scope=scope, issuer_cnpj=issuer_cnpj,
            issuer_municipality_ibge=issuer_municipality_ibge,
            schema=self._schema,
        )
        material = self._resolve_certificate(scope, issuer_cnpj.value)
        validate_a1_for_issuer(
            material.pkcs12_bytes, material.password,
            issuer_cnpj=issuer_cnpj, at=datetime.now(UTC),
        )
        context = build_fiscal_tls_context(material)
        response = self._exchange(prepared, context, self._timeout, self._endpoint)
        return parse_extrema_webiss_soap(
            operation=operation, soap_response=response, schema=self._schema,
        )
