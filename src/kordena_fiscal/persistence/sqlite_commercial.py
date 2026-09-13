"""SQLite persistence for zero-code commercial fiscal configuration."""

from __future__ import annotations

import sqlite3
from datetime import datetime

from kordena_fiscal.control_plane.commercial import (
    ConfiguredFiscalOperation,
    ProviderBinding,
    ProviderRuntimePolicyConfig,
    UnitModuleBinding,
    WebhookDestinationConfig,
)
from kordena_fiscal.domain import (
    BrazilianJurisdiction,
    CestCode,
    ExecutionScope,
    FiscalDocumentKind,
    FiscalEnvironment,
    FiscalProductProfile,
    FiscalUnitCode,
    FiscalValidationError,
    Gtin,
    NcmCode,
    ProductOrigin,
    TaxClassificationHints,
)

from ._sqlite_common import dt, integer, iso, one_row, optional_text, text
from .ports import PersistenceConflictError, PersistenceStateError

_PRODUCT_SELECT = """
    profile_id, version, product_id, host_namespace, tenant_id, unit_id,
    environment, correlation_id, commercial_code, description, ncm,
    commercial_unit, taxable_unit, origin, cest, gtin, fiscal_benefit_code,
    ibs_cbs_classification_code, effective_from, effective_to
"""


def _normalized(value: str, field_name: str) -> str:
    result = value.strip().lower()
    if not result:
        raise FiscalValidationError(f"{field_name} must not be blank")
    return result


