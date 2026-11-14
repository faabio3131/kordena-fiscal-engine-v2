"""Reviewed Barueri PMB004 connected to the shared NFCore fiscal application.

Barueri accepts asynchronous fixed-width remittances, not an immediately
authorized NFS-e. The canonical application owns RPS numbering, durable state,
protocol archive and recovery. This adapter introduces no second persistence.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from kordena_fiscal.application.service import FiscalApplicationService
from kordena_fiscal.domain import (
    BrazilianJurisdiction,
    ExecutionScope,
    FiscalDocumentKind,
    FiscalValidationError,
)
from kordena_fiscal.gateway.barueri_official_invoice_xml import (
    retrieve_barueri_original_invoice_xml,
)
from kordena_fiscal.gateway.barueri_official_return_file import (
    BarueriConvertedNfseEvidence,
    parse_barueri_official_return_file,
)
from kordena_fiscal.gateway.barueri_pmb004_homologation import (
    BARUERI_PMB004_PROVIDER,
    BarueriPmb004HomologationTransport,
    BarueriReceipt,
    BarueriRpsBatch,
)
from kordena_fiscal.gateway.sp4_municipal_canonical import (
    Sp4OriginalRps,
    Sp4ProviderOutcome,
    Sp4VerifiedInvoice,
)
from kordena_fiscal.issuance.nfe_nfse import NfseAuthorizationRequest
from kordena_fiscal.vault.encrypted_a1 import EncryptedA1Vault

from .sp4_municipal_canonical_composition import Sp4ReviewedMunicipalPorts
from .sp4_municipal_provider_bridges import (
    Sp4BridgeAuthority,
    build_barueri_reviewed_ports,
)


@dataclass(frozen=True, slots=True)
class BarueriTrustedRuntimePorts:
    """Complete operator-reviewed PMB004 dependencies, with canonical identity."""

    transport: BarueriPmb004HomologationTransport
    build_remittance: Callable[
        [NfseAuthorizationRequest, Sp4OriginalRps], BarueriRpsBatch
    ]
    verify_fixed_width_rps_identity: Callable[
        [Sp4OriginalRps, BarueriRpsBatch], None
    ]
    fiscal_issuer_policy: Callable[[NfseAuthorizationRequest], None]
    validate_prepared_rps: Callable[[Sp4OriginalRps], None]
    verify_official_invoice_xml: Callable[[Sp4VerifiedInvoice], None]
    interpret_official_result: Callable[
        [BarueriReceipt, NfseAuthorizationRequest, Sp4OriginalRps],
        Sp4ProviderOutcome,
    ]
    retrieve_official_invoice_xml: Callable[
        [BarueriConvertedNfseEvidence], bytes
    ] = retrieve_barueri_original_invoice_xml
    validate_return_file: Callable[
        [BarueriRpsBatch, BarueriReceipt], BarueriConvertedNfseEvidence
    ] = parse_barueri_official_return_file

    def __post_init__(self) -> None:
        if not isinstance(self.transport, BarueriPmb004HomologationTransport):
            raise FiscalValidationError("Barueri requires approved municipal transport")
        if not all(callable(field) for field in (
            self.build_remittance, self.verify_fixed_width_rps_identity,
            self.fiscal_issuer_policy, self.validate_prepared_rps,
            self.verify_official_invoice_xml, self.interpret_official_result,
            self.retrieve_official_invoice_xml, self.validate_return_file,
        )):
            raise FiscalValidationError("Barueri fiscal review ports are incomplete")

    def attach(self, application: FiscalApplicationService) -> Sp4ReviewedMunicipalPorts:
        if not isinstance(application, FiscalApplicationService):
            raise FiscalValidationError("Barueri needs the canonical fiscal application")
        authority = Sp4BridgeAuthority(
            load_original_rps=lambda scope, document_id: application.load_sp4_original_rps(
                scope, document_id,
            ),
            fiscal_issuer_policy=self.fiscal_issuer_policy,
            validate_prepared_rps=self.validate_prepared_rps,
            verify_official_invoice_xml=self.verify_official_invoice_xml,
        )
        return build_barueri_reviewed_ports(
            authority=authority,
            transport=self.transport,
            build_remittance=self.build_remittance,
            verify_fixed_width_rps_identity=self.verify_fixed_width_rps_identity,
            load_approved_remittance_protocol=application.load_barueri_remittance_protocol,
            interpret_official_result=self.interpret_official_result,
            validate_return_file=self.validate_return_file,
            retrieve_official_invoice_xml=self.retrieve_official_invoice_xml,
            load_original_submission_date=application.load_barueri_submission_date,
        )


def build_barueri_trusted_transport(
    *,
    application: FiscalApplicationService,
    vault: EncryptedA1Vault,
    validate_pmb004: Callable[[bytes], None],
) -> BarueriPmb004HomologationTransport:
    """Use the same tenant-scoped provider binding and A1 Vault as the Portal."""
    if (
        not isinstance(application, FiscalApplicationService)
        or not isinstance(vault, EncryptedA1Vault)
        or not callable(validate_pmb004)
    ):
        raise FiscalValidationError("Barueri requires canonical A1 and PMB004 validator")

    class CanonicalResolver:
        def resolve_provider_id(
            self, *, scope: ExecutionScope,
            document_kind: FiscalDocumentKind,
            jurisdiction: BrazilianJurisdiction,
            operation: str,
        ) -> str:
            return application.resolve_configured_provider_id(
                scope=scope,
                document_kind=document_kind,
                jurisdiction=jurisdiction,
                operation=operation,
            )

    return BarueriPmb004HomologationTransport(
        provider_resolver=CanonicalResolver(),
        resolve_certificate=lambda scope, cnpj: vault.resolve(
            scope=scope, issuer_cnpj=cnpj,
        ),
        validate_pmb004=validate_pmb004,
    )
