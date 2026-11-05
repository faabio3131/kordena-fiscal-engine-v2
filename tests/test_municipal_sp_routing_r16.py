"""SP R16 provider selection: canonical persistence is the only authority."""
from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from kordena_fiscal.domain import (
    BrazilianJurisdiction,
    ExecutionScope,
    FiscalDocumentKind,
    FiscalEnvironment,
)
from kordena_fiscal.gateway.municipal_sp_routing import (
    SP_MUNICIPAL_CANDIDATES,
    GovernedSpMunicipalProviderResolver,
)
from kordena_fiscal.gateway.provider import (
    ProviderSelectionResolver,
    UnsupportedProviderError,
)


def _scope(
    tenant: str = "tenant-1", unit: str = "unit-1",
    env: FiscalEnvironment = FiscalEnvironment.HOMOLOGATION,
    host: str | None = "nfcore",
) -> ExecutionScope:
    return ExecutionScope(
        host_namespace=host, tenant_id=tenant, unit_id=unit,
        environment=env, correlation_id="r16",
    )


@dataclass
class _CanonicalBindingResolver:
    """Test double for existing DurableProviderBindingResolver contract."""

    approved: dict[tuple[str, str, FiscalEnvironment, str, str], str]
    calls: list[tuple[str, str, FiscalEnvironment, str, str]] = field(default_factory=list)

    def resolve_provider_id(
        self, *, scope: ExecutionScope, document_kind: FiscalDocumentKind,
        jurisdiction: BrazilianJurisdiction, operation: str,
    ) -> str:
        assert document_kind is FiscalDocumentKind.NFSE
        assert jurisdiction.municipality_ibge_code is not None
        key = (scope.tenant_id, scope.unit_id, scope.environment,
               jurisdiction.municipality_ibge_code, operation)
        self.calls.append(key)
        if key not in self.approved:
            raise UnsupportedProviderError("no durable binding")
        return self.approved[key]


def _resolve(
    router: GovernedSpMunicipalProviderResolver, scope: ExecutionScope,
    ibge: str = "3550308", kind: FiscalDocumentKind = FiscalDocumentKind.NFSE,
    operation: str = "authorize", state: str = "SP",
) -> str:
    return router.resolve_provider_id(
        scope=scope, document_kind=kind,
        jurisdiction=BrazilianJurisdiction(state, ibge), operation=operation,
    )


def test_all_22_municipal_ibge_codes_are_registered() -> None:
    assert set(SP_MUNICIPAL_CANDIDATES) == {
        "3505708", "3550308", "3509502", "3552205", "3518800",
        "3548500", "3548807", "3525904", "3552502", "3547304",
        "3534401", "3522505", "3525003", "3528502", "3503901",
        "3527306", "3556206", "3523909", "3545209", "3531803",
        "3518701", "3551009",
    }


def test_routes_via_existing_provider_selection_protocol() -> None:
    canonical = _CanonicalBindingResolver({
        ("tenant-1", "unit-1", FiscalEnvironment.HOMOLOGATION,
         "3550308", "authorize"): "nota-paulistana"
    })
    router = GovernedSpMunicipalProviderResolver(canonical_resolver=canonical)
    selected: ProviderSelectionResolver = router
    assert selected.resolve_provider_id(
        scope=_scope(), document_kind=FiscalDocumentKind.NFSE,
        jurisdiction=BrazilianJurisdiction("SP", "3550308"),
        operation="authorize",
    ) == "nota-paulistana"
    assert len(canonical.calls) == 1


def test_no_provider_is_selected_from_catalog_without_a_durable_binding() -> None:
    canonical = _CanonicalBindingResolver({})
    router = GovernedSpMunicipalProviderResolver(canonical_resolver=canonical)
    with pytest.raises(UnsupportedProviderError, match="durable"):
        _resolve(router, _scope())
    assert len(canonical.calls) == 1


def test_candidate_family_never_overrides_governed_provider_choice() -> None:
    canonical = _CanonicalBindingResolver({
        ("tenant-1", "unit-1", FiscalEnvironment.HOMOLOGATION,
         "3505708", "authorize"): "future-vetted-transport"
    })
    router = GovernedSpMunicipalProviderResolver(canonical_resolver=canonical)
    assert _resolve(router, _scope(), ibge="3505708") == "future-vetted-transport"


@pytest.mark.parametrize(
    "scope",
    [
        _scope(tenant="other-tenant"),
        _scope(unit="other-unit"),
        _scope(env=FiscalEnvironment.PRODUCTION),
    ],
)
def test_tenant_unit_environment_isolation(scope: ExecutionScope) -> None:
    canonical = _CanonicalBindingResolver({
        ("tenant-1", "unit-1", FiscalEnvironment.HOMOLOGATION,
         "3550308", "authorize"): "nota-paulistana"
    })
    router = GovernedSpMunicipalProviderResolver(canonical_resolver=canonical)
    with pytest.raises(UnsupportedProviderError):
        _resolve(router, scope)


@pytest.mark.parametrize(
    ("municipality", "kind", "operation", "state"),
    [
        ("3550308", FiscalDocumentKind.NFE, "authorize", "SP"),
        ("0000000", FiscalDocumentKind.NFSE, "authorize", "SP"),
        ("3550308", FiscalDocumentKind.NFSE, "invalid", "SP"),
        ("3550308", FiscalDocumentKind.NFSE, "authorize", "RJ"),
    ],
)
def test_rejects_out_of_scope_municipality_kind_operation_and_state(
    municipality: str, kind: FiscalDocumentKind, operation: str, state: str,
) -> None:
    canonical = _CanonicalBindingResolver({})
    router = GovernedSpMunicipalProviderResolver(canonical_resolver=canonical)
    with pytest.raises(UnsupportedProviderError):
        _resolve(router, _scope(), municipality, kind, operation, state)
    assert canonical.calls == []


def test_missing_host_authority_rejected_before_db_lookup() -> None:
    canonical = _CanonicalBindingResolver({})
    router = GovernedSpMunicipalProviderResolver(canonical_resolver=canonical)
    with pytest.raises(UnsupportedProviderError):
        _resolve(router, _scope(host=None))
    assert canonical.calls == []


def test_taker_municipality_cannot_change_issuer_binding() -> None:
    canonical = _CanonicalBindingResolver({
        ("tenant-1", "unit-1", FiscalEnvironment.HOMOLOGATION,
         "3550308", "authorize"): "nota-paulistana"
    })
    router = GovernedSpMunicipalProviderResolver(canonical_resolver=canonical)
    assert _resolve(router, _scope(), ibge="3550308") == "nota-paulistana"
    with pytest.raises(UnsupportedProviderError):
        _resolve(router, _scope(), ibge="3509502")


def test_cannot_construct_without_canonical_authority() -> None:
    with pytest.raises(TypeError):
        GovernedSpMunicipalProviderResolver(canonical_resolver=None)  # type: ignore[arg-type]


def test_new_sp_city_is_onboarded_without_code_change() -> None:
    """R16 must not require a deploy to connect an IBGE outside the pilot catalog."""
    new_code = "3500105"  # Adamantina/SP
    assert new_code not in SP_MUNICIPAL_CANDIDATES
    canonical = _CanonicalBindingResolver({
        ("tenant-1", "unit-1", FiscalEnvironment.HOMOLOGATION,
         new_code, "authorize"): "approved-next-city"
    })
    router = GovernedSpMunicipalProviderResolver(canonical_resolver=canonical)
    assert _resolve(router, _scope(), ibge=new_code) == "approved-next-city"
