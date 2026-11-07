"""Governed lookup of the certificate binding on file for a tenant/unit scope.

Covers NFV1 "piloto contábil" item 1: cadastro governado de certificado A1/PKCS#12
por tenant/unidade, validacao de expiracao e rotacao/revogacao. Reuses the existing
SecretBinding/SecretBindingAdministration authority; this does not create a second
certificate registry and never stores private key or password material.
"""

from __future__ import annotations

import os
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import psycopg
import pytest

from kordena_fiscal.persistence.postgres import PostgresFiscalDatabase
from kordena_fiscal.persistence.sqlite import SqliteFiscalDatabase
from kordena_fiscal.runtime.secret_manager import SecretBindingAdministration
from kordena_fiscal.security.human_identity import AuthenticatedHuman, HumanAccount, PortalRole
from kordena_fiscal.security.secret_binding import SecretBinding, certificate_binding_status
from kordena_fiscal.security.secrets import SecretResolutionError
from kordena_fiscal.security.signing import CertificateStatus

NOW = datetime(2026, 11, 7, 12, tzinfo=UTC)
_DEFAULT_NOT_AFTER = object()


@pytest.fixture(params=["sqlite", "postgres"])
def database(request, tmp_path):
    if request.param == "sqlite":
        db = SqliteFiscalDatabase(tmp_path / "cert-scope-synthetic.db")
    else:
        dsn = os.environ.get("NFCORE_TEST_POSTGRES_DSN")
        if not dsn:
            pytest.skip("NFCORE_TEST_POSTGRES_DSN required for real PostgreSQL CI")
        with psycopg.connect(dsn, autocommit=True) as connection:
            connection.execute("DROP SCHEMA public CASCADE")
            connection.execute("CREATE SCHEMA public")
        db = PostgresFiscalDatabase(dsn)
    db.initialize()
    try:
        yield db
    finally:
        if isinstance(db, PostgresFiscalDatabase):
            db.close()


def _certificate_binding(
    *,
    reference_id: str = "ref:scope/certificate",
    tenant_id: str = "pilot-tenant",
    unit_id: str = "pilot-unit",
    fiscal_environment: str = "homologation",
    not_after: datetime | None | object = _DEFAULT_NOT_AFTER,
    state: str = "active",
) -> SecretBinding:
    resolved_not_after = NOW + timedelta(days=90) if not_after is _DEFAULT_NOT_AFTER else not_after
    return SecretBinding(
        reference_id=reference_id,
        tenant_id=tenant_id,
        unit_id=unit_id,
        purpose="document-signing",
        runtime_environment="staging",
        fiscal_environment=fiscal_environment,
        provider_id=None,
        workload_id="nfcore-api",
        kind="certificate",
        canonical_version="fiscal-v1",
        resource="projects/nfcore-synthetic/secrets/scope-certificate",
        cloud_version="1",
        state=state,
        not_after=resolved_not_after,
    )


def _actor() -> AuthenticatedHuman:
    account = HumanAccount(
        "pilot-admin",
        "pilot-admin@example.test",
        "synthetic-hash",
        "pilot-tenant",
        PortalRole.OWNER,
        platform_admin=True,
    )
    return AuthenticatedHuman(
        account, "synthetic-session", "synthetic-csrf", NOW + timedelta(days=1)
    )


def _register(database, binding: SecretBinding, *, expected_revision: int = 0) -> None:
    SecretBindingAdministration(database, clock=lambda: NOW).put(
        actor=_actor(),
        binding=binding,
        expected_revision=expected_revision,
        correlation_id="cert-scope-registry-synthetic",
    )


def test_no_binding_registered_returns_none(database) -> None:
    administration = SecretBindingAdministration(database, clock=lambda: NOW)
    result = administration.active_certificate_for_scope(
        tenant_id="pilot-tenant", unit_id="pilot-unit", fiscal_environment="homologation"
    )
    assert result is None


