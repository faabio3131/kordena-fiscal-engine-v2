"""Osasco RTC WCF plugged into the existing canonical SP4 fiscal runtime.

All fiscal authorities and credentials are injected through reviewed ports;
no second database, sequence, browser credential or provider registry.
This does not activate a municipal WSDL in the executable entrypoint.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from kordena_fiscal.application.service import FiscalApplicationService
from kordena_fiscal.gateway.osasco_rtc_homologation import (
    OsascoOperationReceipt,
    OsascoPreparedOperation,
    OsascoRtcHomologationTransport,
)
from kordena_fiscal.gateway.sp4_municipal_canonical import (
    Sp4OriginalRps,
    Sp4ProviderOutcome,
    Sp4VerifiedInvoice,
)
from kordena_fiscal.issuance.nfe_nfse import NfseAuthorizationRequest

from .sp4_municipal_canonical_composition import Sp4ReviewedMunicipalPorts
from .sp4_municipal_provider_bridges import (
    Sp4BridgeAuthority,
    build_osasco_reviewed_ports,
)


@dataclass(frozen=True, slots=True)
class OsascoTrustedRuntimePorts:
    """Explicit reviewed WCF dependencies, with no hardcoded secret or policy."""

    transport: OsascoRtcHomologationTransport
    build_wcf_operation: Callable[
        [NfseAuthorizationRequest, Sp4OriginalRps, str], OsascoPreparedOperation
    ]
    verify_wcf_rps_identity: Callable[[Sp4OriginalRps, bytes], None]
    fiscal_issuer_policy: Callable[[NfseAuthorizationRequest], None]
    validate_prepared_rps: Callable[[Sp4OriginalRps], None]
    verify_official_invoice_xml: Callable[[Sp4VerifiedInvoice], None]
    interpret_official_result: Callable[
        [OsascoOperationReceipt, NfseAuthorizationRequest, Sp4OriginalRps],
        Sp4ProviderOutcome,
    ]

    def __post_init__(self) -> None:
        if not isinstance(self.transport, OsascoRtcHomologationTransport) or not all(
            callable(port) for port in (
                self.build_wcf_operation,
                self.verify_wcf_rps_identity,
                self.fiscal_issuer_policy,
                self.validate_prepared_rps,
                self.verify_official_invoice_xml,
                self.interpret_official_result,
            )
        ):
            raise ValueError("Osasco requires complete reviewed municipal fiscal ports")

    def attach(self, application: FiscalApplicationService) -> Sp4ReviewedMunicipalPorts:
        """The same application's loader is the ONLY original-RPS authority."""
        authority = Sp4BridgeAuthority(
            load_original_rps=lambda scope, document_id: application.load_sp4_original_rps(
                scope, document_id,
            ),
            fiscal_issuer_policy=self.fiscal_issuer_policy,
            validate_prepared_rps=self.validate_prepared_rps,
            verify_official_invoice_xml=self.verify_official_invoice_xml,
        )
        return build_osasco_reviewed_ports(
            authority=authority,
            transport=self.transport,
            build_wcf_operation=self.build_wcf_operation,
            verify_wcf_rps_identity=self.verify_wcf_rps_identity,
            interpret_official_result=self.interpret_official_result,
        )
