"""Governed writes for durable commercial runtime configuration."""

from __future__ import annotations

from kordena_fiscal.control_plane.commercial_models import (
    HomologationEvidenceRecord,
    NumberingConfiguration,
)
from kordena_fiscal.domain import FiscalEnvironment, FiscalValidationError
from kordena_fiscal.persistence.ports import FiscalUnitOfWorkFactory
from kordena_fiscal.security import WorkloadCredentialRecord

from .models import AdminPrincipal, ControlPlanePermission
from .service import (
    ControlPlaneAuthorizationError,
    ControlPlaneNotFoundError,
)


class CommercialRuntimeConfigurationService:
    """Governed writes for the remaining B0 commercial-runtime configuration."""

    def __init__(self, unit_of_work_factory: FiscalUnitOfWorkFactory) -> None:
        self._unit_of_work_factory = unit_of_work_factory

    def set_numbering_configuration(
        self,
        *,
        actor: AdminPrincipal,
        config: NumberingConfiguration,
    ) -> NumberingConfiguration:
        self._require_tenant(actor, config.tenant_id)
        self._require_unit_environment(
            config.tenant_id,
            config.unit_id,
            config.environment,
        )
        with self._unit_of_work_factory() as uow:
            result = uow.commercial.put_numbering_configuration(config)
            uow.commit()
        return result

    def set_homologation_evidence(
        self,
        *,
        actor: AdminPrincipal,
        record: HomologationEvidenceRecord,
    ) -> HomologationEvidenceRecord:
        self._require_tenant(actor, record.tenant_id)
        self._require_unit_environment(
            record.tenant_id,
            record.unit_id,
            record.environment,
        )
        with self._unit_of_work_factory() as uow:
            result = uow.commercial.put_homologation_evidence(record)
            uow.commit()
        return result

    def set_workload_credential(
        self,
        *,
        actor: AdminPrincipal,
        record: WorkloadCredentialRecord,
    ) -> WorkloadCredentialRecord:
        self._require_permission(actor)
        tenant_grants = {
            grant.tenant_id
            for grant in record.caller.scope_grants
            if grant.tenant_id is not None
        }
        if any(grant.tenant_id is None for grant in record.caller.scope_grants):
            if not actor.global_scope:
                raise ControlPlaneAuthorizationError(
                    "global workload grants require a global administrator"
                )
        elif not all(actor.can_access_tenant(tenant_id) for tenant_id in tenant_grants):
            raise ControlPlaneAuthorizationError(
                "actor cannot configure workload grants for another tenant"
            )
        with self._unit_of_work_factory() as uow:
            result = uow.commercial.put_workload_credential(record)
            uow.commit()
        return result

    def _require_unit_environment(
        self,
        tenant_id: str,
        unit_id: str,
        environment: FiscalEnvironment,
    ) -> None:
        with self._unit_of_work_factory() as uow:
            unit = uow.control_plane.get_unit(tenant_id, unit_id)
        if unit is None:
            raise ControlPlaneNotFoundError(
                f"unit is not onboarded: {tenant_id}/{unit_id}"
            )
        if environment not in unit.enabled_environments:
            raise ControlPlaneAuthorizationError(
                "environment is not enabled for the target unit"
            )

    @staticmethod
    def _require_permission(actor: AdminPrincipal) -> None:
        if not isinstance(actor, AdminPrincipal):
            raise FiscalValidationError("actor must be AdminPrincipal")
        permission = ControlPlanePermission.COMMERCIAL_CONFIG_WRITE
        if not actor.has_permission(permission):
            raise ControlPlaneAuthorizationError(
                f"actor lacks required permission: {permission.value}"
            )

    @classmethod
    def _require_tenant(cls, actor: AdminPrincipal, tenant_id: str) -> None:
        cls._require_permission(actor)
        if not actor.can_access_tenant(tenant_id):
            raise ControlPlaneAuthorizationError(
                f"actor cannot access tenant: {tenant_id}"
            )