def test_registered_certificate_is_found_by_scope(database) -> None:
    binding = _certificate_binding()
    _register(database, binding)
    administration = SecretBindingAdministration(database, clock=lambda: NOW)
    result = administration.active_certificate_for_scope(
        tenant_id="pilot-tenant", unit_id="pilot-unit", fiscal_environment="homologation"
    )
    assert result == binding


def test_wrong_tenant_unit_or_environment_does_not_match(database) -> None:
    binding = _certificate_binding()
    _register(database, binding)
    administration = SecretBindingAdministration(database, clock=lambda: NOW)
    assert (
        administration.active_certificate_for_scope(
            tenant_id="other-tenant", unit_id="pilot-unit", fiscal_environment="homologation"
        )
        is None
    )
    assert (
        administration.active_certificate_for_scope(
            tenant_id="pilot-tenant", unit_id="other-unit", fiscal_environment="homologation"
        )
        is None
    )
    assert (
        administration.active_certificate_for_scope(
            tenant_id="pilot-tenant", unit_id="pilot-unit", fiscal_environment="production"
        )
        is None
    )


def test_revoked_binding_is_excluded(database) -> None:
    binding = _certificate_binding()
    _register(database, binding)
    revoked = replace(binding, revision=2, state="revoked")
    _register(database, revoked, expected_revision=1)
    administration = SecretBindingAdministration(database, clock=lambda: NOW)
    result = administration.active_certificate_for_scope(
        tenant_id="pilot-tenant", unit_id="pilot-unit", fiscal_environment="homologation"
    )
    assert result is None


def test_rotation_replaces_active_certificate_for_the_scope(database) -> None:
    old = _certificate_binding(reference_id="ref:scope/certificate-old")
    _register(database, old)
    revoked_old = replace(old, revision=2, state="revoked")
    _register(database, revoked_old, expected_revision=1)
    new = _certificate_binding(
        reference_id="ref:scope/certificate-new", not_after=NOW + timedelta(days=365)
    )
    _register(database, new)
    administration = SecretBindingAdministration(database, clock=lambda: NOW)
    result = administration.active_certificate_for_scope(
        tenant_id="pilot-tenant", unit_id="pilot-unit", fiscal_environment="homologation"
    )
    assert result == new


def test_two_simultaneous_active_bindings_for_the_same_scope_are_rejected(database) -> None:
    first = _certificate_binding(reference_id="ref:scope/certificate-a")
    second = _certificate_binding(reference_id="ref:scope/certificate-b")
    _register(database, first)
    _register(database, second)
    administration = SecretBindingAdministration(database, clock=lambda: NOW)
    with pytest.raises(SecretResolutionError):
        administration.active_certificate_for_scope(
            tenant_id="pilot-tenant", unit_id="pilot-unit", fiscal_environment="homologation"
        )


def test_certificate_binding_status_transitions() -> None:
    valid = _certificate_binding(not_after=NOW + timedelta(days=90))
    assert certificate_binding_status(valid, NOW) is CertificateStatus.VALID

    expiring = _certificate_binding(not_after=NOW + timedelta(days=5))
    assert certificate_binding_status(expiring, NOW) is CertificateStatus.EXPIRING

    expired = _certificate_binding(not_after=NOW - timedelta(days=1))
    assert certificate_binding_status(expired, NOW) is CertificateStatus.EXPIRED

    no_expiry = _certificate_binding(not_after=None)
    assert certificate_binding_status(no_expiry, NOW) is CertificateStatus.VALID


def test_certificate_binding_status_rejects_non_certificate_kind() -> None:
    signature = SecretBinding(
        reference_id="sec_not_a_certificate",
        tenant_id="pilot-tenant",
        unit_id="pilot-unit",
        purpose="webhook-signing",
        runtime_environment="staging",
        fiscal_environment=None,
        provider_id="pilot-provider",
        workload_id="nfcore-worker",
        kind="signature",
        canonical_version=1,
        resource="projects/nfcore-synthetic/secrets/not-a-certificate",
        cloud_version="1",
    )
    with pytest.raises(SecretResolutionError):
        certificate_binding_status(signature, NOW)
