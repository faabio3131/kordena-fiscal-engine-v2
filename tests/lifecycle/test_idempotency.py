from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from kordena_fiscal.documents import (
    CanonicalFiscalDocument,
    FiscalLineSnapshot,
    FiscalPaymentSnapshot,
    PaymentMethodKind,
)
from kordena_fiscal.domain import (
    BrazilianJurisdiction,
    CnaeCode,
    Cnpj,
    ExecutionScope,
    FiscalAddress,
    FiscalDocumentKind,
    FiscalEnvironment,
    FiscalProductProfile,
    FiscalProfile,
    FiscalUnitCode,
    Gtin,
    Money,
    NcmCode,
    ProductOrigin,
    SourceReference,
    StateRegistration,
    TaxRegimeCode,
)
from kordena_fiscal.lifecycle import (
    IdempotencyConflictError,
    IdempotencyCoordinator,
    IdempotencyStateError,
    InMemoryIdempotencyStore,
    IssuanceAttemptStatus,
    build_issuance_key,
    build_request_fingerprint,
)
from kordena_fiscal.tax import TaxDecision, TaxRuleOutcome


def _scope(
    *,
    tenant: str = "tenant-test",
    unit: str = "unit-test",
    environment: FiscalEnvironment = FiscalEnvironment.HOMOLOGATION,
    correlation: str = "corr-1",
) -> ExecutionScope:
    return ExecutionScope(
        tenant_id=tenant,
        unit_id=unit,
        environment=environment,
        correlation_id=correlation,
    )


def _issuer(scope: ExecutionScope) -> FiscalProfile:
    return FiscalProfile(
        profile_id="issuer-profile-1",
        scope=scope,
        cnpj=Cnpj("12.345.678/0001-95"),
        legal_name="Empresa Fiscal Sintetica Ltda",
        tax_regime=TaxRegimeCode.SIMPLES_NACIONAL,
        state_registration=StateRegistration("SP", "123456789"),
        primary_cnae=CnaeCode("5611-2/01"),
        address=FiscalAddress(
            street="Rua Sintetica",
            number="100",
            district="Centro",
            municipality_name="Sao Paulo",
            jurisdiction=BrazilianJurisdiction("SP", "3550308"),
            postal_code="01001000",
        ),
        effective_from=datetime(2026, 1, 1, tzinfo=UTC),
    )


def _product(scope: ExecutionScope) -> FiscalProductProfile:
    return FiscalProductProfile(
        profile_id="product-profile-1",
        product_id="product-1",
        scope=scope,
        commercial_code="SKU-001",
        description="Produto fiscal sintetico",
        ncm=NcmCode("21069090"),
        commercial_unit=FiscalUnitCode("UN"),
        taxable_unit=FiscalUnitCode("UN"),
        origin=ProductOrigin.NATIONAL,
        effective_from=datetime(2026, 1, 1, tzinfo=UTC),
        gtin=Gtin("SEM GTIN"),
    )


def _tax_decision() -> TaxDecision:
    return TaxDecision(
        rule_id="rule-synthetic-1",
        rule_version=1,
        source_normative="NORMA-SINTETICA",
        outcome=TaxRuleOutcome(
            cfop="5102",
            icms_code="102",
            pis_cst="49",
            cofins_cst="49",
        ),
        rank=(2, 4, 0),
    )


def _document(
    *,
    scope: ExecutionScope | None = None,
    document_id: str = "doc-1",
    source_id: str = "sale-42",
    document_kind: FiscalDocumentKind = FiscalDocumentKind.NFCE,
    gross: str = "20.00",
) -> CanonicalFiscalDocument:
    actual_scope = scope or _scope()
    amount = Decimal(gross)
    return CanonicalFiscalDocument(
        document_id=document_id,
        scope=actual_scope,
        source=SourceReference("sale", source_id),
        document_kind=document_kind,
        issued_at=datetime(2026, 9, 10, 20, 0, tzinfo=UTC),
        issuer=_issuer(actual_scope),
        items=(
            FiscalLineSnapshot(
                line_number=1,
                product=_product(actual_scope),
                quantity=Decimal("1"),
                unit_price=Money(amount),
                gross_amount=Money(amount),
                tax_decision=_tax_decision(),
            ),
        ),
        payments=(
            FiscalPaymentSnapshot(
                method=PaymentMethodKind.PIX,
                amount=Money(amount),
            ),
        ),
    )


def test_same_semantic_retry_returns_same_reserved_generation() -> None:
    store = InMemoryIdempotencyStore()
    coordinator = IdempotencyCoordinator(store)
    document = _document()

    first = coordinator.begin(document)
    second = coordinator.begin(document)

    assert first.replay is False
    assert second.replay is True
    assert first.attempt == second.attempt
    assert first.attempt.generation == 1
    assert len(store.attempts(first.attempt.key)) == 1


