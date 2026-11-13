"""Cajamar reviewed municipal bridge on the existing SP4 canonical ports.

Other SP municipality adapters are intentionally excluded from this city PR.
The canonical fiscal application and official proof remain authoritative.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Protocol, TypeVar

from lxml import etree

from kordena_fiscal.domain import Cnpj, ExecutionScope, TaxRegimeCode
from kordena_fiscal.gateway.authorization import AuthorizationStatus
from kordena_fiscal.gateway.osasco_rtc_homologation import (
    OsascoOperationReceipt,
    OsascoPreparedOperation,
    OsascoRtcHomologationTransport,
)
from kordena_fiscal.gateway.osasco_rtc_request_builder import (
    build_osasco_original_note_query,
)
from kordena_fiscal.gateway.cajamar_geisweb_cancellation_builder import (
    CajamarCancellationDecision,
    interpret_cajamar_cancel_response,
    prepare_cajamar_cancel,
)
from kordena_fiscal.gateway.cajamar_geisweb_homologation import (
    CajamarGeiswebHomologationTransport,
    CajamarGeiswebResult,
    CajamarPreparedNfse,
)
from kordena_fiscal.gateway.cajamar_geisweb_invoice_interpreter import (
    interpret_cajamar_geisweb_result,
)
from kordena_fiscal.gateway.sp4_municipal_canonical import (
    Sp4CanonicalMunicipalError,
    Sp4OriginalRps,
    Sp4ProviderOutcome,
    Sp4VerifiedInvoice,
)
from kordena_fiscal.issuance.nfe_nfse import NfseAuthorizationRequest

from .sp4_municipal_canonical_composition import Sp4ReviewedMunicipalPorts


class _PreparedSp4Operation(Protocol):
    """Read-only contract for distinct signed, frozen municipal operation DTOs."""

    @property
    def scope(self) -> ExecutionScope: ...

    @property
    def issuer_cnpj(self) -> Cnpj: ...

    @property
    def tax_regime(self) -> TaxRegimeCode: ...

    @property
    def competence_date(self) -> date: ...

    @property
    def method(self) -> str: ...


P = TypeVar("P", bound=_PreparedSp4Operation)


@dataclass(frozen=True, slots=True)
class Sp4BridgeAuthority:
    """Canonical persisted RPS and legal checks, never extracted from a browser."""

    load_original_rps: Callable[[ExecutionScope, str], Sp4OriginalRps]
    fiscal_issuer_policy: Callable[[NfseAuthorizationRequest], None]
    validate_prepared_rps: Callable[[Sp4OriginalRps], None]
    verify_official_invoice_xml: Callable[[Sp4VerifiedInvoice], None]

    def wrap(
        self,
        submit: Callable[
            [NfseAuthorizationRequest, Sp4OriginalRps], Sp4ProviderOutcome
        ],
        query: Callable[
            [NfseAuthorizationRequest, Sp4OriginalRps], Sp4ProviderOutcome
        ],
    ) -> Sp4ReviewedMunicipalPorts:
        if not callable(submit) or not callable(query):
            raise Sp4CanonicalMunicipalError("SP4 municipal bridge operations required")
        return Sp4ReviewedMunicipalPorts(
            load_original_rps=self.load_original_rps,
            fiscal_issuer_policy=self.fiscal_issuer_policy,
            validate_prepared_rps=self.validate_prepared_rps,
            submit_official_rps=submit,
            query_official_rps=query,
            verify_official_invoice_xml=self.verify_official_invoice_xml,
        )


def _validate_prepared_link(
    request: NfseAuthorizationRequest,
    original: Sp4OriginalRps,
    prepared: P,
    *,
    expected_type: type[P],
    expected_method: str,
) -> P:
    """No document, tenant, issuer, tax period or operation substitution."""
    if type(prepared) is not expected_type or (
        prepared.scope.identity_partition_key
        != request.document.scope.identity_partition_key
        or prepared.issuer_cnpj != original.issuer_cnpj
        or prepared.tax_regime != request.document.issuer.tax_regime
        or prepared.competence_date != original.competence_date
        or prepared.method != expected_method
    ):
        raise Sp4CanonicalMunicipalError("Prepared municipal operation conflicts with original RPS")
    return prepared


def _verified_outcome(value: object) -> Sp4ProviderOutcome:
    if not isinstance(value, Sp4ProviderOutcome):
        raise Sp4CanonicalMunicipalError(
            "Municipal official interpreter did not return a reviewed fiscal result"
        )
    return value


def build_cajamar_reviewed_ports(
    *, authority: Sp4BridgeAuthority,
    transport: CajamarGeiswebHomologationTransport,
    build_signed_operation: Callable[
        [NfseAuthorizationRequest, Sp4OriginalRps, str], CajamarPreparedNfse
    ],
    verify_signed_rps_identity: Callable[[Sp4OriginalRps, bytes], None],
    interpret_official_result: Callable[
        [CajamarGeiswebResult, NfseAuthorizationRequest, Sp4OriginalRps],
        Sp4ProviderOutcome,
    ] = interpret_cajamar_geisweb_result,
) -> Sp4ReviewedMunicipalPorts:
    if not isinstance(transport, CajamarGeiswebHomologationTransport) or not all(
        callable(x) for x in (
            build_signed_operation, verify_signed_rps_identity,
            interpret_official_result,
        )
    ):
        raise Sp4CanonicalMunicipalError("Cajamar official contract adapters unavailable")

    def invoke(
        req: NfseAuthorizationRequest, original: Sp4OriginalRps, method: str,
    ) -> Sp4ProviderOutcome:
        # GeisWeb20 accepts one service per RPS and one invoice per lot.
        # Reject incompatible canonical documents before opening Vault/HTTP.
        if (
            len(req.document.services) != 1
            or not original.rps_number.isascii()
            or not original.rps_number.isdecimal()
            or not 1 <= len(original.rps_number) <= 8
            or int(original.rps_number) < 1
        ):
            raise Sp4CanonicalMunicipalError(
                "Cajamar GeisWeb requires one service and 1-8 digit original RPS"
            )
        operation = _validate_prepared_link(
            req, original, build_signed_operation(req, original, method),
            expected_type=CajamarPreparedNfse, expected_method=method,
        )
        # GeisWeb ConsultaLoteRps is keyed by NumeroLote (10 chars),
        # NOT the invoice number. Without a durable lot ID a lost POST
        # cannot be reconciled and must not be retransmitted.
        if (
            original.municipal_batch_id is None
            or len(original.municipal_batch_id) > 10
        ):
            raise Sp4CanonicalMunicipalError(
                "Cajamar requires persisted original GeisWeb lot ID"
            )
        try:
            root = etree.fromstring(
                operation.signed_request_xml,
                parser=etree.XMLParser(
                    no_network=True, resolve_entities=False, load_dtd=False,
                ),
            )
        except etree.XMLSyntaxError:
            raise Sp4CanonicalMunicipalError("Cajamar signed lot XML malformed") from None
        lots = [
            child for child in root.iter()
            if etree.QName(child).localname == "NumeroLote"
        ]
        if (
            etree.QName(root).localname != method
            or bool(getattr(root.getroottree().docinfo, "doctype", ""))
            or len(lots) != 1
            or (lots[0].text or "").strip() != original.municipal_batch_id
        ):
            raise Sp4CanonicalMunicipalError(
                "Cajamar lot XML differs from persisted original batch"
            )
        verify_signed_rps_identity(original, operation.signed_request_xml)
        receipt = transport.invoke(operation)
        return _verified_outcome(interpret_official_result(receipt, req, original))

    return authority.wrap(
        lambda req, original: invoke(req, original, "EnviaLoteRps"),
        # A pending issuance has a durable original LOT/RPS, not yet an
        # NFS-e number. ConsultaNfse requires an already assigned invoice
        # identifier and cannot reconcile an ambiguous emission POST.
        lambda req, original: invoke(req, original, "ConsultaLoteRps"),
    )


def build_cajamar_verified_cancellation_port(
    *,
    transport: CajamarGeiswebHomologationTransport,
    sign_cancel: Callable[[ExecutionScope, Cnpj, bytes], bytes],
    validate_signed_cancel: Callable[[ExecutionScope, Cnpj, bytes], None],
    verify_official_cancel: Callable[[ExecutionScope, Cnpj, bytes], None],
) -> Callable[
    [NfseAuthorizationRequest, Sp4OriginalRps, Sp4VerifiedInvoice],
    CajamarCancellationDecision,
]:
    """Review and invoke one original-issuer CancelaNfse, never re-number RPS.

    This is an opt-in trusted fiscal transport port; the application's
    CANCEL_REQUESTED transaction and human Portal review happen first.
    """
    if not isinstance(transport, CajamarGeiswebHomologationTransport) or not all(
        callable(port) for port in (
            sign_cancel, validate_signed_cancel, verify_official_cancel,
        )
    ):
        raise Sp4CanonicalMunicipalError("Verified Cajamar cancellation ports required")

    def submit(
        req: NfseAuthorizationRequest,
        original: Sp4OriginalRps,
        issued: Sp4VerifiedInvoice,
    ) -> CajamarCancellationDecision:
        if (
            not isinstance(req, NfseAuthorizationRequest)
            or not isinstance(original, Sp4OriginalRps)
            or not isinstance(issued, Sp4VerifiedInvoice)
            or req.document.scope.identity_partition_key
            != original.scope.identity_partition_key
            or req.document.issuer.cnpj != original.issuer_cnpj
            or original.document_id != req.document.document_id
            or original.request_fingerprint != req.request_fingerprint
            or original.issuer_ibge != "3509205"
        ):
            raise Sp4CanonicalMunicipalError(
                "Cancellation cannot change original Cajamar issuer or RPS"
            )
        prepared = prepare_cajamar_cancel(
            source=original, issued=issued,
            regime=req.document.issuer.tax_regime, human_approved=True,
            sign_document=lambda raw: sign_cancel(
                original.scope, original.issuer_cnpj, raw,
            ),
            validate_signed_request=lambda signed: validate_signed_cancel(
                original.scope, original.issuer_cnpj, signed,
            ),
        )
        receipt = transport.invoke(prepared)
        return interpret_cajamar_cancel_response(
            receipt=receipt, source=original, issued=issued,
            verify_official_response=lambda official: verify_official_cancel(
                original.scope, original.issuer_cnpj, official,
            ),
        )

    return submit


def build_osasco_reviewed_ports(
    *, authority: Sp4BridgeAuthority,
    transport: OsascoRtcHomologationTransport,
    build_wcf_operation: Callable[
        [NfseAuthorizationRequest, Sp4OriginalRps, str], OsascoPreparedOperation
    ],
    verify_wcf_rps_identity: Callable[[Sp4OriginalRps, bytes], None],
    interpret_official_result: Callable[
        [OsascoOperationReceipt, NfseAuthorizationRequest, Sp4OriginalRps],
        Sp4ProviderOutcome,
    ],
) -> Sp4ReviewedMunicipalPorts:
    if not isinstance(transport, OsascoRtcHomologationTransport) or not all(
        callable(x) for x in (
            build_wcf_operation, verify_wcf_rps_identity,
            interpret_official_result,
        )
    ):
        raise Sp4CanonicalMunicipalError("Osasco RTC provider adapter incomplete")

    def invoke(
        req: NfseAuthorizationRequest, original: Sp4OriginalRps, method: str,
    ) -> Sp4ProviderOutcome:
        prepared = (
            build_osasco_original_note_query(
                original=original, regime=req.document.issuer.tax_regime,
            ) if method == "ConsultarNotaCompleta"
            else build_wcf_operation(req, original, method)
        )
        operation = _validate_prepared_link(
            req, original, prepared,
            expected_type=OsascoPreparedOperation, expected_method=method,
        )
        # The April 2026 municipal v2.1 manual includes RTC_ConsultarNFE
        # and ConsultarNotaCompleta. The latter retrieves complete invoice
        # XML by the original NumeroReciboUnico without a second issuance.
        if (
            not original.rps_number.isascii()
            or not original.rps_number.isdecimal()
            or not 1 <= len(original.rps_number) <= 20
        ):
            raise Sp4CanonicalMunicipalError("Osasco original receipt number invalid")
        field_name = (
            "NumeroRecibo" if method == "RTC_EmitirNFE"
            else "NumeroReciboUnico"
        )
        namespace = (
            "http://schemas.datacontract.org/2004/07/"
            + "Eissnfe.Dominio.DataTransferObject.Prestador"
            if method == "RTC_EmitirNFE"
            else "http://schemas.datacontract.org/2004/07/"
            + "Eissnfe.Negocio.WebServices.Mensagem"
        )
        try:
            root = etree.fromstring(
                operation.request_xml,
                parser=etree.XMLParser(
                    no_network=True, resolve_entities=False, load_dtd=False,
                ),
            )
        except etree.XMLSyntaxError:
            raise Sp4CanonicalMunicipalError("Osasco fiscal request is malformed") from None
        found = root.findall(f".//{{{namespace}}}{field_name}")
        if (
            len(found) != 1
            or not found[0].text
            or not found[0].text.isascii()
            or not found[0].text.isdecimal()
            or int(found[0].text) != int(original.rps_number)
            or bool(getattr(root.getroottree().docinfo, "doctype", ""))
        ):
            raise Sp4CanonicalMunicipalError(
                "Osasco requested receipt differs from durable original RPS"
            )
        verify_wcf_rps_identity(original, operation.request_xml)
        receipt = transport.invoke(operation)
        if not isinstance(receipt, OsascoOperationReceipt) or receipt.method != method:
            raise Sp4CanonicalMunicipalError(
                "Osasco returned an unexpected official operation"
            )
        if method == "RTC_EmitirNFE":
            # Even a synchronous NotaFiscalGerada with Erro=false is only a
            # provider reference until read-only ConsultarNotaCompleta
            # reconciles the original receipt and official invoice XML.
            return Sp4ProviderOutcome(
                status=AuthorizationStatus.PENDING,
                provider_request_id=(
                    receipt.note_reference.number
                    if receipt.note_reference is not None else None
                ),
            )
        if not receipt.response_xml or receipt.fiscal_error:
            return Sp4ProviderOutcome(status=AuthorizationStatus.PENDING)
        return _verified_outcome(interpret_official_result(receipt, req, original))

    return authority.wrap(
        lambda req, original: invoke(req, original, "RTC_EmitirNFE"),
        lambda req, original: invoke(req, original, "ConsultarNotaCompleta"),
    )
