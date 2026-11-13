"""Cajamar GeisWeb canonical issuance and read-only lot recovery factories.

Cajamar-only extraction. The fiscal Core owns tax rules and original RPS state;
later cities extend this municipal adapter module incrementally.
"""
from __future__ import annotations

from collections.abc import Callable

from kordena_fiscal.gateway.cajamar_geisweb_homologation import CajamarPreparedNfse
from kordena_fiscal.gateway.cajamar_geisweb_issue_builder import (
    CajamarGeiswebIssueData,
    prepare_cajamar_signed_issue,
)
from kordena_fiscal.gateway.cajamar_geisweb_request_builder import (
    prepare_cajamar_original_lot_query,
)
from kordena_fiscal.gateway.sp4_municipal_canonical import (
    Sp4CanonicalMunicipalError,
    Sp4OriginalRps,
)
from kordena_fiscal.issuance.nfe_nfse import NfseAuthorizationRequest


def build_cajamar_reviewed_request_factory(
    *,
    build_signed_issue: Callable[
        [NfseAuthorizationRequest, Sp4OriginalRps], CajamarPreparedNfse
    ],
    sign_lot_query: Callable[[bytes], bytes],
    validate_signed_query: Callable[[bytes], None],
) -> Callable[
    [NfseAuthorizationRequest, Sp4OriginalRps, str], CajamarPreparedNfse
]:
    """Compose original-lot recovery and taxpayer-specific emission builder."""
    if not all(callable(x) for x in (
        build_signed_issue, sign_lot_query, validate_signed_query,
    )):
        raise Sp4CanonicalMunicipalError("Cajamar builder ports unavailable")

    def prepare(
        request: NfseAuthorizationRequest, source: Sp4OriginalRps, method: str,
    ) -> CajamarPreparedNfse:
        if method == "EnviaLoteRps":
            return build_signed_issue(request, source)
        if method != "ConsultaLoteRps":
            raise Sp4CanonicalMunicipalError("Unsupported Cajamar issuance/recovery method")
        return prepare_cajamar_original_lot_query(
            source=source, tax_regime=request.document.issuer.tax_regime,
            sign_document=sign_lot_query,
            validate_signed_request=validate_signed_query,
        )

    return prepare



def build_cajamar_geisweb_issue_request_factory(
    *,
    resolve_issue_fields: Callable[
        [NfseAuthorizationRequest, Sp4OriginalRps], CajamarGeiswebIssueData
    ],
    sign_issue: Callable[[bytes], bytes],
    validate_signed_issue: Callable[[bytes], None],
    sign_lot_query: Callable[[bytes], bytes],
    validate_signed_query: Callable[[bytes], None],
) -> Callable[
    [NfseAuthorizationRequest, Sp4OriginalRps, str], CajamarPreparedNfse
]:
    """Concrete GeisWeb issue + recovery factory using existing fiscal ports.

    Fiscal policy owns the city-specific issue fields. The builder never
    substitutes a new RPS number, taxpayer, tax amount or signature engine.
    """
    if not all(callable(x) for x in (
        resolve_issue_fields, sign_issue, validate_signed_issue,
        sign_lot_query, validate_signed_query,
    )):
        raise Sp4CanonicalMunicipalError("Cajamar fiscal issue ports unavailable")

    def issue(
        request: NfseAuthorizationRequest, source: Sp4OriginalRps,
    ) -> CajamarPreparedNfse:
        return prepare_cajamar_signed_issue(
            request=request, original=source,
            fields=resolve_issue_fields(request, source),
            sign_document=sign_issue,
            validate_signed_request=validate_signed_issue,
        )

    return build_cajamar_reviewed_request_factory(
        build_signed_issue=issue, sign_lot_query=sign_lot_query,
        validate_signed_query=validate_signed_query,
    )
