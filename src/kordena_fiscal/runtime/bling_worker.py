"""Bling handlers run exclusively on the canonical, scoped fiscal outbox.

Legacy single-company composition and multi-installation composition share
exactly ONE fiscal handler builder. No second fiscal executor or queue exists.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping
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
    """Legacy single-company mode: explicit host binding; never fallback."""
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


def build_scoped_bling_handlers(
    database: FiscalUnitOfWorkFactory,
    orders: BlingOrders,
    *,
    token: Callable[[], str],
    validate_binding: Callable[[], None],
    status_mapping: Mapping[str, int] | None = None,
    vault: EncryptedA1Vault | None = None,
) -> ScopedWorkerHandlerComposition:
    """Shared handler composition for legacy and multi-installation modes.

    The caller must independently derive orders.scope from canonical bindings
    and must supply a provider token from that very installation. The existing
    fiscal operation path and outbox claim mechanism own all state transitions.
    """
    scope = orders.scope
    if scope.environment is not FiscalEnvironment.HOMOLOGATION:
        raise RuntimeConfigurationError("Bling fiscal production has not been activated")
    application = orders.application
    handlers = build_runtime_fiscal_handler_factory(certificate_vault=vault)(application)

    def before_issue(document_id: str) -> None:
        with database() as uow:
            uow.lifecycle.assert_scope(document_id, scope)
            lifecycle = uow.lifecycle.get(document_id)
        if lifecycle is not None and lifecycle.state is not FiscalDocumentState.READY_TO_TRANSMIT:
            return  # Replayed settled job cannot require a new signing credential.
        if vault is None:
            raise RuntimeConfigurationError("Bling fiscal certificate is not configured")
        request = application.load_prepared_document_authorization(scope, document_id)
        if not isinstance(request, AuthorizationRequest):
            raise RuntimeConfigurationError("Bling requires a prepared NF-e")
        vault.resolve(scope=scope, issuer_cnpj=request.access_key.value[6:20])

    handler = BlingProcessingHandler(
        orders=orders,
        fetch=lambda order_id: fetch_sales_order(order_id, token()),
        fiscal_path=CanonicalFiscalOperationPath(application, handlers=handlers),
        before_issue=before_issue,
        validate_binding=validate_binding,
    )
    registered: dict[str, FiscalOutboxHandler] = {PROCESS_ORDER: handler}
    if status_mapping is not None:
        if set(status_mapping) != {"authorized", "rejected"}:
            raise RuntimeConfigurationError("Bling status mapping is incomplete")
        authorized, rejected = status_mapping["authorized"], status_mapping["rejected"]
        if (
            type(authorized) is not int or type(rejected) is not int
            or min(authorized, rejected) <= 0 or authorized == rejected
        ):
            raise RuntimeConfigurationError("Bling status mapping is invalid")
        registered[PUBLISH_STATUS] = BlingStatusPublisher(
            orders,
            {"authorized": authorized, "rejected": rejected},
            fetch=lambda order_id: fetch_sales_order(order_id, token()),
            update=lambda order_id, status: update_sales_order_status(
                order_id, status, token()
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


def build_bling_worker(
    database: FiscalUnitOfWorkFactory,
    environ: Mapping[str, str],
) -> ScopedWorkerHandlerComposition:
    """Existing opt-in single-company mode preserved for isolated legacy tests."""
    orders = build_bling_orders(database, environ)
    scope = orders.scope
    token_file = environ.get("NFCORE_BLING_ACCESS_TOKEN_FILE", "").strip()
    if not token_file:
        raise RuntimeConfigurationError("Bling OAuth token file is not configured")
    path = Path(token_file)

    def token() -> str:
        try:
            with path.open("rb") as stream:
                raw = stream.read(8193)
            value = raw.decode("ascii").strip()
            if len(raw) > 8192 or not value or any(not 33 <= ord(c) <= 126 for c in value):
                raise ValueError("invalid token")
            return value
        except (OSError, ValueError):
            raise RuntimeConfigurationError("Bling OAuth token is unavailable") from None

    token()  # Fail closed before continuous worker startup.
    validated_token_digest: str | None = None

    def scoped_token() -> str:
        nonlocal validated_token_digest
        value = token()
        digest = hashlib.sha256(value.encode()).hexdigest()
        if digest != validated_token_digest:
            verify_company(value, orders.company_id)
            validated_token_digest = digest
        return value

    def validate_binding() -> None:
        current = build_bling_orders(database, environ)
        if current.scope.identity_partition_key != scope.identity_partition_key:
            raise RuntimeConfigurationError("Bling installation binding changed")

    status_mapping: dict[str, int] | None = None
    keys = ("NFCORE_BLING_AUTHORIZED_STATUS_ID", "NFCORE_BLING_REJECTED_STATUS_ID")
    values = [environ.get(key, "").strip() for key in keys]
    if any(values):
        try:
            authorized, rejected = (int(value) for value in values)
        except ValueError:
            raise RuntimeConfigurationError("Bling status mapping is invalid") from None
        status_mapping = {"authorized": authorized, "rejected": rejected}

    return build_scoped_bling_handlers(
        database, orders,
        token=scoped_token,
        validate_binding=validate_binding,
        status_mapping=status_mapping,
        vault=EncryptedA1Vault.from_environ(),
    )
