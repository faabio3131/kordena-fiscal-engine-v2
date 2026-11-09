"""Opt-in Bling composition on the existing Worker; credentials are provisioned later."""

import hashlib
from collections.abc import Mapping
from pathlib import Path

from kordena_fiscal.application.bling_orders import (
    ISSUE_ORDER,
    PROCESS_ORDER,
    PUBLISH_STATUS,
    BlingOrders,
)
from kordena_fiscal.application.bling_processing import BlingProcessingHandler
from kordena_fiscal.application.bling_status_delivery import BlingStatusPublisher
from kordena_fiscal.application.service import FiscalApplicationService
from kordena_fiscal.connectors.bling_api import (
    fetch_sales_order,
    update_sales_order_status,
    verify_company,
)
from kordena_fiscal.contingency import FiscalOutboxHandler
from kordena_fiscal.contingency.outbox import OutboxClaimSelection
from kordena_fiscal.domain import FiscalEnvironment, HostNamespace, HostScope
from kordena_fiscal.gateway import AuthorizationRequest
from kordena_fiscal.lifecycle import FiscalDocumentState
from kordena_fiscal.persistence.ports import FiscalUnitOfWorkFactory
from kordena_fiscal.vault.encrypted_a1 import EncryptedA1Vault

from .canonical_fiscal_composition import build_runtime_fiscal_handler_factory
from .config import RuntimeConfigurationError
from .fiscal_runtime import CanonicalFiscalOperationPath
from .worker_composition import ScopedWorkerHandlerComposition


def build_bling_orders(
    database: FiscalUnitOfWorkFactory,
    environ: Mapping[str, str],
) -> BlingOrders:
    """Resolve local installation authority without requiring any external credential."""
    names = ("COMPANY_ID", "TENANT_ID", "UNIT_ID", "ENVIRONMENT")
    values = [environ.get("NFCORE_BLING_" + name, "").strip() for name in names]
    if not all(values):
        raise RuntimeConfigurationError("Bling installation configuration is incomplete")
    company, tenant, unit, environment = values
    application = FiscalApplicationService(database)
    try:
        scope = application.resolve_scope(
            HostScope(HostNamespace("bling"), tenant, unit),
            environment=FiscalEnvironment(environment),
            correlation_id="bling-worker",
        )
        orders = BlingOrders(database, scope, company)
    except ValueError:
        raise RuntimeConfigurationError("Bling worker binding is unavailable") from None
    if scope.environment is not FiscalEnvironment.HOMOLOGATION:
        raise RuntimeConfigurationError("Bling fiscal production has not been activated")
    return orders


def build_bling_worker(
    database: FiscalUnitOfWorkFactory,
    environ: Mapping[str, str],
) -> ScopedWorkerHandlerComposition:
    """Claim only the exact installation's Bling operations, never another worker's jobs."""
    orders = build_bling_orders(database, environ)
    application, scope = orders.application, orders.scope
    token_file = environ.get("NFCORE_BLING_ACCESS_TOKEN_FILE", "").strip()
    if not token_file:
        raise RuntimeConfigurationError("Bling OAuth token file is not configured")
    path = Path(token_file)

    def token() -> str:
        # Re-read a mounted secret each time so rotation needs no application restart.
        try:
            with path.open("rb") as stream:
                raw = stream.read(8193)
            value = raw.decode("ascii").strip()
            if len(raw) > 8192 or not value or any(not 33 <= ord(c) <= 126 for c in value):
                raise ValueError("invalid token")
            return value
        except (OSError, ValueError):
            raise RuntimeConfigurationError("Bling OAuth token is unavailable") from None

    token()  # No network access; refuse startup with an unusable secret mount.
    validated_token_digest: str | None = None

    def scoped_token() -> str:
        nonlocal validated_token_digest
        value = token()
        digest = hashlib.sha256(value.encode()).hexdigest()
        if digest != validated_token_digest:
            verify_company(value, orders.company_id)
            validated_token_digest = digest
        return value

    vault = EncryptedA1Vault.from_environ()
    handlers = build_runtime_fiscal_handler_factory(certificate_vault=vault)(application)

    def before_issue(document_id: str) -> None:
        with database() as uow:
            uow.lifecycle.assert_scope(document_id, scope)
            lifecycle = uow.lifecycle.get(document_id)
        if lifecycle is not None and lifecycle.state is not FiscalDocumentState.READY_TO_TRANSMIT:
            return  # Canonical replay/recovery needs no new signing credential.
        if vault is None:
            raise RuntimeConfigurationError("Bling fiscal certificate is not configured")
        request = application.load_prepared_document_authorization(scope, document_id)
        if not isinstance(request, AuthorizationRequest):
            raise RuntimeConfigurationError("Bling requires a prepared NF-e")
        # Validate local provisioning before committing the fiscal transmission claim.
        vault.resolve(scope=scope, issuer_cnpj=request.access_key.value[6:20])

    def validate_binding() -> None:
        current = build_bling_orders(database, environ)
        if current.scope.identity_partition_key != scope.identity_partition_key:
            raise RuntimeConfigurationError("Bling installation binding changed")

    handler = BlingProcessingHandler(
        orders=orders,
        fetch=lambda order_id: fetch_sales_order(order_id, scoped_token()),
        fiscal_path=CanonicalFiscalOperationPath(application, handlers=handlers),
        before_issue=before_issue,
        validate_binding=validate_binding,
    )
    registered: dict[str, FiscalOutboxHandler] = {PROCESS_ORDER: handler}
    status_keys = ("NFCORE_BLING_AUTHORIZED_STATUS_ID", "NFCORE_BLING_REJECTED_STATUS_ID")
    status_values = [environ.get(key, "").strip() for key in status_keys]
    if any(status_values):
        try:
            authorized_status, rejected_status = (int(value) for value in status_values)
            if min(authorized_status, rejected_status) <= 0 or authorized_status == rejected_status:
                raise ValueError("invalid status mapping")
        except ValueError:
            raise RuntimeConfigurationError("Bling result status mapping is incomplete") from None
        registered[PUBLISH_STATUS] = BlingStatusPublisher(
            orders,
            {"authorized": authorized_status, "rejected": rejected_status},
            fetch=lambda order_id: fetch_sales_order(order_id, scoped_token()),
            update=lambda order_id, status: update_sales_order_status(
                order_id, status, scoped_token()
            ),
            validate_binding=validate_binding,
        )
    if vault is not None:
        registered[ISSUE_ORDER] = handler
    return ScopedWorkerHandlerComposition(
        handlers=registered,
        claim_selection=OutboxClaimSelection(
            scope=scope,
            operations=frozenset(registered),
        ),
    )
