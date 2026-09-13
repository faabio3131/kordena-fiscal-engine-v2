"""SQLite persistence for zero-code commercial fiscal configuration."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime

from kordena_fiscal.control_plane.commercial import (
    ConfiguredFiscalOperation,
    ProviderBinding,
    ProviderRuntimePolicyConfig,
    UnitModuleBinding,
    WebhookDestinationConfig,
)
from kordena_fiscal.control_plane.commercial_models import (
    HomologationEvidenceRecord,
    NumberingConfiguration,
)
from kordena_fiscal.domain import (
    BrazilianJurisdiction,
    CestCode,
    ElectronicInvoiceModel,
    ExecutionScope,
    FiscalDocumentKind,
    FiscalEnvironment,
    FiscalProductProfile,
    FiscalUnitCode,
    FiscalValidationError,
    Gtin,
    HostNamespace,
    NcmCode,
    ProductOrigin,
    TaxClassificationHints,
)
from kordena_fiscal.security import (
    CallerIdentity,
    FiscalCapability,
    HostScopeGrant,
    WorkloadCredentialRecord,
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


def _required(value: str, field_name: str) -> str:
    result = value.strip()
    if not result:
        raise FiscalValidationError(f"{field_name} must not be blank")
    return result


def _real(value: object, field_name: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise PersistenceStateError(f"persisted {field_name} must be numeric")
    return float(value)


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
            raise PersistenceConflictError(
                "provider binding conflicts with existing identity"
            ) from exc
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
        product = _required(product_id, "product_id")
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
            connect_timeout_seconds=_real(row[5], "connect_timeout_seconds"),
            read_timeout_seconds=_real(row[6], "read_timeout_seconds"),
            max_attempts=integer(row[7], "max_attempts"),
            base_delay_seconds=_real(row[8], "base_delay_seconds"),
            max_delay_seconds=_real(row[9], "max_delay_seconds"),
            jitter_ratio=_real(row[10], "jitter_ratio"),
            circuit_failure_threshold=integer(row[11], "circuit_failure_threshold"),
            circuit_recovery_seconds=_real(row[12], "circuit_recovery_seconds"),
            circuit_success_threshold=integer(row[13], "circuit_success_threshold"),
        )


    def put_numbering_configuration(
        self,
        config: NumberingConfiguration,
    ) -> NumberingConfiguration:
        if not isinstance(config, NumberingConfiguration):
            raise FiscalValidationError("config must be NumberingConfiguration")
        self._connection.execute(
            """
            INSERT INTO fm_commercial_numbering_configurations (
                tenant_id, unit_id, environment, model, series,
                first_number, max_number, enabled
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (tenant_id, unit_id, environment, model)
            DO UPDATE SET
                series = excluded.series,
                first_number = excluded.first_number,
                max_number = excluded.max_number,
                enabled = excluded.enabled
            """,
            (
                config.tenant_id,
                config.unit_id,
                config.environment.value,
                config.model.value,
                config.series,
                config.first_number,
                config.max_number,
                int(config.enabled),
            ),
        )
        return config

    def get_numbering_configuration(
        self,
        *,
        tenant_id: str,
        unit_id: str,
        environment: FiscalEnvironment,
        model: object,
    ) -> NumberingConfiguration | None:
        if not isinstance(model, ElectronicInvoiceModel):
            raise FiscalValidationError("model must be ElectronicInvoiceModel")
        row = one_row(
            self._connection.execute(
                """
                SELECT tenant_id, unit_id, environment, model, series,
                       first_number, max_number, enabled
                FROM fm_commercial_numbering_configurations
                WHERE tenant_id = ? AND unit_id = ?
                  AND environment = ? AND model = ?
                """,
                (
                    _normalized(tenant_id, "tenant_id"),
                    _normalized(unit_id, "unit_id"),
                    environment.value,
                    model.value,
                ),
            )
        )
        if row is None:
            return None
        max_number = None if row[6] is None else integer(row[6], "max_number")
        return NumberingConfiguration(
            tenant_id=text(row[0], "tenant_id"),
            unit_id=text(row[1], "unit_id"),
            environment=FiscalEnvironment(text(row[2], "environment")),
            model=ElectronicInvoiceModel(integer(row[3], "model")),
            series=integer(row[4], "series"),
            first_number=integer(row[5], "first_number"),
            max_number=max_number,
            enabled=bool(integer(row[7], "enabled")),
        )

    def put_workload_credential(
        self,
        record: WorkloadCredentialRecord,
    ) -> WorkloadCredentialRecord:
        if not isinstance(record, WorkloadCredentialRecord):
            raise FiscalValidationError("record must be WorkloadCredentialRecord")
        capabilities_json = json.dumps(
            sorted(capability.value for capability in record.caller.capabilities),
            separators=(",", ":"),
        )
        grants_json = json.dumps(
            [
                {"tenant_id": grant.tenant_id, "unit_id": grant.unit_id}
                for grant in record.caller.scope_grants
            ],
            separators=(",", ":"),
            sort_keys=True,
        )
        self._connection.execute(
            """
            INSERT INTO fm_commercial_workload_credentials (
                credential_id, caller_id, host_namespace, capabilities_json,
                grants_json, secret_sha256, valid_from, expires_at, revoked
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (credential_id) DO UPDATE SET
                caller_id = excluded.caller_id,
                host_namespace = excluded.host_namespace,
                capabilities_json = excluded.capabilities_json,
                grants_json = excluded.grants_json,
                secret_sha256 = excluded.secret_sha256,
                valid_from = excluded.valid_from,
                expires_at = excluded.expires_at,
                revoked = excluded.revoked
            """,
            (
                record.credential_id,
                record.caller.caller_id,
                record.caller.host_namespace.value,
                capabilities_json,
                grants_json,
                record.secret_sha256,
                iso(record.valid_from),
                iso(record.expires_at),
                int(record.revoked),
            ),
        )
        return record

    def get_workload_credential(
        self,
        credential_id: str,
    ) -> WorkloadCredentialRecord | None:
        row = one_row(
            self._connection.execute(
                """
                SELECT credential_id, caller_id, host_namespace,
                       capabilities_json, grants_json, secret_sha256,
                       valid_from, expires_at, revoked
                FROM fm_commercial_workload_credentials
                WHERE credential_id = ?
                """,
                (_required(credential_id, "credential_id"),),
            )
        )
        if row is None:
            return None
        raw_capabilities = json.loads(text(row[3], "capabilities_json"))
        raw_grants = json.loads(text(row[4], "grants_json"))
        if not isinstance(raw_capabilities, list) or not all(
            isinstance(item, str) for item in raw_capabilities
        ):
            raise PersistenceStateError(
                "persisted workload capabilities must be a string list"
            )
        if not isinstance(raw_grants, list) or not all(
            isinstance(item, dict) for item in raw_grants
        ):
            raise PersistenceStateError(
                "persisted workload grants must be an object list"
            )
        grants: list[HostScopeGrant] = []
        for raw_grant in raw_grants:
            tenant = raw_grant.get("tenant_id")
            unit = raw_grant.get("unit_id")
            if tenant is not None and not isinstance(tenant, str):
                raise PersistenceStateError(
                    "persisted workload grant tenant_id must be text or null"
                )
            if unit is not None and not isinstance(unit, str):
                raise PersistenceStateError(
                    "persisted workload grant unit_id must be text or null"
                )
            grants.append(HostScopeGrant(tenant_id=tenant, unit_id=unit))
        caller = CallerIdentity(
            caller_id=text(row[1], "caller_id"),
            host_namespace=HostNamespace(text(row[2], "host_namespace")),
            capabilities=frozenset(
                FiscalCapability(item) for item in raw_capabilities
            ),
            scope_grants=tuple(grants),
        )
        return WorkloadCredentialRecord(
            credential_id=text(row[0], "credential_id"),
            caller=caller,
            secret_sha256=text(row[5], "secret_sha256"),
            valid_from=dt(text(row[6], "valid_from")),
            expires_at=dt(text(row[7], "expires_at")),
            revoked=bool(integer(row[8], "revoked")),
        )

    def put_homologation_evidence(
        self,
        record: HomologationEvidenceRecord,
    ) -> HomologationEvidenceRecord:
        if not isinstance(record, HomologationEvidenceRecord):
            raise FiscalValidationError("record must be HomologationEvidenceRecord")
        municipality = record.jurisdiction.municipality_ibge_code or ""
        self._connection.execute(
            """
            INSERT INTO fm_commercial_homologation_evidence (
                tenant_id, unit_id, environment, provider_id, document_kind,
                state_code, municipality_ibge_code, operation,
                provider_adapter_available,
                credentials_reference_configured, signer_capability,
                csc_reference_configured, transport_configured,
                resilience_certified, contract_tests_certified,
                jurisdiction_mapping, operation_supported,
                requires_signer, requires_csc, external_evidence_id,
                external_official, recorded_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (
                tenant_id, unit_id, environment, provider_id, document_kind,
                state_code, municipality_ibge_code, operation
            ) DO UPDATE SET
                provider_adapter_available = excluded.provider_adapter_available,
                credentials_reference_configured = excluded.credentials_reference_configured,
                signer_capability = excluded.signer_capability,
                csc_reference_configured = excluded.csc_reference_configured,
                transport_configured = excluded.transport_configured,
                resilience_certified = excluded.resilience_certified,
                contract_tests_certified = excluded.contract_tests_certified,
                jurisdiction_mapping = excluded.jurisdiction_mapping,
                operation_supported = excluded.operation_supported,
                requires_signer = excluded.requires_signer,
                requires_csc = excluded.requires_csc,
                external_evidence_id = excluded.external_evidence_id,
                external_official = excluded.external_official,
                recorded_at = excluded.recorded_at
            """,
            (
                record.tenant_id,
                record.unit_id,
                record.environment.value,
                record.provider_id,
                record.document_kind.value,
                record.jurisdiction.state_code,
                municipality,
                record.operation,
                int(record.provider_adapter_available),
                int(record.credentials_reference_configured),
                int(record.signer_capability),
                int(record.csc_reference_configured),
                int(record.transport_configured),
                int(record.resilience_certified),
                int(record.contract_tests_certified),
                int(record.jurisdiction_mapping),
                int(record.operation_supported),
                int(record.requires_signer),
                int(record.requires_csc),
                record.external_evidence_id,
                int(record.external_official),
                None if record.recorded_at is None else iso(record.recorded_at),
            ),
        )
        return record

    def get_homologation_evidence(
        self,
        *,
        tenant_id: str,
        unit_id: str,
        environment: FiscalEnvironment,
        provider_id: str,
        document_kind: FiscalDocumentKind,
        jurisdiction: BrazilianJurisdiction,
        operation: str,
    ) -> HomologationEvidenceRecord | None:
        municipality = jurisdiction.municipality_ibge_code or ""
        row = one_row(
            self._connection.execute(
                """
                SELECT tenant_id, unit_id, environment, provider_id,
                       document_kind, state_code, municipality_ibge_code,
                       operation, provider_adapter_available,
                       credentials_reference_configured, signer_capability,
                       csc_reference_configured, transport_configured,
                       resilience_certified, contract_tests_certified,
                       jurisdiction_mapping, operation_supported,
                       requires_signer, requires_csc, external_evidence_id,
                       external_official, recorded_at
                FROM fm_commercial_homologation_evidence
                WHERE tenant_id = ? AND unit_id = ? AND environment = ?
                  AND provider_id = ? AND document_kind = ?
                  AND state_code = ? AND municipality_ibge_code = ?
                  AND operation = ?
                """,
                (
                    _normalized(tenant_id, "tenant_id"),
                    _normalized(unit_id, "unit_id"),
                    environment.value,
                    _normalized(provider_id, "provider_id"),
                    document_kind.value,
                    jurisdiction.state_code,
                    municipality,
                    _normalized(operation, "operation"),
                ),
            )
        )
        if row is None:
            return None
        persisted_municipality = text(row[6], "municipality_ibge_code") or None
        recorded = None if row[21] is None else dt(text(row[21], "recorded_at"))
        return HomologationEvidenceRecord(
            tenant_id=text(row[0], "tenant_id"),
            unit_id=text(row[1], "unit_id"),
            environment=FiscalEnvironment(text(row[2], "environment")),
            provider_id=text(row[3], "provider_id"),
            document_kind=FiscalDocumentKind(text(row[4], "document_kind")),
            jurisdiction=BrazilianJurisdiction(
                text(row[5], "state_code"), persisted_municipality
            ),
            operation=text(row[7], "operation"),
            provider_adapter_available=bool(integer(row[8], "provider_adapter_available")),
            credentials_reference_configured=bool(
                integer(row[9], "credentials_reference_configured")
            ),
            signer_capability=bool(integer(row[10], "signer_capability")),
            csc_reference_configured=bool(integer(row[11], "csc_reference_configured")),
            transport_configured=bool(integer(row[12], "transport_configured")),
            resilience_certified=bool(integer(row[13], "resilience_certified")),
            contract_tests_certified=bool(integer(row[14], "contract_tests_certified")),
            jurisdiction_mapping=bool(integer(row[15], "jurisdiction_mapping")),
            operation_supported=bool(integer(row[16], "operation_supported")),
            requires_signer=bool(integer(row[17], "requires_signer")),
            requires_csc=bool(integer(row[18], "requires_csc")),
            external_evidence_id=optional_text(row[19], "external_evidence_id"),
            external_official=bool(integer(row[20], "external_official")),
            recorded_at=recorded,
        )
