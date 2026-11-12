"""City-specific reviewed preparation factories for existing SP4 driver ports.

No second fiscal engine is introduced: the canonical motor owns service
tax calculation, issue XML, durable source identifiers and policy; these
factories implement the municipality's read-only recovery envelopes using
the same original persisted document. Issuance builders are injected ports.
"""
from __future__ import annotations

from collections.abc import Callable

from kordena_fiscal.domain import ExecutionScope
from kordena_fiscal.gateway.cajamar_geisweb_homologation import CajamarPreparedNfse
from kordena_fiscal.gateway.cajamar_geisweb_request_builder import (
    prepare_cajamar_original_lot_query,
)
from kordena_fiscal.gateway.jundiai_giss_homologation import JundiaiSignedOperation
from kordena_fiscal.gateway.jundiai_giss_request_builder import (
    prepare_jundiai_original_rps_query,
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


def build_jundiai_reviewed_request_factory(
    *,
    build_signed_issue: Callable[
        [NfseAuthorizationRequest, Sp4OriginalRps], JundiaiSignedOperation
    ],
    resolve_municipal_registration: Callable[[ExecutionScope, str], str],
    sign_rps_query: Callable[[bytes], bytes],
    validate_signed_query: Callable[[bytes], None],
) -> Callable[
    [NfseAuthorizationRequest, Sp4OriginalRps, str], JundiaiSignedOperation
]:
    """Compose Giss 2.04 issuer-scoped RPS query and existing issue builder."""
    if not all(callable(x) for x in (
        build_signed_issue, resolve_municipal_registration,
        sign_rps_query, validate_signed_query,
    )):
        raise Sp4CanonicalMunicipalError("Jundiai builder ports unavailable")

    def prepare(
        request: NfseAuthorizationRequest, source: Sp4OriginalRps, method: str,
    ) -> JundiaiSignedOperation:
        if method == "RecepcionarLoteRps":
            return build_signed_issue(request, source)
        if method != "ConsultarNfsePorRps":
            raise Sp4CanonicalMunicipalError("Unsupported Jundiai issuance/recovery method")
        municipal_registration = resolve_municipal_registration(
            source.scope, source.issuer_cnpj.value,
        )
        return prepare_jundiai_original_rps_query(
            original=source, regime=request.document.issuer.tax_regime,
            municipal_registration=municipal_registration,
            sign_document=sign_rps_query,
            validate_signed_request=validate_signed_query,
        )

    return prepare