class SqliteCommercialConfigurationStore:
    """Transactional durable repository for customer-specific configuration."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def put_provider_binding(self, binding: ProviderBinding) -> ProviderBinding:
        if not isinstance(binding, ProviderBinding):
            raise FiscalValidationError("binding must be ProviderBinding")
        municipality = binding.jurisdiction.municipality_ibge_code or ""
        try:
            self._connection.execute(
                """
                INSERT INTO fm_commercial_provider_bindings (
                    binding_id, tenant_id, unit_id, environment, document_kind,
                    state_code, municipality_ibge_code, operation, provider_id, enabled
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (
                    tenant_id, unit_id, environment, document_kind,
                    state_code, municipality_ibge_code, operation
                ) DO UPDATE SET
                    binding_id = excluded.binding_id,
                    provider_id = excluded.provider_id,
                    enabled = excluded.enabled
                """,
                (
                    binding.binding_id,
                    binding.tenant_id,
                    binding.unit_id,
                    binding.environment.value,
                    binding.document_kind.value,
                    binding.jurisdiction.state_code,
                    municipality,
                    binding.operation.value,
                    binding.provider_id,
                    1 if binding.enabled else 0,
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise PersistenceConflictError("provider binding conflicts with existing identity") from exc
        return binding

    def resolve_provider_binding(
        self,
        *,
        tenant_id: str,
        unit_id: str,
        environment: FiscalEnvironment,
        document_kind: FiscalDocumentKind,
        jurisdiction: BrazilianJurisdiction,
        operation: ConfiguredFiscalOperation,
    ) -> ProviderBinding | None:
        if not isinstance(environment, FiscalEnvironment):
            raise FiscalValidationError("environment must be FiscalEnvironment")
        if not isinstance(document_kind, FiscalDocumentKind):
            raise FiscalValidationError("document_kind must be FiscalDocumentKind")
        if not isinstance(jurisdiction, BrazilianJurisdiction):
            raise FiscalValidationError("jurisdiction must be BrazilianJurisdiction")
        if not isinstance(operation, ConfiguredFiscalOperation):
            raise FiscalValidationError("operation must be ConfiguredFiscalOperation")
        tenant = _normalized(tenant_id, "tenant_id")
        unit = _normalized(unit_id, "unit_id")
        municipality = jurisdiction.municipality_ibge_code or ""
        row = one_row(
            self._connection.execute(
                """
                SELECT binding_id, tenant_id, unit_id, environment, document_kind,
                       state_code, municipality_ibge_code, operation, provider_id, enabled
                FROM fm_commercial_provider_bindings
                WHERE tenant_id = ? AND unit_id = ? AND environment = ?
                  AND document_kind = ? AND state_code = ?
                  AND municipality_ibge_code = ? AND operation = ?
                """,
                (
                    tenant,
                    unit,
                    environment.value,
                    document_kind.value,
                    jurisdiction.state_code,
                    municipality,
                    operation.value,
                ),
            )
        )
        if row is None:
            return None
        persisted_municipality = text(row[6], "municipality_ibge_code")
        return ProviderBinding(
            binding_id=text(row[0], "binding_id"),
            tenant_id=text(row[1], "tenant_id"),
            unit_id=text(row[2], "unit_id"),
            environment=FiscalEnvironment(text(row[3], "environment")),
            document_kind=FiscalDocumentKind(text(row[4], "document_kind")),
            jurisdiction=BrazilianJurisdiction(
                text(row[5], "state_code"),
                persisted_municipality or None,
            ),
            operation=ConfiguredFiscalOperation(text(row[7], "operation")),
            provider_id=text(row[8], "provider_id"),
            enabled=bool(integer(row[9], "enabled")),
        )

    def add_product_profile(self, profile: FiscalProductProfile) -> FiscalProductProfile:
        if not isinstance(profile, FiscalProductProfile):
            raise FiscalValidationError("profile must be FiscalProductProfile")
        if profile.scope.host_namespace is None:
            raise FiscalValidationError("commercial product profile requires host_namespace")
        existing = one_row(
            self._connection.execute(
                """
                SELECT profile_id FROM fm_commercial_product_profiles
                WHERE profile_id = ? AND version = ?
                """,
                (profile.profile_id, profile.version),
            )
        )
        if existing is not None:
            raise PersistenceConflictError("product fiscal profile id/version already exists")
        new_end = None if profile.effective_to is None else iso(profile.effective_to)
        overlap = one_row(
            self._connection.execute(
                """
                SELECT profile_id, version
                FROM fm_commercial_product_profiles
                WHERE tenant_id = ? AND unit_id = ? AND environment = ?
                  AND product_id = ?
                  AND (? IS NULL OR effective_from < ?)
                  AND (effective_to IS NULL OR effective_to > ?)
                LIMIT 1
                """,
                (
                    profile.scope.tenant_id,
                    profile.scope.unit_id,
                    profile.scope.environment.value,
                    profile.product_id,
                    new_end,
                    new_end,
                    iso(profile.effective_from),
                ),
            )
        )
        if overlap is not None:
            raise PersistenceConflictError(
                "product fiscal profile effective period overlaps an existing profile"
            )
        self._connection.execute(
            """
            INSERT INTO fm_commercial_product_profiles (
                profile_id, version, product_id, host_namespace, tenant_id, unit_id,
                environment, correlation_id, commercial_code, description, ncm,
                commercial_unit, taxable_unit, origin, cest, gtin, fiscal_benefit_code,
                ibs_cbs_classification_code, effective_from, effective_to
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                profile.profile_id,
                profile.version,
                profile.product_id,
                profile.scope.host_namespace,
                profile.scope.tenant_id,
                profile.scope.unit_id,
                profile.scope.environment.value,
                profile.scope.correlation_id,
                profile.commercial_code,
                profile.description,
                profile.ncm.value,
                profile.commercial_unit.value,
                profile.taxable_unit.value,
                int(profile.origin),
                None if profile.cest is None else profile.cest.value,
                None if profile.gtin is None else profile.gtin.value,
                profile.hints.fiscal_benefit_code,
                profile.hints.ibs_cbs_classification_code,
                iso(profile.effective_from),
                new_end,
            ),
        )
        return profile

    @staticmethod
    def _product_profile(row: tuple[object, ...]) -> FiscalProductProfile:
        cest = optional_text(row[14], "cest")
        gtin = optional_text(row[15], "gtin")
        return FiscalProductProfile(
            profile_id=text(row[0], "profile_id"),
            version=integer(row[1], "version"),
            product_id=text(row[2], "product_id"),
            scope=ExecutionScope(
                host_namespace=text(row[3], "host_namespace"),
                tenant_id=text(row[4], "tenant_id"),
                unit_id=text(row[5], "unit_id"),
                environment=FiscalEnvironment(text(row[6], "environment")),
                correlation_id=text(row[7], "correlation_id"),
            ),
            commercial_code=text(row[8], "commercial_code"),
            description=text(row[9], "description"),
            ncm=NcmCode(text(row[10], "ncm")),
            commercial_unit=FiscalUnitCode(text(row[11], "commercial_unit")),
            taxable_unit=FiscalUnitCode(text(row[12], "taxable_unit")),
            origin=ProductOrigin(integer(row[13], "origin")),
            cest=None if cest is None else CestCode(cest),
            gtin=None if gtin is None else Gtin(gtin),
            hints=TaxClassificationHints(
                fiscal_benefit_code=optional_text(row[16], "fiscal_benefit_code"),
                ibs_cbs_classification_code=optional_text(
                    row[17], "ibs_cbs_classification_code"
                ),
            ),
            effective_from=dt(text(row[18], "effective_from")),
            effective_to=None if row[19] is None else dt(text(row[19], "effective_to")),
        )

    def resolve_product_profile(
        self,
        *,
        tenant_id: str,
        unit_id: str,
        environment: FiscalEnvironment,
        product_id: str,
        instant: datetime,
    ) -> FiscalProductProfile | None:
        tenant = _normalized(tenant_id, "tenant_id")
        unit = _normalized(unit_id, "unit_id")
        product = _normalized(product_id, "product_id")
        instant_iso = iso(instant)
        rows = self._connection.execute(
            f"""
            SELECT {_PRODUCT_SELECT}
            FROM fm_commercial_product_profiles
            WHERE tenant_id = ? AND unit_id = ? AND environment = ?
              AND product_id = ? AND effective_from <= ?
              AND (effective_to IS NULL OR effective_to > ?)
            ORDER BY effective_from DESC
            LIMIT 2
            """,
            (tenant, unit, environment.value, product, instant_iso, instant_iso),
        ).fetchall()
        if not rows:
            return None
        if len(rows) > 1:
            raise PersistenceStateError(
                "multiple effective product fiscal profiles found for the same partition"
            )
        return self._product_profile(tuple(rows[0]))

    def put_module_binding(self, binding: UnitModuleBinding) -> UnitModuleBinding:
        if not isinstance(binding, UnitModuleBinding):
            raise FiscalValidationError("binding must be UnitModuleBinding")
        self._connection.execute(
            """
            INSERT INTO fm_commercial_unit_modules (
                tenant_id, unit_id, environment, module_id, enabled
            ) VALUES (?, ?, ?, ?, ?)
            ON CONFLICT (tenant_id, unit_id, environment, module_id)
            DO UPDATE SET enabled = excluded.enabled
            """,
            (
                binding.tenant_id,
                binding.unit_id,
                binding.environment.value,
                binding.module_id,
                1 if binding.enabled else 0,
            ),
        )
        return binding

    def list_module_bindings(
        self,
        *,
        tenant_id: str,
        unit_id: str,
        environment: FiscalEnvironment,
    ) -> tuple[UnitModuleBinding, ...]:
        tenant = _normalized(tenant_id, "tenant_id")
        unit = _normalized(unit_id, "unit_id")
        rows = self._connection.execute(
            """
            SELECT tenant_id, unit_id, environment, module_id, enabled
            FROM fm_commercial_unit_modules
            WHERE tenant_id = ? AND unit_id = ? AND environment = ?
            ORDER BY module_id
            """,
            (tenant, unit, environment.value),
        ).fetchall()
        return tuple(
            UnitModuleBinding(
                tenant_id=text(row[0], "tenant_id"),
                unit_id=text(row[1], "unit_id"),
                environment=FiscalEnvironment(text(row[2], "environment")),
                module_id=text(row[3], "module_id"),
                enabled=bool(integer(row[4], "enabled")),
            )
            for row in rows
        )

    def put_webhook_destination(
        self,
        destination: WebhookDestinationConfig,
    ) -> WebhookDestinationConfig:
        if not isinstance(destination, WebhookDestinationConfig):
            raise FiscalValidationError("destination must be WebhookDestinationConfig")
        self._connection.execute(
            """
            INSERT INTO fm_commercial_webhook_destinations (
                tenant_id, unit_id, environment, destination_id, url, enabled
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT (tenant_id, unit_id, environment, destination_id)
            DO UPDATE SET url = excluded.url, enabled = excluded.enabled
            """,
            (
                destination.tenant_id,
                destination.unit_id,
                destination.environment.value,
                destination.destination_id,
                destination.url,
                1 if destination.enabled else 0,
            ),
        )
        return destination

    def list_webhook_destinations(
        self,
        *,
        tenant_id: str,
        unit_id: str,
        environment: FiscalEnvironment,
    ) -> tuple[WebhookDestinationConfig, ...]:
        tenant = _normalized(tenant_id, "tenant_id")
        unit = _normalized(unit_id, "unit_id")
        rows = self._connection.execute(
            """
            SELECT destination_id, tenant_id, unit_id, environment, url, enabled
            FROM fm_commercial_webhook_destinations
            WHERE tenant_id = ? AND unit_id = ? AND environment = ?
            ORDER BY destination_id
            """,
            (tenant, unit, environment.value),
        ).fetchall()
        return tuple(
            WebhookDestinationConfig(
                destination_id=text(row[0], "destination_id"),
                tenant_id=text(row[1], "tenant_id"),
                unit_id=text(row[2], "unit_id"),
                environment=FiscalEnvironment(text(row[3], "environment")),
                url=text(row[4], "url"),
                enabled=bool(integer(row[5], "enabled")),
            )
            for row in rows
        )

    def put_runtime_policy(
        self,
        policy: ProviderRuntimePolicyConfig,
    ) -> ProviderRuntimePolicyConfig:
        if not isinstance(policy, ProviderRuntimePolicyConfig):
            raise FiscalValidationError("policy must be ProviderRuntimePolicyConfig")
        self._connection.execute(
            """
            INSERT INTO fm_commercial_provider_runtime_policies (
                tenant_id, unit_id, environment, provider_id, policy_id,
                connect_timeout_seconds, read_timeout_seconds, max_attempts,
                base_delay_seconds, max_delay_seconds, jitter_ratio,
                circuit_failure_threshold, circuit_recovery_seconds,
                circuit_success_threshold
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (tenant_id, unit_id, environment, provider_id)
            DO UPDATE SET
                policy_id = excluded.policy_id,
                connect_timeout_seconds = excluded.connect_timeout_seconds,
                read_timeout_seconds = excluded.read_timeout_seconds,
                max_attempts = excluded.max_attempts,
                base_delay_seconds = excluded.base_delay_seconds,
                max_delay_seconds = excluded.max_delay_seconds,
                jitter_ratio = excluded.jitter_ratio,
                circuit_failure_threshold = excluded.circuit_failure_threshold,
                circuit_recovery_seconds = excluded.circuit_recovery_seconds,
                circuit_success_threshold = excluded.circuit_success_threshold
            """,
            (
                policy.tenant_id,
                policy.unit_id,
                policy.environment.value,
                policy.provider_id,
                policy.policy_id,
                policy.connect_timeout_seconds,
                policy.read_timeout_seconds,
                policy.max_attempts,
                policy.base_delay_seconds,
                policy.max_delay_seconds,
                policy.jitter_ratio,
                policy.circuit_failure_threshold,
                policy.circuit_recovery_seconds,
                policy.circuit_success_threshold,
            ),
        )
        return policy

    def get_runtime_policy(
        self,
        *,
        tenant_id: str,
        unit_id: str,
        environment: FiscalEnvironment,
        provider_id: str,
    ) -> ProviderRuntimePolicyConfig | None:
        tenant = _normalized(tenant_id, "tenant_id")
        unit = _normalized(unit_id, "unit_id")
        provider = _normalized(provider_id, "provider_id")
        row = one_row(
            self._connection.execute(
                """
                SELECT policy_id, tenant_id, unit_id, environment, provider_id,
                       connect_timeout_seconds, read_timeout_seconds, max_attempts,
                       base_delay_seconds, max_delay_seconds, jitter_ratio,
                       circuit_failure_threshold, circuit_recovery_seconds,
                       circuit_success_threshold
                FROM fm_commercial_provider_runtime_policies
                WHERE tenant_id = ? AND unit_id = ? AND environment = ? AND provider_id = ?
                """,
                (tenant, unit, environment.value, provider),
            )
        )
        if row is None:
            return None
        return ProviderRuntimePolicyConfig(
            policy_id=text(row[0], "policy_id"),
            tenant_id=text(row[1], "tenant_id"),
            unit_id=text(row[2], "unit_id"),
            environment=FiscalEnvironment(text(row[3], "environment")),
            provider_id=text(row[4], "provider_id"),
            connect_timeout_seconds=float(row[5]),
            read_timeout_seconds=float(row[6]),
            max_attempts=integer(row[7], "max_attempts"),
            base_delay_seconds=float(row[8]),
            max_delay_seconds=float(row[9]),
            jitter_ratio=float(row[10]),
            circuit_failure_threshold=integer(row[11], "circuit_failure_threshold"),
            circuit_recovery_seconds=float(row[12]),
            circuit_success_threshold=integer(row[13], "circuit_success_threshold"),
        )
