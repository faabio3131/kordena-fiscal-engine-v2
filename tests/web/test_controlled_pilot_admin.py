"""Controlled Pilot admin route reuses the portal's own session/CSRF authority.

Covers: platform-admin gating, the activation + readiness-report round trip
against a real SQLite-backed ControlledPilotGovernanceService wired with the
real production provider catalog, and the fail-closed "nothing configured"
case for an unrelated tenant/unit.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Import order matters here: kordena_fiscal.persistence must finish importing
# before kordena_fiscal.control_plane's lazy ``__getattr__`` pulls in
# .commercial, or the two modules' pre-existing circular dependency on each
# other raises a partial-init ImportError during collection.
import kordena_fiscal.persistence  # noqa: F401
from kordena_fiscal.control_plane import (
    AdminPrincipal,
    CommercialConfigurationService,
    ConfiguredFiscalOperation,
    ControlPlanePermission,
    DurableControlPlaneService,
    FiscalUnitRegistration,
    ProviderBinding,
    ProviderRuntimePolicyConfig,
    SecretReference,
    SecretReferenceKind,
)
from kordena_fiscal.control_plane.commercial_admin import CommercialRuntimeConfigurationService
from kordena_fiscal.control_plane.commercial_models import HomologationEvidenceRecord
from kordena_fiscal.domain import BrazilianJurisdiction, FiscalDocumentKind, FiscalEnvironment
from kordena_fiscal.persistence import SqliteFiscalDatabase
from kordena_fiscal.runtime.controlled_pilot_catalog import (
    SEFAZ_SP_HOMOLOGATION_PROVIDER_ID,
    build_controlled_pilot_provider_catalog,
)
from kordena_fiscal.runtime.controlled_pilots import ControlledPilotGovernanceService
from kordena_fiscal.runtime.homologation_readiness import (
    DurableHomologationEnvironmentReadinessService,
)
from kordena_fiscal.web import controlled_pilot_admin as admin

SP = BrazilianJurisdiction("SP")
TENANT = "tenant-pilot-admin"
UNIT = "unit-pilot-admin"


def _seed_admin() -> AdminPrincipal:
    return AdminPrincipal(
        actor_id="seed-admin",
        permissions=frozenset(
            {
                ControlPlanePermission.ORGANIZATION_WRITE,
                ControlPlanePermission.UNIT_WRITE,
                ControlPlanePermission.SECRET_REFERENCE_WRITE,
                ControlPlanePermission.COMMERCIAL_CONFIG_WRITE,
            }
        ),
        global_scope=True,
    )


def _database(tmp_path) -> SqliteFiscalDatabase:
    database = SqliteFiscalDatabase(tmp_path / "pilot-admin.sqlite3")
    database.initialize()
    control = DurableControlPlaneService(database)
    control.onboard_organization(
        actor=_seed_admin(), tenant_id=TENANT,
        legal_name="Synthetic Pilot Admin Tenant", correlation_id="corr-org",
    )
    control.onboard_unit(
        actor=_seed_admin(),
        registration=FiscalUnitRegistration(
            tenant_id=TENANT, unit_id=UNIT, display_name="Synthetic Pilot Admin Unit",
            enabled_environments=frozenset({FiscalEnvironment.HOMOLOGATION}),
        ),
        correlation_id="corr-unit",
    )
    for kind, provider_id, suffix in (
        (SecretReferenceKind.CERTIFICATE, None, "certificate"),
        (SecretReferenceKind.CREDENTIALS, SEFAZ_SP_HOMOLOGATION_PROVIDER_ID, "credentials"),
    ):
        control.bind_secret_reference(
            actor=_seed_admin(),
            reference=SecretReference(
                reference_id=f"ref:synthetic/pilot-admin/{suffix}",
                kind=kind, tenant_id=TENANT, unit_id=UNIT,
                environment=FiscalEnvironment.HOMOLOGATION, provider_id=provider_id,
            ),
            correlation_id=f"corr-{suffix}",
        )
    commercial = CommercialConfigurationService(database)
    commercial.set_runtime_policy(
        actor=_seed_admin(),
        policy=ProviderRuntimePolicyConfig(
            policy_id="policy-pilot-admin", tenant_id=TENANT, unit_id=UNIT,
            environment=FiscalEnvironment.HOMOLOGATION,
            provider_id=SEFAZ_SP_HOMOLOGATION_PROVIDER_ID,
            connect_timeout_seconds=5, read_timeout_seconds=15, max_attempts=2,
            base_delay_seconds=0.1, max_delay_seconds=0.5, jitter_ratio=0,
            circuit_failure_threshold=2, circuit_recovery_seconds=10,
        ),
    )
    commercial.set_provider_binding(
        actor=_seed_admin(),
        binding=ProviderBinding(
            binding_id="binding-pilot-admin", tenant_id=TENANT, unit_id=UNIT,
            environment=FiscalEnvironment.HOMOLOGATION, document_kind=FiscalDocumentKind.NFE,
            jurisdiction=SP, operation=ConfiguredFiscalOperation.AUTHORIZE,
            provider_id=SEFAZ_SP_HOMOLOGATION_PROVIDER_ID,
        ),
    )
    CommercialRuntimeConfigurationService(database).set_homologation_evidence(
        actor=_seed_admin(),
        record=HomologationEvidenceRecord(
            tenant_id=TENANT, unit_id=UNIT, environment=FiscalEnvironment.HOMOLOGATION,
            provider_id=SEFAZ_SP_HOMOLOGATION_PROVIDER_ID, document_kind=FiscalDocumentKind.NFE,
            jurisdiction=SP, operation="authorize", provider_adapter_available=True,
            credentials_reference_configured=True, signer_capability=True,
            csc_reference_configured=False, transport_configured=True,
            resilience_certified=True, contract_tests_certified=True,
            jurisdiction_mapping=True, operation_supported=True,
        ),
    )
    return database


def _service(database: SqliteFiscalDatabase) -> ControlledPilotGovernanceService:
    readiness = DurableHomologationEnvironmentReadinessService(
        database, provider_catalog=build_controlled_pilot_provider_catalog(),
    )
    return ControlledPilotGovernanceService(database, readiness=readiness)


def _app(
    monkeypatch: pytest.MonkeyPatch, service: ControlledPilotGovernanceService, *, is_admin: bool
):
    authority = SimpleNamespace(
        account=SimpleNamespace(account_id="admin-1", platform_admin=is_admin),
    )

    def fake_authenticated(request, identity, *, now):
        return authority

    def fake_csrf(request, identity, authority_):
        return None

    monkeypatch.setattr(admin, "_authenticated", fake_authenticated)
    monkeypatch.setattr(admin, "_csrf", fake_csrf)
    app = FastAPI()
    app.include_router(admin.create_controlled_pilot_admin_router(object(), service))
    return TestClient(app)


def _payload(*, pilot_id: str = "pilot-admin-01", tenant_id: str = TENANT, unit_id: str = UNIT):
    return {
        "pilot_id": pilot_id,
        "tenant_id": tenant_id,
        "unit_id": unit_id,
        "document_kind": "nfe",
        "jurisdiction": {"state_code": "SP"},
        "provider_id": SEFAZ_SP_HOMOLOGATION_PROVIDER_ID,
        "allowed_operations": ["authorize"],
    }


def test_rejects_non_platform_admin(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    database = _database(tmp_path)
    client = _app(monkeypatch, _service(database), is_admin=False)
    response = client.post("/admin/controlled-pilots/activate", json=_payload())
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "PLATFORM_ADMIN_REQUIRED"


def test_activate_then_assess_fully_ready(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    database = _database(tmp_path)
    client = _app(monkeypatch, _service(database), is_admin=True)

    activate = client.post("/admin/controlled-pilots/activate", json=_payload())
    assert activate.status_code == 200
    body = activate.json()
    assert body["status"] == "activated"
    assert body["internal_ready"] is True
    # No real official SEFAZ-SP homologation evidence has been recorded yet
    # (that is exactly the real gap documented for tomorrow's pilot: the
    # accountant's real A1 certificate), so this stays fail-closed too.
    assert body["official_evidence_complete"] is False
    assert body["external_reasons"] == ["external_official_evidence_missing:authorize"]

    assess = client.post("/admin/controlled-pilots/assess", json=_payload())
    assert assess.status_code == 200
    assert assess.json()["internal_ready"] is True

    deactivate = client.post("/admin/controlled-pilots/deactivate", json=_payload())
    assert deactivate.status_code == 200
    assert deactivate.json()["status"] == "deactivated"


def test_assess_fails_closed_for_unconfigured_tenant(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _database(tmp_path)
    client = _app(monkeypatch, _service(database), is_admin=True)
    response = client.post(
        "/admin/controlled-pilots/assess",
        json=_payload(pilot_id="pilot-unconfigured", tenant_id="tenant-never-onboarded",
                       unit_id="unit-never-onboarded"),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["internal_ready"] is False
    assert body["internal_reasons"] == ["pilot_provider_mismatch:authorize"]


def test_invalid_payload_returns_400(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    database = _database(tmp_path)
    client = _app(monkeypatch, _service(database), is_admin=True)
    payload = _payload()
    payload["document_kind"] = "not-a-real-kind"
    response = client.post("/admin/controlled-pilots/activate", json=payload)
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "INVALID_PILOT_SCOPE"
