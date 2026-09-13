from pathlib import Path


def write_if_changed(path_name: str, text: str) -> None:
    path = Path(path_name)
    current = path.read_text(encoding="utf-8")
    if text != current:
        path.write_text(text, encoding="utf-8")


# Extend unmerged V5 with the remaining durable B0 runtime state.
path = Path("src/kordena_fiscal/persistence/sqlite.py")
text = path.read_text(encoding="utf-8")
if "CREATE TABLE fm_commercial_numbering_configurations" not in text:
    tail = '''            """,
        ),
    ),
)


class SqliteFiscalUnitOfWork:'''
    tables = '''            """,
            """
            CREATE TABLE fm_commercial_numbering_configurations (
                tenant_id TEXT NOT NULL,
                unit_id TEXT NOT NULL,
                environment TEXT NOT NULL,
                model INTEGER NOT NULL,
                series INTEGER NOT NULL,
                first_number INTEGER NOT NULL,
                max_number INTEGER,
                enabled INTEGER NOT NULL,
                PRIMARY KEY (tenant_id, unit_id, environment, model),
                FOREIGN KEY (tenant_id, unit_id)
                    REFERENCES fm_control_plane_units(tenant_id, unit_id)
            )
            """,
            """
            CREATE TABLE fm_commercial_workload_credentials (
                credential_id TEXT PRIMARY KEY,
                caller_id TEXT NOT NULL,
                host_namespace TEXT NOT NULL,
                capabilities_json TEXT NOT NULL,
                grants_json TEXT NOT NULL,
                secret_sha256 TEXT NOT NULL,
                valid_from TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                revoked INTEGER NOT NULL
            )
            """,
            """
            CREATE TABLE fm_commercial_homologation_evidence (
                tenant_id TEXT NOT NULL,
                unit_id TEXT NOT NULL,
                environment TEXT NOT NULL,
                provider_id TEXT NOT NULL,
                document_kind TEXT NOT NULL,
                state_code TEXT NOT NULL,
                municipality_ibge_code TEXT NOT NULL DEFAULT '',
                operation TEXT NOT NULL,
                provider_adapter_available INTEGER NOT NULL,
                credentials_reference_configured INTEGER NOT NULL,
                signer_capability INTEGER NOT NULL,
                csc_reference_configured INTEGER NOT NULL,
                transport_configured INTEGER NOT NULL,
                resilience_certified INTEGER NOT NULL,
                contract_tests_certified INTEGER NOT NULL,
                jurisdiction_mapping INTEGER NOT NULL,
                operation_supported INTEGER NOT NULL,
                requires_signer INTEGER NOT NULL,
                requires_csc INTEGER NOT NULL,
                external_evidence_id TEXT,
                external_official INTEGER NOT NULL,
                recorded_at TEXT,
                PRIMARY KEY (
                    tenant_id, unit_id, environment, provider_id, document_kind,
                    state_code, municipality_ibge_code, operation
                ),
                FOREIGN KEY (tenant_id, unit_id)
                    REFERENCES fm_control_plane_units(tenant_id, unit_id)
            )
            """,
        ),
    ),
)


class SqliteFiscalUnitOfWork:'''
    if tail not in text:
        raise SystemExit("migration V5 tail marker not found")
    text = text.replace(tail, tables, 1)
write_if_changed(str(path), text)


# Persistence ports.
path = Path("src/kordena_fiscal/persistence/ports.py")
text = path.read_text(encoding="utf-8")
if "HomologationEvidenceRecord" not in text:
    needle = '''        WebhookDestinationConfig,
    )
'''
    replacement = needle + '''    from kordena_fiscal.control_plane.commercial_models import (
        HomologationEvidenceRecord,
        NumberingConfiguration,
    )
    from kordena_fiscal.security import WorkloadCredentialRecord
'''
    if needle not in text:
        raise SystemExit("ports TYPE_CHECKING marker not found")
    text = text.replace(needle, replacement, 1)
if "def put_numbering_configuration" not in text:
    needle = '''    def get_runtime_policy(
        self,
        *,
        tenant_id: str,
        unit_id: str,
        environment: FiscalEnvironment,
        provider_id: str,
    ) -> ProviderRuntimePolicyConfig | None: ...
'''
    replacement = needle + '''
    def put_numbering_configuration(
        self,
        config: NumberingConfiguration,
    ) -> NumberingConfiguration: ...

    def get_numbering_configuration(
        self,
        *,
        tenant_id: str,
        unit_id: str,
        environment: FiscalEnvironment,
        model: object,
    ) -> NumberingConfiguration | None: ...

    def put_workload_credential(
        self,
        record: WorkloadCredentialRecord,
    ) -> WorkloadCredentialRecord: ...

    def get_workload_credential(
        self,
        credential_id: str,
    ) -> WorkloadCredentialRecord | None: ...

    def put_homologation_evidence(
        self,
        record: HomologationEvidenceRecord,
    ) -> HomologationEvidenceRecord: ...

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
    ) -> HomologationEvidenceRecord | None: ...
'''
    if needle not in text:
        raise SystemExit("ports commercial store marker not found")
    text = text.replace(needle, replacement, 1)
write_if_changed(str(path), text)


# SQLite commercial repository imports and methods.
path = Path("src/kordena_fiscal/persistence/sqlite_commercial.py")
text = path.read_text(encoding="utf-8")
if "import json\n" not in text:
    text = text.replace("import sqlite3\n", "import json\nimport sqlite3\n", 1)
