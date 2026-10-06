"""Synthetic persisted configuration metadata; never real endpoints or credentials."""

from kordena_fiscal.control_plane import SecretReference, SecretReferenceKind
from kordena_fiscal.control_plane.commercial import (
    ConfiguredFiscalOperation,
    ProviderBinding,
    ProviderRuntimePolicyConfig,
    UnitModuleBinding,
    WebhookDestinationConfig,
)
from kordena_fiscal.domain import (
    BrazilianJurisdiction,
    FiscalAccountBinding,
    FiscalAccountId,
    FiscalDocumentKind,
    FiscalEnvironment,
    FiscalUnitId,
    HostNamespace,
    HostScope,
)

PROTECTED_QUERY = "SYNTHETIC_QUERY_MUST_NOT_ESCAPE"


def seed(database):
    hml = FiscalEnvironment.HOMOLOGATION
    for label, tenant, unit, env in (
        ("a", "tenant-a", "unit-a", hml),
        ("b", "tenant-a", "unit-b", hml),
        ("other", "tenant-b", "unit-a", hml),
        ("prod", "tenant-a", "unit-a", FiscalEnvironment.PRODUCTION),
    ):
        with database() as uow:
            for kind in SecretReferenceKind:
                uow.control_plane.add_secret_reference(
                    SecretReference(
                        reference_id="ref:synthetic-" + label + "-" + kind.value,
                        kind=kind, tenant_id=tenant, unit_id=unit, environment=env,
                        provider_id=(
                            None if kind is SecretReferenceKind.CERTIFICATE else "synthetic"
                        ),
                    )
                )
            uow.commercial.put_provider_binding(
                ProviderBinding(
                    binding_id="binding-" + label, tenant_id=tenant, unit_id=unit,
                    environment=env, document_kind=FiscalDocumentKind.NFE,
                    jurisdiction=BrazilianJurisdiction("SP"),
                    operation=ConfiguredFiscalOperation.AUTHORIZE,
                    provider_id="synthetic",
                )
            )
            uow.commercial.put_webhook_destination(
                WebhookDestinationConfig(
                    destination_id="events-" + label, tenant_id=tenant, unit_id=unit,
                    environment=env,
                    url=(
                        "https://callback.example.invalid/path/" + label
                        + "?token=" + PROTECTED_QUERY
                    ),
                )
            )
            uow.commercial.put_module_binding(
                UnitModuleBinding(
                    tenant_id=tenant, unit_id=unit, environment=env, module_id="module-" + label,
                )
            )
            uow.commercial.put_runtime_policy(
                ProviderRuntimePolicyConfig(
                    policy_id="policy-" + label, tenant_id=tenant, unit_id=unit, environment=env,
                    provider_id="synthetic", connect_timeout_seconds=2, read_timeout_seconds=5,
                    max_attempts=2, base_delay_seconds=1, max_delay_seconds=5, jitter_ratio=0.1,
                    circuit_failure_threshold=3, circuit_recovery_seconds=10,
                )
            )
            uow.commit()
        if env is hml:
            with database() as uow:
                uow.bindings.add(
                    FiscalAccountBinding(
                        binding_id="host-binding-" + label,
                        host_scope=HostScope(
                            namespace=HostNamespace("synthetic-host"),
                            tenant_id="external-" + label, unit_id="external-unit-" + label,
                        ),
                        fiscal_account_id=FiscalAccountId(tenant),
                        fiscal_unit_id=FiscalUnitId(unit),
                    )
                )
                uow.commit()