def test_transient_document_and_correlation_ids_do_not_change_semantic_identity() -> None:
    first = _document(
        scope=_scope(correlation="corr-first"),
        document_id="doc-first",
    )
    second = _document(
        scope=_scope(correlation="corr-retry"),
        document_id="doc-recreated-on-retry",
    )

    assert build_issuance_key(first) == build_issuance_key(second)
    assert build_request_fingerprint(first) == build_request_fingerprint(second)

    coordinator = IdempotencyCoordinator(InMemoryIdempotencyStore())
    initial = coordinator.begin(first)
    replay = coordinator.begin(second)

    assert initial.replay is False
    assert replay.replay is True
    assert replay.attempt.document_id == "doc-first"


def test_changed_content_while_reserved_is_blocked() -> None:
    coordinator = IdempotencyCoordinator(InMemoryIdempotencyStore())
    coordinator.begin(_document(gross="20.00"))

    with pytest.raises(IdempotencyConflictError, match="different content"):
        coordinator.begin(_document(document_id="doc-2", gross="25.00"))


def test_rejected_attempt_allows_corrected_new_generation() -> None:
    store = InMemoryIdempotencyStore()
    coordinator = IdempotencyCoordinator(store)

    first = coordinator.begin(_document(gross="20.00"))
    rejected = coordinator.mark_rejected(
        first.attempt.key,
        first.attempt.generation,
        "synthetic fiscal rejection",
    )
    corrected = coordinator.begin(_document(document_id="doc-2", gross="25.00"))

    assert rejected.status is IssuanceAttemptStatus.REJECTED
    assert corrected.replay is False
    assert corrected.attempt.generation == 2
    assert corrected.attempt.document_id == "doc-2"
    assert len(store.attempts(first.attempt.key)) == 2


def test_authorized_attempt_blocks_changed_content_forever_for_same_intent() -> None:
    coordinator = IdempotencyCoordinator(InMemoryIdempotencyStore())
    first = coordinator.begin(_document())
    authorized = coordinator.mark_authorized(
        first.attempt.key,
        first.attempt.generation,
        "authorization-reference-1",
    )

    assert authorized.status is IssuanceAttemptStatus.AUTHORIZED
    with pytest.raises(IdempotencyConflictError, match="different content"):
        coordinator.begin(_document(document_id="doc-2", gross="25"))


def test_authorization_completion_is_idempotent_but_cannot_be_rewritten() -> None:
    coordinator = IdempotencyCoordinator(InMemoryIdempotencyStore())
    reservation = coordinator.begin(_document())

    first = coordinator.mark_authorized(
        reservation.attempt.key,
        1,
        "authorization-reference-1",
    )
    replay = coordinator.mark_authorized(
        reservation.attempt.key,
        1,
        "authorization-reference-1",
    )

    assert replay == first
    with pytest.raises(IdempotencyStateError, match="cannot change result_reference"):
        coordinator.mark_authorized(
            reservation.attempt.key,
            1,
            "authorization-reference-2",
        )


def test_only_latest_generation_can_be_completed() -> None:
    coordinator = IdempotencyCoordinator(InMemoryIdempotencyStore())
    first = coordinator.begin(_document(gross="20"))
    coordinator.mark_rejected(first.attempt.key, 1, "synthetic rejection")
    second = coordinator.begin(_document(document_id="doc-2", gross="21"))

    assert second.attempt.generation == 2
    with pytest.raises(IdempotencyStateError, match="latest generation"):
        coordinator.mark_authorized(
            first.attempt.key,
            1,
            "late-authorization",
        )


def test_key_is_partitioned_by_source_scope_environment_and_document_kind() -> None:
    baseline = build_issuance_key(_document())
    variants = (
        _document(source_id="sale-43"),
        _document(scope=_scope(tenant="tenant-other")),
        _document(scope=_scope(unit="unit-other")),
        _document(scope=_scope(environment=FiscalEnvironment.PRODUCTION)),
        _document(document_kind=FiscalDocumentKind.NFE),
    )

    assert all(build_issuance_key(document) != baseline for document in variants)


def test_concurrent_begin_creates_exactly_one_new_reservation() -> None:
    store = InMemoryIdempotencyStore()
    coordinator = IdempotencyCoordinator(store)
    document = _document()

    with ThreadPoolExecutor(max_workers=16) as executor:
        reservations = list(executor.map(lambda _: coordinator.begin(document), range(64)))

    assert sum(not reservation.replay for reservation in reservations) == 1
    assert sum(reservation.replay for reservation in reservations) == 63
    assert {reservation.attempt.generation for reservation in reservations} == {1}
    assert len({reservation.attempt.key.value for reservation in reservations}) == 1
    assert len(store.attempts(reservations[0].attempt.key)) == 1
