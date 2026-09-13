"""Runtime consumers for durable commercial configuration.

The classes in this module turn persisted customer configuration into runtime
policies without customer-specific branching. Legal/readiness authority remains
outside this module.
"""

from __future__ import annotations

from datetime import datetime

from kordena_fiscal.control_plane.commercial import (
    ProviderBindingResolver,
    ProviderRuntimePolicyConfig,
)
from kordena_fiscal.control_plane.commercial_models import (
    HomologationEvidenceRecord,
    NumberingConfiguration,
)
from kordena_fiscal.control_plane.service import ControlPlaneNotFoundError
from kordena_fiscal.domain import (
    BrazilianJurisdiction,
    ElectronicInvoiceModel,
    ExecutionScope,
    FiscalDocumentKind,
    FiscalEnvironment,
    FiscalValidationError,
    HostScope,
)
from kordena_fiscal.gateway import (
    FiscalProviderTransport,
    ProviderRequest,
    ProviderResponse,
    ProviderTimeoutPolicy,
    ProviderTransportResponse,
)
from kordena_fiscal.homologation import (
    HomologationEvidence,
    HomologationGateKey,
    TechnicalHomologationRule,
)
from kordena_fiscal.numbering import (
    FiscalNumberReservation,
    FiscalSequenceKey,
    FiscalSequenceStore,
)
from kordena_fiscal.persistence.ports import FiscalUnitOfWorkFactory
from kordena_fiscal.resilience.runtime import (
    CircuitBreakerPolicy,
    CircuitBreakerRegistry,
    JitterSource,
    MonotonicClock,
    ProviderExecutor,
    RandomJitterSource,
    ResilientProviderGateway,
    RetryPolicy,
    Sleeper,
    SystemMonotonicClock,
    SystemSleeper,
)
from kordena_fiscal.security import AuthenticatedCaller, WorkloadAuthenticator
from kordena_fiscal.vault import (
    EphemeralCscMaterial,
    EphemeralProviderCredentialsMaterial,
)


class DurableProviderRuntimePolicyResolver:
    """Resolve exact tenant/unit/environment/provider policies from durable state."""

    def __init__(self, unit_of_work_factory: FiscalUnitOfWorkFactory) -> None:
        self._unit_of_work_factory = unit_of_work_factory

    def resolve_config(
        self,
        *,
        scope: ExecutionScope,
        provider_id: str,
    ) -> ProviderRuntimePolicyConfig:
        provider = provider_id.strip().lower()
        if not provider:
            raise FiscalValidationError("provider_id must not be blank")
        with self._unit_of_work_factory() as uow:
            policy = uow.commercial.get_runtime_policy(
                tenant_id=scope.tenant_id,
                unit_id=scope.unit_id,
                environment=scope.environment,
                provider_id=provider,
            )
        if policy is None:
            raise ControlPlaneNotFoundError(
                "provider runtime policy is not configured for exact customer scope"
            )
        return policy

    def resolve_timeout_policy(
        self,
        *,
        scope: ExecutionScope,
        provider_id: str,
    ) -> ProviderTimeoutPolicy:
        policy = self.resolve_config(scope=scope, provider_id=provider_id)
        return ProviderTimeoutPolicy(
            connect_seconds=policy.connect_timeout_seconds,
            read_seconds=policy.read_timeout_seconds,
        )

    def resolve_retry_policy(
        self,
        *,
        scope: ExecutionScope,
        provider_id: str,
    ) -> RetryPolicy:
        policy = self.resolve_config(scope=scope, provider_id=provider_id)
        return RetryPolicy(
            max_attempts=policy.max_attempts,
            base_delay_seconds=policy.base_delay_seconds,
            max_delay_seconds=policy.max_delay_seconds,
            jitter_ratio=policy.jitter_ratio,
        )

    def resolve_circuit_policy(
        self,
        *,
        scope: ExecutionScope,
        provider_id: str,
    ) -> CircuitBreakerPolicy:
        policy = self.resolve_config(scope=scope, provider_id=provider_id)
        return CircuitBreakerPolicy(
            failure_threshold=policy.circuit_failure_threshold,
            recovery_timeout_seconds=policy.circuit_recovery_seconds,
            success_threshold=policy.circuit_success_threshold,
        )


