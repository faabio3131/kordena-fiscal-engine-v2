"""Canonical runtime composition with explicit fail-closed fiscal provider boundaries.

The handlers are always registered. Provider credentials and official transports
must be provisioned independently; this module never simulates authorization.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from kordena_fiscal.application.service import FiscalApplicationService
from kordena_fiscal.archive import RetentionPolicyMetadata
from kordena_fiscal.domain import FiscalValidationError
from kordena_fiscal.gateway import FiscalGatewayClient
from kordena_fiscal.gateway.nfe_sp_homologation import SefazSpHomologationGateway
from kordena_fiscal.gateway.nfe_sp_operations_homologation import (
    SefazSpHomologationOperationsGateway,
)
from kordena_fiscal.operations import FiscalOperationsClient
from kordena_fiscal.vault.encrypted_a1 import EncryptedA1Vault

from .fiscal_runtime import FiscalOperationHandler
from .provider_operation_wiring import build_provider_operation_handlers


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


def build_runtime_fiscal_handler_factory(
    *,
    operations_gateway: Any | None = None,
    authorization_gateway: Any | None = None,
    certificate_vault: EncryptedA1Vault | None = None,
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
    operations = FiscalOperationsClient(selected_operations or UnprovisionedFiscalGateway())
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
    retention = RetentionPolicyMetadata(
        policy_id="nfcore-fiscal-archive", policy_version=1
    )

    def factory(
        application: FiscalApplicationService,
    ) -> Mapping[str, FiscalOperationHandler]:
        handlers = build_provider_operation_handlers(
            operations,
            application=application,
            prepared_xml_gateway=authorization,
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
