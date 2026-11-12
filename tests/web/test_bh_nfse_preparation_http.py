"""Authenticated BH Web preparation: no municipal POST or inferred authorization."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from kordena_fiscal.application.service import FiscalApplicationService
from kordena_fiscal.control_plane import FiscalOrganization, FiscalUnitRegistration
from kordena_fiscal.control_plane.commercial import ConfiguredFiscalOperation, ProviderBinding
from kordena_fiscal.domain import (
    BrazilianJurisdiction,
    CnaeCode,
    Cnpj,
    ExecutionScope,
    FiscalAddress,
    FiscalDocumentKind,
    FiscalEnvironment,
    FiscalProfile,
    StateRegistration,
    TaxRegimeCode,
)
from kordena_fiscal.gateway.nfse_nacional_homologation import (
    NACIONAL_HOMOLOGATION_PROVIDER_ID,
)
from kordena_fiscal.numbering import FiscalSequenceKey, InternalFiscalSequenceStream
from kordena_fiscal.persistence import SqliteFiscalDatabase
from kordena_fiscal.security.human_identity import (
    HumanAccount,
    HumanIdentityService,
    InMemoryHumanAccountRepository,
    InMemoryWebSessionRepository,
    PortalRole,
    ScryptPasswordHasher,
)
from kordena_fiscal.web import create_app
from kordena_fiscal.web.human_auth import CSRF_COOKIE, CSRF_HEADER
from kordena_fiscal.web.portal_runtime import DurableHumanPortalExecutor


def _database(path: Path, *, binding: str = NACIONAL_HOMOLOGATION_PROVIDER_ID):
    db = SqliteFiscalDatabase(path)
    db.initialize(enable_national_dps=True)
    bh = BrazilianJurisdiction("MG", "3106200")
    scope = ExecutionScope(
        tenant_id="tenant-bh", unit_id="unit-bh",
        environment=FiscalEnvironment.HOMOLOGATION,
        host_namespace="fm-nfcore", correlation_id="setup-bh",
    )
    with db() as uow:
        uow.control_plane.add_organization(FiscalOrganization(
            tenant_id="tenant-bh", legal_name="Synthetic BH Taxpayer",
        ))
        uow.control_plane.add_unit(FiscalUnitRegistration(
            tenant_id="tenant-bh", unit_id="unit-bh",
            display_name="Belo Horizonte",
            enabled_environments=frozenset({FiscalEnvironment.HOMOLOGATION}),
        ))
        uow.control_plane.add_profile(FiscalProfile(
            profile_id="bh-profile", scope=scope, cnpj=Cnpj("11222333000181"),
            legal_name="Synthetic BH Issuer Ltda",
            tax_regime=TaxRegimeCode.SIMPLES_NACIONAL,
            state_registration=StateRegistration("MG", "123456789"),
            primary_cnae=CnaeCode("6201501"),
            address=FiscalAddress(
                street="Rua Sintetica", number="10", district="Centro",
                municipality_name="Belo Horizonte", jurisdiction=bh,
                postal_code="30100000",
            ),
            effective_from=datetime.now(UTC) - timedelta(days=1),
        ))
        uow.commercial.put_provider_binding(ProviderBinding(
            binding_id="bh-national-bound", tenant_id="tenant-bh", unit_id="unit-bh",
            environment=FiscalEnvironment.HOMOLOGATION,
            document_kind=FiscalDocumentKind.NFSE,
            jurisdiction=bh, operation=ConfiguredFiscalOperation.AUTHORIZE,
            provider_id=binding,
        ))
        uow.commit()
    return db


def _client(db: SqliteFiscalDatabase, *, role: PortalRole) -> TestClient:
    password = "only-synthetic-bh-password"
    hasher = ScryptPasswordHasher()
    accounts = InMemoryHumanAccountRepository((HumanAccount(
        account_id="bh-user-" + role.value, email=role.value + "@example.com",
        password_hash=hasher.hash(password),
        tenant_id="tenant-bh", role=role, unit_ids=frozenset({"unit-bh"}),
    ),))
    identity = HumanIdentityService(
        accounts=accounts, sessions=InMemoryWebSessionRepository(),
        password_hasher=hasher,
    )
    web = TestClient(create_app(
        human_identity=identity,
        portal_executor=DurableHumanPortalExecutor(db),
    ), base_url="https://nfcore.test")
    result = web.post("/v1/auth/login", json={
        "email": role.value + "@example.com", "password": password,
    })
    assert result.status_code == 200
    return web


def _payload():
    return {
        "unit_id": "unit-bh", "environment": "homologation",
        "source_id": "bh-reviewed-service-1",
        "competence_date": datetime.now(UTC).date().isoformat(),
        "service_code": "0107", "national_taxation_code": "010701",
        "municipal_taxation_detail": "001", "nbs_code": "123456789",
        "description": "Servico sintetico BH revisado",
        "gross_amount": "100.00", "deduction_amount": "0.00",
        "iss_rate_fraction": "0.0300", "iss_withheld": False,
        "special_tax_regime": "0",
        "rule_reference": "urn:nfcore:bh:synthetic:reviewed-rule-2026",
        "rule_version": 1, "dps_series": 1,
        "fiscal_review_approved": True,
    }


def _post(web, payload, *, csrf=True, key="bh-http-review-1"):
    headers = {"Idempotency-Key": key}
    if csrf:
        token = web.cookies.get(CSRF_COOKIE)
        assert token
        headers[CSRF_HEADER] = token
    return web.post("/v1/portal/operations/prepareBhNfse", json=payload, headers=headers)


def test_bh_http_preparation_is_durable_idempotent_and_never_transmitted(tmp_path: Path):
    db = _database(tmp_path / "bh-preparation.sqlite")
    web = _client(db, role=PortalRole.OWNER)
    payload = _payload()
    first = _post(web, payload)
    assert first.status_code == 200, first.text
    data = first.json()
    assert data["dps_number"] == 1 and data["dps_series"] == 1
    assert data["municipality_ibge"] == "3106200"
    assert data["transmitted"] is False
    assert data["fiscal_authorization"] == "not_inferred_from_preparation"
    second = _post(web, payload, key="second-http-attempt")
    assert second.status_code == 200, second.text
    assert second.json()["replay"] is True
    assert second.json()["dps_number"] == 1

    app = FiscalApplicationService(db)
    prepared = app.load_prepared_nfse_authorization(
        ExecutionScope(
            "tenant-bh", "unit-bh", FiscalEnvironment.HOMOLOGATION,
            "different-correlation", "fm-nfcore",
        ), data["document_id"],
    )
    assert prepared.document.services[0].municipal_taxation_detail == "001"
    assert prepared.document.services[0].national_service_nbs == "123456789"
    assert prepared.document.special_tax_regime == "0"


@pytest.mark.parametrize("field,value", [
    ("municipal_taxation_detail", "not-CTISS"),
    ("nbs_code", "wrong-NBS"),
    ("special_tax_regime", "8"),
    ("environment", "production"),
    ("unit_id", "other-unit"),
    ("fiscal_review_approved", False),
])
def test_bh_http_fiscal_preflight_refuses_invalid_scope_or_review(
    tmp_path: Path, field: str, value: object,
):
    db = _database(tmp_path / (field + ".sqlite"))
    web = _client(db, role=PortalRole.OWNER)
    payload = _payload()
    payload[field] = value
    result = _post(web, payload)
    assert result.status_code in {400, 403, 409}
    with db() as uow:
        assert uow.dps_sequences.last_reserved(
            FiscalSequenceKey.from_scope(
                ExecutionScope(
                    "tenant-bh", "unit-bh", FiscalEnvironment.HOMOLOGATION,
                    "test", "fm-nfcore",
                ),
                model=InternalFiscalSequenceStream.NFSE_DPS,
                series=1,
                issuer_cnpj="11222333000181",
            )
        ) is None


def test_bh_http_session_csrf_rbac_and_provider_binding_are_mandatory(tmp_path: Path):
    good = _database(tmp_path / "bh-auth.sqlite")
    owner = _client(good, role=PortalRole.OWNER)
    no_csrf = _post(owner, _payload(), csrf=False)
    assert no_csrf.status_code in {401, 403}
    auditor = _client(good, role=PortalRole.AUDITOR)
    denied = _post(auditor, _payload())
    assert denied.status_code in {401, 403}
    different = _database(tmp_path / "bh-wrong-provider.sqlite", binding="unapproved")
    rejected = _post(_client(different, role=PortalRole.OWNER), _payload())
    assert rejected.status_code == 400


def test_bh_http_mutated_review_never_reserves_second_dps(tmp_path: Path):
    db = _database(tmp_path / "bh-conflict.sqlite")
    web = _client(db, role=PortalRole.OWNER)
    assert _post(web, _payload()).status_code == 200
    changed = _payload()
    changed["municipal_taxation_detail"] = "002"
    assert _post(web, changed).status_code == 409
