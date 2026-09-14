from __future__ import annotations

from dataclasses import fields
from datetime import UTC, datetime

import pytest

from kordena_fiscal.control_plane import (
    AdminPrincipal,
    ControlPlaneAuditAction,
    ControlPlaneAuthorizationError,
    ControlPlaneConflictError,
    ControlPlaneFoundationService,
    ControlPlaneNotFoundError,
    ControlPlanePermission,
    FiscalUnitRegistration,
    SecretReference,
    SecretReferenceKind,
)
from kordena_fiscal.domain import FiscalEnvironment, FiscalValidationError


class _FixedClock:
    def now(self) -> datetime:
        return datetime(2026, 9, 12, 17, 30, tzinfo=UTC)


def _global_admin() -> AdminPrincipal:
    return AdminPrincipal(
        actor_id="fm-platform-admin",
        permissions=frozenset(
            {
                ControlPlanePermission.ORGANIZATION_WRITE,
                ControlPlanePermission.UNIT_WRITE,
                ControlPlanePermission.SECRET_REFERENCE_WRITE,
                ControlPlanePermission.AUDIT_READ,
            }
        ),
        global_scope=True,
    )


def _tenant_admin(tenant_id: str = "tenant-a") -> AdminPrincipal:
    return AdminPrincipal(
        actor_id="tenant-admin",
        permissions=frozenset(
            {
                ControlPlanePermission.UNIT_WRITE,
                ControlPlanePermission.SECRET_REFERENCE_WRITE,
                ControlPlanePermission.AUDIT_READ,
            }
        ),
        tenant_ids=frozenset({tenant_id}),
    )


def _service_with_org() -> ControlPlaneFoundationService:
    service = ControlPlaneFoundationService(clock=_FixedClock())
    service.onboard_organization(
        actor=_global_admin(),
        tenant_id="tenant-a",
        legal_name="Synthetic Fiscal Company A",
        correlation_id="cp-org-001",
    )
    return service


def test_global_admin_onboards_organization_and_generates_audit_fact() -> None:
    service = _service_with_org()

    organization = service.state.organizations["tenant-a"]
    assert organization.legal_name == "Synthetic Fiscal Company A"

    events = service.list_audit(actor=_global_admin())
    assert len(events) == 1
    assert events[0].action is ControlPlaneAuditAction.ORGANIZATION_ONBOARDED
    assert events[0].tenant_id == "tenant-a"
    assert events[0].actor_id == "fm-platform-admin"
    assert events[0].occurred_at == datetime(2026, 9, 12, 17, 30, tzinfo=UTC)


def test_organization_onboarding_requires_global_scope_and_permission() -> None:
    service = ControlPlaneFoundationService(clock=_FixedClock())
    scoped_org_writer = AdminPrincipal(
        actor_id="tenant-org-writer",
        permissions=frozenset({ControlPlanePermission.ORGANIZATION_WRITE}),
        tenant_ids=frozenset({"tenant-a"}),
    )

    with pytest.raises(ControlPlaneAuthorizationError, match="global-scope"):
        service.onboard_organization(
            actor=scoped_org_writer,
            tenant_id="tenant-a",
            legal_name="Synthetic Company",
            correlation_id="cp-org-002",
        )

    actor = AdminPrincipal(
        actor_id="global-auditor",
        permissions=frozenset({ControlPlanePermission.AUDIT_READ}),
        global_scope=True,
    )
    with pytest.raises(ControlPlaneAuthorizationError, match="organization.write"):
        service.onboard_organization(
            actor=actor,
            tenant_id="tenant-a",
            legal_name="Synthetic Company",
            correlation_id="cp-org-003",
        )