class PolicyBoundFiscalProviderTransport:
    """Override composition-time timeout literals with exact durable policy."""

    def __init__(
        self,
        *,
        transport: FiscalProviderTransport,
        policy_resolver: DurableProviderRuntimePolicyResolver,
    ) -> None:
        self._transport = transport
        self._policy_resolver = policy_resolver

    def exchange(
        self,
        *,
        provider_id: str,
        request: ProviderRequest,
        credentials: EphemeralProviderCredentialsMaterial,
        csc: EphemeralCscMaterial | None,
        timeout: ProviderTimeoutPolicy,
    ) -> ProviderTransportResponse:
        del timeout
        configured_timeout = self._policy_resolver.resolve_timeout_policy(
            scope=request.scope,
            provider_id=provider_id,
        )
        return self._transport.exchange(
            provider_id=provider_id,
            request=request,
            credentials=credentials,
            csc=csc,
            timeout=configured_timeout,
        )


class DurablePolicyResilientProviderGateway:
    """Apply persisted retry/circuit policy for every exact provider/customer scope."""

    def __init__(
        self,
        *,
        executor: ProviderExecutor,
        policy_resolver: DurableProviderRuntimePolicyResolver,
        provider_selector: ProviderBindingResolver | None = None,
        clock: MonotonicClock | None = None,
        sleeper: Sleeper | None = None,
        jitter: JitterSource | None = None,
    ) -> None:
        self._executor = executor
        self._policy_resolver = policy_resolver
        self._provider_selector = provider_selector
        self._clock = clock or SystemMonotonicClock()
        self._sleeper = sleeper or SystemSleeper()
        self._jitter = jitter or RandomJitterSource()
        self._circuits: dict[
            tuple[str, str, str, str, ProviderRuntimePolicyConfig],
            CircuitBreakerRegistry,
        ] = {}

    def execute(
        self,
        request: ProviderRequest,
        *,
        provider_id: str | None = None,
    ) -> ProviderResponse:
        selected = provider_id.strip().lower() if provider_id is not None else None
        if selected is None and self._provider_selector is not None:
            selected = self._provider_selector.resolve_provider_id(
                scope=request.scope,
                document_kind=request.document_kind,
                jurisdiction=request.jurisdiction,
                operation=request.operation.value,
            )
        if not selected:
            raise FiscalValidationError(
                "durable resilience requires an explicit or configured provider"
            )
        config = self._policy_resolver.resolve_config(
            scope=request.scope,
            provider_id=selected,
        )
        key = (
            request.scope.tenant_id,
            request.scope.unit_id,
            request.scope.environment.value,
            selected,
            config,
        )
        circuits = self._circuits.get(key)
        if circuits is None:
            circuits = CircuitBreakerRegistry(
                policy=self._policy_resolver.resolve_circuit_policy(
                    scope=request.scope,
                    provider_id=selected,
                ),
                clock=self._clock,
            )
            self._circuits[key] = circuits
        gateway = ResilientProviderGateway(
            executor=self._executor,
            retry_policy=self._policy_resolver.resolve_retry_policy(
                scope=request.scope,
                provider_id=selected,
            ),
            circuits=circuits,
            sleeper=self._sleeper,
            jitter=self._jitter,
        )
        return gateway.execute(request, provider_id=selected)


class DurableNumberingConfigurationResolver:
    def __init__(self, unit_of_work_factory: FiscalUnitOfWorkFactory) -> None:
        self._unit_of_work_factory = unit_of_work_factory

    def resolve(
        self,
        *,
        scope: ExecutionScope,
        model: ElectronicInvoiceModel,
    ) -> NumberingConfiguration:
        with self._unit_of_work_factory() as uow:
            config = uow.commercial.get_numbering_configuration(
                tenant_id=scope.tenant_id,
                unit_id=scope.unit_id,
                environment=scope.environment,
                model=model,
            )
        if config is None or not config.enabled:
            raise ControlPlaneNotFoundError(
                "numbering configuration is not enabled for exact customer scope"
            )
        return config


