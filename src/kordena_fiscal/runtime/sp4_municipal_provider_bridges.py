"""Distinct municipal transports mapped into the governed SP4 canonical lifecycle.

Each bridge requires a trusted RPS/DPS builder and a source-identity validator;
it does not accept raw front-end XML. The municipality-specific interpreter
cannot confer final tax authority: Sp4MunicipalCanonicalGateway independently
checks original RPS, fiscal amount and signed official XML provenance.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar

from kordena_fiscal.domain import ExecutionScope
from kordena_fiscal.gateway.barueri_pmb004_homologation import (
    BarueriPmb004HomologationTransport,
    BarueriReceipt,
    BarueriRpsBatch,
)
from kordena_fiscal.gateway.cajamar_geisweb_homologation import (
    CajamarGeiswebHomologationTransport,
    CajamarGeiswebResult,
    CajamarPreparedNfse,
)
from kordena_fiscal.gateway.jundiai_giss_homologation import (
    JundiaiGissHomologationTransport,
    JundiaiGissReceipt,
    JundiaiSignedOperation,
)
from kordena_fiscal.gateway.osasco_rtc_homologation import (
    OsascoOperationReceipt,
    OsascoPreparedOperation,
    OsascoRtcHomologationTransport,
)
from kordena_fiscal.gateway.sp4_municipal_canonical import (
    Sp4CanonicalMunicipalError,
    Sp4OriginalRps,
    Sp4ProviderOutcome,
    Sp4VerifiedInvoice,
)
from kordena_fiscal.issuance.nfe_nfse import NfseAuthorizationRequest

from .sp4_municipal_canonical_composition import Sp4ReviewedMunicipalPorts

P = TypeVar("P")


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
    ],
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
        operation = _validate_prepared_link(
            req, original, build_signed_operation(req, original, method),
            expected_type=CajamarPreparedNfse, expected_method=method,
        )
        verify_signed_rps_identity(original, operation.signed_request_xml)
        receipt = transport.invoke(operation)
        return _verified_outcome(interpret_official_result(receipt, req, original))

    return authority.wrap(
        lambda req, original: invoke(req, original, "EnviaLoteRps"),
        lambda req, original: invoke(req, original, "ConsultaNfse"),
    )


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
        operation = _validate_prepared_link(
            req, original, build_wcf_operation(req, original, method),
            expected_type=OsascoPreparedOperation, expected_method=method,
        )
        verify_wcf_rps_identity(original, operation.request_xml)
        receipt = transport.invoke(operation)
        return _verified_outcome(interpret_official_result(receipt, req, original))

    return authority.wrap(
        lambda req, original: invoke(req, original, "RTC_EmitirNFE"),
        lambda req, original: invoke(req, original, "RTC_ConsultarNFE"),
    )


def build_jundiai_reviewed_ports(
    *, authority: Sp4BridgeAuthority,
    transport: JundiaiGissHomologationTransport,
    build_signed_operation: Callable[
        [NfseAuthorizationRequest, Sp4OriginalRps, str], JundiaiSignedOperation
    ],
    verify_signed_rps_identity: Callable[[Sp4OriginalRps, bytes], None],
    interpret_official_result: Callable[
        [JundiaiGissReceipt, NfseAuthorizationRequest, Sp4OriginalRps],
        Sp4ProviderOutcome,
    ],
) -> Sp4ReviewedMunicipalPorts:
    if not isinstance(transport, JundiaiGissHomologationTransport) or not all(
        callable(x) for x in (
            build_signed_operation, verify_signed_rps_identity,
            interpret_official_result,
        )
    ):
        raise Sp4CanonicalMunicipalError("Jundiai Giss provider adapter incomplete")

    def invoke(
        req: NfseAuthorizationRequest, original: Sp4OriginalRps, method: str,
    ) -> Sp4ProviderOutcome:
        operation = _validate_prepared_link(
            req, original, build_signed_operation(req, original, method),
            expected_type=JundiaiSignedOperation, expected_method=method,
        )
        verify_signed_rps_identity(original, operation.signed_xml)
        receipt = transport.invoke(operation)
        return _verified_outcome(interpret_official_result(receipt, req, original))

    return authority.wrap(
        lambda req, original: invoke(req, original, "RecepcionarLoteRps"),
        lambda req, original: invoke(req, original, "ConsultarNfsePorRps"),
    )


def build_barueri_reviewed_ports(
    *, authority: Sp4BridgeAuthority,
    transport: BarueriPmb004HomologationTransport,
    build_remittance: Callable[
        [NfseAuthorizationRequest, Sp4OriginalRps], BarueriRpsBatch
    ],
    verify_fixed_width_rps_identity: Callable[[Sp4OriginalRps, BarueriRpsBatch], None],
    load_approved_remittance_protocol: Callable[[ExecutionScope, str], str | None],
    interpret_official_result: Callable[
        [BarueriReceipt, NfseAuthorizationRequest, Sp4OriginalRps],
        Sp4ProviderOutcome,
    ],
) -> Sp4ReviewedMunicipalPorts:
    if not isinstance(transport, BarueriPmb004HomologationTransport) or not all(
        callable(x) for x in (
            build_remittance, verify_fixed_width_rps_identity,
            load_approved_remittance_protocol, interpret_official_result,
        )
    ):
        raise Sp4CanonicalMunicipalError("Barueri PMB004 provider adapter incomplete")

    def original_batch(
        req: NfseAuthorizationRequest, original: Sp4OriginalRps,
    ) -> BarueriRpsBatch:
        batch = build_remittance(req, original)
        if not isinstance(batch, BarueriRpsBatch) or (
            batch.scope.identity_partition_key
            != req.document.scope.identity_partition_key
            or batch.issuer_cnpj != original.issuer_cnpj
            or batch.tax_regime != req.document.issuer.tax_regime
            or batch.competence_date != original.competence_date
        ):
            raise Sp4CanonicalMunicipalError("Barueri remittance conflicts with canonical RPS")
        verify_fixed_width_rps_identity(original, batch)
        return batch

    def authorize(
        req: NfseAuthorizationRequest, original: Sp4OriginalRps,
    ) -> Sp4ProviderOutcome:
        batch = original_batch(req, original)
        receipt = transport.submit(batch)
        return _verified_outcome(interpret_official_result(receipt, req, original))

    def query(
        req: NfseAuthorizationRequest, original: Sp4OriginalRps,
    ) -> Sp4ProviderOutcome:
        batch = original_batch(req, original)
        protocol = load_approved_remittance_protocol(
            req.document.scope, req.document.document_id,
        )
        if protocol is None:
            # No protocol is not evidence that an ambiguous POST failed.
            return Sp4ProviderOutcome(status=__import__(
                "kordena_fiscal.gateway.authorization",
                fromlist=["AuthorizationStatus"],
            ).AuthorizationStatus.PENDING)
        if (
            not isinstance(protocol, str)
            or not 1 <= len(protocol) <= 128
            or not protocol.isascii()
            or not protocol.isalnum()
        ):
            raise Sp4CanonicalMunicipalError("Invalid original Barueri protocol")
        status = transport.status(batch=batch, protocol=protocol)
        receipt = status
        if status.return_file_name:
            # Read-only download; never repeat the RPS submission.
            receipt = transport.download(
                batch=batch, file_name=status.return_file_name,
            )
        return _verified_outcome(interpret_official_result(receipt, req, original))

    return authority.wrap(authorize, query)