def test_unit_onboarding_requires_existing_organization_and_tenant_scope() -> None:
    service = ControlPlaneFoundationService(clock=_FixedClock())
    registration = FiscalUnitRegistration(
        tenant_id="tenant-a",
        unit_id="unit-01",
        display_name="Synthetic Unit 01",
    )

    with pytest.raises(ControlPlaneNotFoundError, match="organization"):
        service.onboard_unit(
            actor=_tenant_admin(),
            registration=registration,
            correlation_id="cp-unit-001",
        )

    service.onboard_organization(
        actor=_global_admin(),
        tenant_id="tenant-a",
        legal_name="Synthetic Company",
        correlation_id="cp-org-004",
    )
    accepted = service.onboard_unit(
        actor=_tenant_admin(),
        registration=registration,
        correlation_id="cp-unit-002",
    )
    assert accepted is registration

    with pytest.raises(ControlPlaneAuthorizationError, match="cannot access tenant"):
        service.onboard_unit(
            actor=_tenant_admin("tenant-b"),
            registration=FiscalUnitRegistration(
                tenant_id="tenant-a",
                unit_id="unit-02",
                display_name="Synthetic Unit 02",
            ),
            correlation_id="cp-unit-003",
        )


def test_duplicate_organization_and_unit_fail_closed() -> None:
    service = _service_with_org()
    actor = _global_admin()

    with pytest.raises(ControlPlaneConflictError, match="organization already exists"):
        service.onboard_organization(
            actor=actor,
            tenant_id="tenant-a",
            legal_name="Duplicate Company",
            correlation_id="cp-dup-001",
        )

    registration = FiscalUnitRegistration(
        tenant_id="tenant-a",
        unit_id="unit-01",
        display_name="Synthetic Unit 01",
    )
    service.onboard_unit(
        actor=actor,
        registration=registration,
        correlation_id="cp-dup-002",
    )
    with pytest.raises(ControlPlaneConflictError, match="unit already exists"):
        service.onboard_unit(
            actor=actor,
            registration=registration,
            correlation_id="cp-dup-003",
        )


def test_secret_reference_is_opaque_and_never_contains_secret_material_field() -> None:
    names = {item.name for item in fields(SecretReference)}

    assert names == {
        "reference_id",
        "kind",
        "tenant_id",
        "unit_id",
        "environment",
        "provider_id",
    }
    assert not ({"secret", "value", "material", "password", "token", "pfx"} & names)

    with pytest.raises(FiscalValidationError, match="opaque ref"):
        SecretReference(
            reference_id="this-is-not-a-vault-reference",
            kind=SecretReferenceKind.CREDENTIALS,
            tenant_id="tenant-a",
            unit_id="unit-01",
            environment=FiscalEnvironment.HOMOLOGATION,
            provider_id="provider-a",
        )


def test_secret_reference_binding_requires_enabled_environment() -> None:
    service = _service_with_org()
    actor = _tenant_admin()
    service.onboard_unit(
        actor=actor,
        registration=FiscalUnitRegistration(
            tenant_id="tenant-a",
            unit_id="unit-01",
            display_name="Synthetic Unit 01",
        ),
        correlation_id="cp-unit-004",
    )

    production_reference = SecretReference(
        reference_id="ref:fm-fiscal/tenant-a/unit-01/prod-credentials",
        kind=SecretReferenceKind.CREDENTIALS,
        tenant_id="tenant-a",
        unit_id="unit-01",
        environment=FiscalEnvironment.PRODUCTION,
        provider_id="provider-a",
    )
    with pytest.raises(ControlPlaneAuthorizationError, match="environment"):
        service.bind_secret_reference(
            actor=actor,
            reference=production_reference,
            correlation_id="cp-secret-001",
        )


def test_secret_reference_binding_is_scoped_unique_and_audited() -> None:
    service = _service_with_org()
    actor = _tenant_admin()
    service.onboard_unit(
        actor=actor,
        registration=FiscalUnitRegistration(
            tenant_id="tenant-a",
            unit_id="unit-01",
            display_name="Synthetic Unit 01",
        ),
        correlation_id="cp-unit-005",
    )
    reference = SecretReference(
        reference_id="ref:fm-fiscal/tenant-a/unit-01/hml-certificate",
        kind=SecretReferenceKind.CERTIFICATE,
        tenant_id="tenant-a",
        unit_id="unit-01",
        environment=FiscalEnvironment.HOMOLOGATION,
    )

    service.bind_secret_reference(
        actor=actor,
        reference=reference,
        correlation_id="cp-secret-002",
    )
    audit = service.list_audit(actor=actor, tenant_id="tenant-a")
    assert audit[-1].action is ControlPlaneAuditAction.SECRET_REFERENCE_BOUND
    assert audit[-1].target_id == reference.reference_id

    with pytest.raises(ControlPlaneConflictError, match="already bound"):
        service.bind_secret_reference(
            actor=actor,
            reference=SecretReference(
                reference_id="ref:fm-fiscal/tenant-a/unit-01/rotated-certificate",
                kind=SecretReferenceKind.CERTIFICATE,
                tenant_id="tenant-a",
                unit_id="unit-01",
                environment=FiscalEnvironment.HOMOLOGATION,
            ),
            correlation_id="cp-secret-003",
        )