if "from kordena_fiscal.control_plane.commercial_models import" not in text:
    marker = '''from kordena_fiscal.control_plane.commercial import (
    ConfiguredFiscalOperation,
    ProviderBinding,
    ProviderRuntimePolicyConfig,
    UnitModuleBinding,
    WebhookDestinationConfig,
)
'''
    addition = marker + '''from kordena_fiscal.control_plane.commercial_models import (
    HomologationEvidenceRecord,
    NumberingConfiguration,
)
'''
    if marker not in text:
        raise SystemExit("sqlite commercial import marker not found")
    text = text.replace(marker, addition, 1)
if "    ElectronicInvoiceModel,\n" not in text:
    text = text.replace("    CestCode,\n", "    CestCode,\n    ElectronicInvoiceModel,\n", 1)
if "    HostNamespace,\n" not in text:
    text = text.replace("    Gtin,\n", "    Gtin,\n    HostNamespace,\n", 1)
if "from kordena_fiscal.security import (" not in text:
    marker = "\nfrom ._sqlite_common import dt, integer, iso, one_row, optional_text, text\n"
    security_import = '''
from kordena_fiscal.security import (
    CallerIdentity,
    FiscalCapability,
    HostScopeGrant,
    WorkloadCredentialRecord,
)
'''
    if marker not in text:
        raise SystemExit("sqlite commercial common import marker not found")
    text = text.replace(marker, security_import + marker, 1)
if "def put_numbering_configuration" not in text:
    text += '''

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
'''
write_if_changed(str(path), text)


# S2S authorizer accepts a structural resolver, including durable bindings.
path = Path("src/kordena_fiscal/security/s2s.py")
text = path.read_text(encoding="utf-8")
text = text.replace("from typing import Protocol\n", "from typing import Protocol, runtime_checkable\n")
text = text.replace("    FiscalBindingRegistry,\n", "")
if "class FiscalExecutionScopeResolver" not in text:
    marker = '''class SecurityAuditSink(Protocol):
    def record(self, record: SecurityAuditRecord) -> None: ...
'''
    resolver = '''@runtime_checkable
class FiscalExecutionScopeResolver(Protocol):
    def execution_scope(
        self,
        host_scope: HostScope,
        *,
        environment: FiscalEnvironment,
        correlation_id: str,
    ) -> ExecutionScope: ...


''' + marker
    if marker not in text:
        raise SystemExit("S2S protocol insertion marker not found")
    text = text.replace(marker, resolver, 1)
text = text.replace(
    "        bindings: FiscalBindingRegistry,\n",
    "        bindings: FiscalExecutionScopeResolver,\n",
    1,
)
text = text.replace(
    '''        if not isinstance(bindings, FiscalBindingRegistry):
            raise FiscalValidationError("bindings must be FiscalBindingRegistry")''',
    '''        if not isinstance(bindings, FiscalExecutionScopeResolver):
            raise FiscalValidationError(
                "bindings must implement FiscalExecutionScopeResolver"
            )''',
    1,
)
write_if_changed(str(path), text)


# Strict typing cleanup in the runtime configuration layer.
path = Path("src/kordena_fiscal/control_plane/commercial_runtime.py")
text = path.read_text(encoding="utf-8")
text = text.replace("from dataclasses import dataclass\n", "")
text = text.replace("from typing import Protocol\n", "")
if "    BrazilianJurisdiction,\n" not in text:
    text = text.replace(
        "from kordena_fiscal.domain import (\n",
        "from kordena_fiscal.domain import (\n    BrazilianJurisdiction,\n    ElectronicInvoiceModel,\n",
        1,
    )
text = text.replace(
    "        model,\n    ) -> NumberingConfiguration:",
    "        model: ElectronicInvoiceModel,\n    ) -> NumberingConfiguration:",
)
text = text.replace(
    "    def reserve(self, scope: ExecutionScope, *, model) -> FiscalNumberReservation:",
    '''    def reserve(
        self,
        scope: ExecutionScope,
        *,
        model: ElectronicInvoiceModel,
    ) -> FiscalNumberReservation:''',
)
text = text.replace(
    "        jurisdiction,\n        operation: str,\n    ) -> HomologationEvidenceRecord:",
    "        jurisdiction: BrazilianJurisdiction,\n        operation: str,\n    ) -> HomologationEvidenceRecord:",
)
old = '''    def technical_rule(self, **kwargs) -> TechnicalHomologationRule:
        record = self.resolve_record(**kwargs)
        from kordena_fiscal.gateway import ProviderOperation
'''
new = '''    def technical_rule(
        self,
        *,
        tenant_id: str,
        unit_id: str,
        environment: FiscalEnvironment,
        provider_id: str,
        document_kind: FiscalDocumentKind,
        jurisdiction: BrazilianJurisdiction,
        operation: str,
    ) -> TechnicalHomologationRule:
        record = self.resolve_record(
            tenant_id=tenant_id,
            unit_id=unit_id,
            environment=environment,
            provider_id=provider_id,
            document_kind=document_kind,
            jurisdiction=jurisdiction,
            operation=operation,
        )
        from kordena_fiscal.gateway import ProviderOperation
'''
if old not in text:
    raise SystemExit("commercial runtime technical_rule marker not found")
text = text.replace(old, new, 1)
write_if_changed(str(path), text)


# Historical V5 rollback helper accounts for every V5 table.
path = Path("tests/events/test_inbox_migration.py")
text = path.read_text(encoding="utf-8")
if '"fm_commercial_homologation_evidence"' not in text:
    text = text.replace(
        '''    for table in (
        "fm_commercial_provider_runtime_policies",''',
        '''    for table in (
        "fm_commercial_homologation_evidence",
        "fm_commercial_workload_credentials",
        "fm_commercial_numbering_configurations",
        "fm_commercial_provider_runtime_policies",''',
        1,
    )
write_if_changed(str(path), text)
