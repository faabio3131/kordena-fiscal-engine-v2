"""Explicit GSM composition and platform-only metadata administration.

No environment credential discovery or cloud provisioning occurs here. Callers supply
an approved workload reader; the existing vault/resolver/Worker retain their authority.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from kordena_fiscal.control_plane.models import ControlPlaneAuditAction, ControlPlaneAuditEvent
from kordena_fiscal.domain import ExecutionScope
from kordena_fiscal.persistence.ports import FiscalUnitOfWorkFactory
from kordena_fiscal.security.human_identity import AuthenticatedHuman
from kordena_fiscal.security.s2s import WebhookSecurity
from kordena_fiscal.security.secret_binding import SecretBinding
from kordena_fiscal.security.secrets import (
    SecretAuditSink,
    SecretReference,
    SecretResolutionError,
    SecretResolver,
    SecretScope,
)
from kordena_fiscal.vault.external import ExternalFiscalSecretVault, SecretAccessAuditSink
from kordena_fiscal.vault.google_secret_manager import (
    DurableGsmReader,
    GoogleFiscalSecretClient,
    GoogleSignatureSecretBackend,
)

from .worker_composition import WorkerWebhookDependencies


class SecretBindingAdministration:
    """Internal metadata command; cloud-resource administration is platform-only."""

    def __init__(
        self, uow_factory: FiscalUnitOfWorkFactory, *, clock: Callable[[], datetime] | None = None
    ) -> None:
        self._uow = uow_factory
        self._clock = clock or (lambda: datetime.now(UTC))

    def put(
        self,
        *,
        actor: AuthenticatedHuman,
        binding: SecretBinding,
        expected_revision: int,
        correlation_id: str,
    ) -> None:
        now = self._clock()
        if (
            not isinstance(actor, AuthenticatedHuman)
            or not actor.account.enabled
            or not actor.account.is_platform_admin
            or actor.expires_at <= now
        ):
            raise SecretResolutionError("platform administrator required for cloud binding")
        with self._uow() as uow:
            previous = uow.secret_bindings.get(binding.reference_id)
            if previous == binding:
                return  # Exact replay: previous command and its audit are already committed.
            if previous is not None:
                # The reference identity cannot be re-used to change tenant/purpose/workload.
                fixed = (
                    "tenant_id",
                    "unit_id",
                    "purpose",
                    "runtime_environment",
                    "fiscal_environment",
                    "provider_id",
                    "workload_id",
                    "kind",
                )
                if any(getattr(previous, x) != getattr(binding, x) for x in fixed):
                    raise SecretResolutionError("binding identity cannot change scope")
            uow.secret_bindings.put(binding, expected_revision=expected_revision)
            uow.control_plane.append_audit(
                ControlPlaneAuditEvent(
                    event_id=uuid4().hex,
                    occurred_at=now,
                    actor_id=actor.account.account_id,
                    action=ControlPlaneAuditAction.SECRET_REFERENCE_BOUND,
                    target_type="external_secret_binding",
                    target_id=binding.reference_id,
                    correlation_id=correlation_id,
                    tenant_id=binding.tenant_id,
                    unit_id=binding.unit_id,
                )
            )
            uow.commit()


@dataclass(frozen=True, slots=True)
class GsmSecretComposition:
    fiscal_vault: ExternalFiscalSecretVault
    signature_resolver: SecretResolver


def build_gsm_secret_composition(
    *,
    reader: DurableGsmReader,
    signature_provider_id: str,
    fiscal_audit: SecretAccessAuditSink,
    signature_audit: SecretAuditSink,
    clock: Callable[[], datetime] | None = None,
) -> GsmSecretComposition:
    return GsmSecretComposition(
        ExternalFiscalSecretVault(client=GoogleFiscalSecretClient(reader), audit=fiscal_audit),
        SecretResolver(
            GoogleSignatureSecretBackend(reader, provider_id=signature_provider_id),
            environment=reader.environment,
            audit_sink=signature_audit,
            clock=clock,
        ),
    )


class _GsmWebhookKeys:
    def __init__(
        self, resolver: SecretResolver, reference: SecretReference, scope: SecretScope
    ) -> None:
        self._resolver = resolver
        self._reference = reference
        self._scope = scope

    def resolve(self, key_id: str) -> bytes | None:
        if key_id != self._reference.reference_id:
            raise SecretResolutionError("webhook signing reference mismatch")
        with self._resolver.resolve(self._reference, scope=self._scope) as material:
            return material.reveal()


class _ScopedGsmWebhookSecurity(WebhookSecurity):
    def __init__(
        self, resolver: SecretResolver, reference: SecretReference, scope: SecretScope
    ) -> None:
        super().__init__(
            key_resolver=_GsmWebhookKeys(resolver, reference, scope),
            signing_key_id=reference.reference_id,
        )
        self._scope = scope

    def assert_dispatch_scope(self, scope: ExecutionScope) -> None:
        if scope.tenant_id != self._scope.tenant_id or scope.unit_id != self._scope.unit_id:
            raise SecretResolutionError("worker secret dispatch scope mismatch")


def build_gsm_worker_webhook_dependencies(
    *, resolver: SecretResolver, reference: SecretReference, scope: SecretScope, destination_id: str
) -> WorkerWebhookDependencies:
    """Same worker registry; one explicitly scoped signing dependency, no key cache.

    This factory alone does not install a Railway bootstrap or certify a multi-tenant
    signing registry. Unsupported scopes fail before secret access/delivery.
    """
    return WorkerWebhookDependencies(
        security=_ScopedGsmWebhookSecurity(resolver, reference, scope),
        destination_id=destination_id,
    )