def test_provider_scoped_credentials_can_coexist_for_same_unit_environment() -> None:
    service = _service_with_org()
    actor = _tenant_admin()
    service.onboard_unit(
        actor=actor,
        registration=FiscalUnitRegistration(
            tenant_id="tenant-a",
            unit_id="unit-01",
            display_name="Synthetic Unit 01",
        ),
        correlation_id="cp-unit-provider-scope",
    )

    for provider in ("provider-a", "provider-b"):
        service.bind_secret_reference(
            actor=actor,
            reference=SecretReference(
                reference_id=f"ref:fm-fiscal/tenant-a/unit-01/{provider}/credentials",
                kind=SecretReferenceKind.CREDENTIALS,
                tenant_id="tenant-a",
                unit_id="unit-01",
                environment=FiscalEnvironment.HOMOLOGATION,
                provider_id=provider,
            ),
            correlation_id=f"cp-secret-{provider}",
        )

    keys = set(service.state.secret_references)
    assert len(keys) == 2
    assert {key[-1] for key in keys} == {"provider-a", "provider-b"}


def test_provider_scoped_secret_requires_provider_and_certificate_forbids_it() -> None:
    with pytest.raises(FiscalValidationError, match="provider_id is required"):
        SecretReference(
            reference_id="ref:fm-fiscal/tenant-a/unit-01/credentials",
            kind=SecretReferenceKind.CREDENTIALS,
            tenant_id="tenant-a",
            unit_id="unit-01",
            environment=FiscalEnvironment.HOMOLOGATION,
        )

    with pytest.raises(FiscalValidationError, match="provider_id is not allowed"):
        SecretReference(
            reference_id="ref:fm-fiscal/tenant-a/unit-01/certificate",
            kind=SecretReferenceKind.CERTIFICATE,
            tenant_id="tenant-a",
            unit_id="unit-01",
            environment=FiscalEnvironment.HOMOLOGATION,
            provider_id="provider-a",
        )


def test_audit_read_is_permissioned_and_tenant_filtered() -> None:
    service = ControlPlaneFoundationService(clock=_FixedClock())
    global_admin = _global_admin()
    for tenant_id in ("tenant-a", "tenant-b"):
        service.onboard_organization(
            actor=global_admin,
            tenant_id=tenant_id,
            legal_name=f"Synthetic {tenant_id}",
            correlation_id=f"cp-{tenant_id}",
        )

    tenant_a_events = service.list_audit(actor=_tenant_admin("tenant-a"))
    assert {event.tenant_id for event in tenant_a_events} == {"tenant-a"}
    assert len(service.list_audit(actor=global_admin)) == 2

    no_audit_permission = AdminPrincipal(
        actor_id="tenant-writer",
        permissions=frozenset({ControlPlanePermission.UNIT_WRITE}),
        tenant_ids=frozenset({"tenant-a"}),
    )
    with pytest.raises(ControlPlaneAuthorizationError, match="audit.read"):
        service.list_audit(actor=no_audit_permission)


def test_global_scope_cannot_mix_with_tenant_allowlist() -> None:
    with pytest.raises(FiscalValidationError, match="must not declare tenant_ids"):
        AdminPrincipal(
            actor_id="ambiguous-admin",
            permissions=frozenset({ControlPlanePermission.AUDIT_READ}),
            tenant_ids=frozenset({"tenant-a"}),
            global_scope=True,
        )
