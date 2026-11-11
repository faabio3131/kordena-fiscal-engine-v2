"""Canonical runtime composition with explicit fail-closed fiscal provider boundaries.

The handlers are always registered. Provider credentials and official transports
must be provisioned independently; this module never simulates authorization.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from kordena_fiscal.application.service import FiscalApplicationService
from kordena_fiscal.archive import RetentionPolicyMetadata
from kordena_fiscal.control_plane.commercial import ConfiguredFiscalOperation
from kordena_fiscal.control_plane.service import ControlPlaneNotFoundError
from kordena_fiscal.domain import (
    BrazilianJurisdiction,
    ExecutionScope,
    FiscalDocumentKind,
    FiscalEnvironment,
    FiscalValidationError,
)
from kordena_fiscal.gateway import AuthorizationRequest, FiscalGatewayClient
from kordena_fiscal.gateway.nfe_sp_homologation import (
    MG_NFE_HOMOLOGATION_PROVIDER_ID,
    HomologationAuthorizationTarget,
    SefazSpHomologationGateway,
    build_mg_nfe_homologation_gateway,
)
from kordena_fiscal.gateway.nfe_sp_operations_homologation import (
    SefazHomologationOperationsGateway,
    SefazSpHomologationOperationsGateway,
)
from kordena_fiscal.gateway.nfse_nacional_homologation import (
    NACIONAL_HOMOLOGATION_PROVIDER_ID,
    NfseNacionalHomologationGateway,
)
from kordena_fiscal.issuance import (
    NfseAuthorizationRequest,
    NfseAuthorizationResult,
    NfseGatewayClient,
)
from kordena_fiscal.operations import (
    CancellationRequest,
    CancellationResult,
    FiscalOperationsClient,
    FiscalOperationsGateway,
    FiscalQueryRequest,
    FiscalQueryResult,
    InutilizationRequest,
    InutilizationResult,
)
from kordena_fiscal.vault import EphemeralCertificateMaterial
from kordena_fiscal.vault.encrypted_a1 import EncryptedA1Vault
from kordena_fiscal.xml import NfeAccessKey

from .fiscal_runtime import FiscalOperationHandler
from .provider_issuance_handler import PreparedXmlGatewaySelector
from .provider_operation_wiring import build_provider_operation_handlers


def fiscal_external_dependency_snapshot(
    *, certificate_vault: EncryptedA1Vault | None,
    trusted_signed_dps_builder: Callable[
        [NfseAuthorizationRequest, EphemeralCertificateMaterial], bytes
    ] | None = None,
    nfse_preaudit: Callable[[NfseAuthorizationRequest], None] | None = None,
) -> dict[str, bool]:
    """Configuration status only; never assert taxpayer-specific issuance readiness.

    A configured Vault is not proof that a tenant has uploaded a valid certificate.
    Both SP NF-e and National NFS-e require a trustworthy signed-document
    preparation boundary; until that is provisioned, external execution is NOT ready.
    """
    vault_ready = isinstance(certificate_vault, EncryptedA1Vault)
    nfe_transport_ready = vault_ready
    nfse_transport_ready = (
        vault_ready and callable(trusted_signed_dps_builder) and callable(nfse_preaudit)
    )
    # Python signer and A1 mTLS are imported at composition time, but a signing
    # capability is only configured when an A1 Vault exists.
    signer_ready = vault_ready
    return {
        "fiscal_provider_transport_real_configured": nfe_transport_ready,
        "fiscal_external_secret_client_configured": vault_ready,
        "fiscal_signer_configured": signer_ready,
        "fiscal_runtime_external_execution_ready": (
            nfe_transport_ready and nfse_transport_ready and signer_ready
        ),
    }


class UnprovisionedFiscalGateway:
    """Concrete deny-by-default boundary until a tenant-scoped official adapter is bound."""

    @staticmethod
    def _unavailable() -> None:
        raise FiscalValidationError(
            "Certificado A1 não cadastrado para o CNPJ emitente ou provedor fiscal "
            "de homologação não configurado"
        )

    def authorize(self, request: Any) -> Any:
        self._unavailable()

    def query(self, request: Any) -> Any:
        self._unavailable()

    def cancel(self, request: Any) -> Any:
        self._unavailable()

    def inutilize(self, request: Any) -> Any:
        self._unavailable()


def _require_mg_binding(
    application: FiscalApplicationService, scope: ExecutionScope,
    access_key: NfeAccessKey, operation: ConfiguredFiscalOperation,
) -> None:
    label = {
        ConfiguredFiscalOperation.QUERY: "consulta MG",
        ConfiguredFiscalOperation.CANCEL: "cancelamento MG",
    }.get(operation, "autorização MG")
    if scope.environment is not FiscalEnvironment.HOMOLOGATION:
        raise FiscalValidationError(f"Operação de {label} disponível apenas em homologação")
    if access_key.model.value != 55:
        raise FiscalValidationError(f"Operação de {label} disponível apenas para NF-e modelo 55")
    try:
        provider_id = application.resolve_configured_provider_id(
            scope=scope,
            document_kind=FiscalDocumentKind.NFE,
            jurisdiction=BrazilianJurisdiction("MG"),
            operation=operation.value,
        )
    except ControlPlaneNotFoundError as exc:
        raise FiscalValidationError(f"Vínculo fiscal de {label} indisponível") from exc
    if provider_id != MG_NFE_HOMOLOGATION_PROVIDER_ID:
        raise FiscalValidationError(f"Provedor do vínculo de {label} incompatível")


class _GovernedNationalNfseGateway:
    """Enforce a durable unit binding and fiscal audit before accessing A1."""

    def __init__(
        self,
        *,
        application: FiscalApplicationService,
        preaudit: Callable[[NfseAuthorizationRequest], None],
        gateway: NfseNacionalHomologationGateway,
    ) -> None:
        self._application = application
        self._preaudit = preaudit
        self._gateway = gateway

    def authorize(self, request: NfseAuthorizationRequest) -> NfseAuthorizationResult:
        document = request.document
        scope = document.scope
        jurisdiction = document.issuer.address.jurisdiction
        if (
            scope.environment is not FiscalEnvironment.HOMOLOGATION
            or scope.host_namespace is None
            or jurisdiction.municipality_ibge_code is None
        ):
            raise FiscalValidationError("NFS-e Nacional exige escopo de homologacao e municipio")
        try:
            provider_id = self._application.resolve_configured_provider_id(
                scope=scope,
                document_kind=FiscalDocumentKind.NFSE,
                jurisdiction=jurisdiction,
                operation=ConfiguredFiscalOperation.AUTHORIZE.value,
            )
        except ControlPlaneNotFoundError as exc:
            raise FiscalValidationError("Vinculo fiscal NFS-e Nacional indisponivel") from exc
        if provider_id != NACIONAL_HOMOLOGATION_PROVIDER_ID:
            raise FiscalValidationError("Provedor do vinculo NFS-e Nacional incompativel")
        self._preaudit(request)
        return self._gateway.authorize(request)


class _GovernedMgQueryGateway:
    def __init__(
        self,
        *,
        legacy: FiscalOperationsGateway,
        mg: FiscalOperationsGateway,
        application: FiscalApplicationService,
    ) -> None:
        self._legacy = legacy
        self._mg = mg
        self._application = application

    def query(self, request: FiscalQueryRequest) -> FiscalQueryResult:
        if request.access_key.value[:2] != "31":
            return self._legacy.query(request)
        _require_mg_binding(
            self._application, request.scope, request.access_key, ConfiguredFiscalOperation.QUERY
        )
        return self._mg.query(request)

    def cancel(self, request: CancellationRequest) -> CancellationResult:
        if request.access_key.value[:2] != "31":
            return self._legacy.cancel(request)
        _require_mg_binding(
            self._application,
            scope=request.scope,
            access_key=request.access_key,
            operation=ConfiguredFiscalOperation.CANCEL,
        )
        return self._mg.cancel(request)

    def inutilize(self, request: InutilizationRequest) -> InutilizationResult:
        # Inutilization has no issuer/state on the command. Do not infer MG
        # from tenant or unit, or silently route all clients through MG.
        # A trusted fiscal profile/state resolver is required before cutover.
        return self._legacy.inutilize(request)


def build_runtime_fiscal_handler_factory(
    *,
    operations_gateway: Any | None = None,
    authorization_gateway: Any | None = None,
    certificate_vault: EncryptedA1Vault | None = None,
    nfse_gateway: NfseGatewayClient | None = None,
    trusted_signed_dps_builder: Callable[
        [NfseAuthorizationRequest, EphemeralCertificateMaterial], bytes
    ] | None = None,
    nfse_preaudit: Callable[[NfseAuthorizationRequest], None] | None = None,
) -> Any:
    """Register all four canonical operations without granting fiscal readiness.

    Real official adapters can be supplied by the deployment composition.
    The default boundary is intentionally non-transmitting.
    """
    selected_operations = operations_gateway
    if selected_operations is None and certificate_vault is not None:
        selected_operations = SefazSpHomologationOperationsGateway(
            resolve_certificate=lambda scope, cnpj: certificate_vault.resolve(
                scope=scope, issuer_cnpj=cnpj
            )
        )
    selected_authorization = authorization_gateway
    if selected_authorization is None and certificate_vault is not None:
        selected_authorization = SefazSpHomologationGateway(
            resolve_certificate=lambda scope, cnpj: certificate_vault.resolve(
                scope=scope, issuer_cnpj=cnpj
            )
        )
    authorization = FiscalGatewayClient(
        selected_authorization or UnprovisionedFiscalGateway()
    )
    # National NFS-e requires an approved, trusted DPS preparation and XMLDSig
    # port; never derive its contents from browser payloads or send unsigned XML.
    if nfse_gateway is not None and trusted_signed_dps_builder is not None:
        raise ValueError("configure either an NFS-e gateway or a trusted DPS builder")
    if trusted_signed_dps_builder is not None and not callable(nfse_preaudit):
        raise ValueError("NFS-e signed DPS composition requires fiscal pre-audit")
    national_nfse = None
    if certificate_vault is not None and trusted_signed_dps_builder is not None:
        national_nfse = NfseNacionalHomologationGateway(
            resolve_certificate=lambda scope, cnpj: certificate_vault.resolve(
                scope=scope, issuer_cnpj=cnpj
            ),
            build_signed_dps=trusted_signed_dps_builder,
        )
    retention = RetentionPolicyMetadata(
        policy_id="nfcore-fiscal-archive", policy_version=1
    )

    def factory(
        application: FiscalApplicationService,
    ) -> Mapping[str, FiscalOperationHandler]:
        gateway = selected_operations or UnprovisionedFiscalGateway()
        if operations_gateway is None and certificate_vault is not None:
            vault = certificate_vault

            def resolve_mg_certificate(
                scope: ExecutionScope, cnpj: str,
            ) -> EphemeralCertificateMaterial:
                return vault.resolve(scope=scope, issuer_cnpj=cnpj)

            gateway = _GovernedMgQueryGateway(
                legacy=gateway,
                mg=SefazHomologationOperationsGateway(
                    resolve_certificate=resolve_mg_certificate,
                    target=HomologationAuthorizationTarget.MG_NFE,
                ),
                application=application,
            )
        selector: PreparedXmlGatewaySelector | None = None
        if authorization_gateway is None and certificate_vault is not None:
            authorization_vault = certificate_vault

            def resolve_authorization_certificate(
                scope: ExecutionScope, cnpj: str,
            ) -> EphemeralCertificateMaterial:
                return authorization_vault.resolve(scope=scope, issuer_cnpj=cnpj)

            mg_authorization = FiscalGatewayClient(build_mg_nfe_homologation_gateway(
                resolve_certificate=resolve_authorization_certificate,
            ))

            def select_xml_gateway(request: AuthorizationRequest) -> FiscalGatewayClient:
                if request.access_key.value[:2] != "31":
                    return authorization
                _require_mg_binding(
                    application, request.scope, request.access_key,
                    ConfiguredFiscalOperation.AUTHORIZE,
                )
                return mg_authorization

            selector = select_xml_gateway
        selected_nfse = nfse_gateway
        if national_nfse is not None and nfse_preaudit is not None:
            selected_nfse = NfseGatewayClient(_GovernedNationalNfseGateway(
                application=application,
                preaudit=nfse_preaudit,
                gateway=national_nfse,
            ))
        handlers = build_provider_operation_handlers(
            FiscalOperationsClient(gateway),
            application=application,
            prepared_xml_gateway=authorization,
            select_xml_gateway=selector,
            prepared_nfse_gateway=selected_nfse,
            archive_retention=retention,
        )
        required = {
            "issueFiscalDocument",
            "queryFiscalDocument",
            "cancelFiscalDocument",
            "reconcileFiscalOperation",
        }
        if not required.issubset(handlers):
            raise RuntimeError("canonical fiscal operation composition is incomplete")
        return handlers

    return factory