class DurableConfiguredSequenceManager:
    """Reserve numbers using persisted series and bounds, not bootstrap literals."""

    def __init__(
        self,
        *,
        store: FiscalSequenceStore,
        resolver: DurableNumberingConfigurationResolver,
    ) -> None:
        self._store = store
        self._resolver = resolver

    def reserve(
        self,
        scope: ExecutionScope,
        *,
        model: ElectronicInvoiceModel,
    ) -> FiscalNumberReservation:
        config = self._resolver.resolve(scope=scope, model=model)
        key = FiscalSequenceKey.from_scope(
            scope,
            model=config.model,
            series=config.series,
        )
        return self._store.reserve_next(key, config.policy)


class DurableWorkloadAuthenticator:
    """Authenticate against durable hashed credentials with live revocation/rotation."""

    def __init__(self, unit_of_work_factory: FiscalUnitOfWorkFactory) -> None:
        self._unit_of_work_factory = unit_of_work_factory

    def authenticate(
        self,
        *,
        credential_id: str,
        presented_secret: str,
        now: datetime,
    ) -> AuthenticatedCaller:
        with self._unit_of_work_factory() as uow:
            record = uow.commercial.get_workload_credential(credential_id)
        if record is None:
            return WorkloadAuthenticator(()).authenticate(
                credential_id=credential_id,
                presented_secret=presented_secret,
                now=now,
            )
        return WorkloadAuthenticator((record,)).authenticate(
            credential_id=credential_id,
            presented_secret=presented_secret,
            now=now,
        )


class DurableFiscalBindingResolver:
    """Resolve S2S host scope through the durable binding repository."""

    def __init__(self, unit_of_work_factory: FiscalUnitOfWorkFactory) -> None:
        self._unit_of_work_factory = unit_of_work_factory

    def execution_scope(
        self,
        host_scope: HostScope,
        *,
        environment: FiscalEnvironment,
        correlation_id: str,
    ) -> ExecutionScope:
        with self._unit_of_work_factory() as uow:
            binding = uow.bindings.resolve(host_scope)
        return binding.to_execution_scope(
            environment=environment,
            correlation_id=correlation_id,
        )


class DurableHomologationEvidenceResolver:
    """Load exact persisted evidence and adapt it to the technical gate contract."""

    def __init__(self, unit_of_work_factory: FiscalUnitOfWorkFactory) -> None:
        self._unit_of_work_factory = unit_of_work_factory

    def resolve_record(
        self,
        *,
        tenant_id: str,
        unit_id: str,
        environment: FiscalEnvironment,
        provider_id: str,
        document_kind: FiscalDocumentKind,
        jurisdiction: BrazilianJurisdiction,
        operation: str,
    ) -> HomologationEvidenceRecord:
        with self._unit_of_work_factory() as uow:
            record = uow.commercial.get_homologation_evidence(
                tenant_id=tenant_id,
                unit_id=unit_id,
                environment=environment,
                provider_id=provider_id,
                document_kind=document_kind,
                jurisdiction=jurisdiction,
                operation=operation,
            )
        if record is None:
            raise ControlPlaneNotFoundError(
                "homologation evidence is not configured for exact customer scope"
            )
        return record

    def technical_rule(
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

        return TechnicalHomologationRule(
            key=HomologationGateKey(
                provider_id=record.provider_id,
                document_kind=record.document_kind,
                jurisdiction=record.jurisdiction,
                environment=record.environment,
                operation=ProviderOperation(record.operation),
            ),
            evidence=HomologationEvidence(
                provider_adapter_available=record.provider_adapter_available,
                credentials_reference_configured=record.credentials_reference_configured,
                signer_capability=record.signer_capability,
                csc_reference_configured=record.csc_reference_configured,
                transport_configured=record.transport_configured,
                resilience_certified=record.resilience_certified,
                contract_tests_certified=record.contract_tests_certified,
                jurisdiction_mapping=record.jurisdiction_mapping,
                operation_supported=record.operation_supported,
            ),
            requires_signer=record.requires_signer,
            requires_csc=record.requires_csc,
        )
