from __future__ import annotations

import pytest

from kordena_fiscal.compliance import FiscalActionCapability
from kordena_fiscal.contract_packs.base import (
    DeclarativeProductFiscalContractPack,
    ProductContractPackDescriptor,
    ProductContractPackNotFoundError,
    ProductContractPackRegistry,
    ProductUseCaseDescriptor,
    ProductUseCaseNotFoundError,
)
from kordena_fiscal.contract_packs.onboarding import (
    ProductMutationPreflight,
    ProductMutationPreflightError,
    ProductOnboardingCertificationError,
    ProductOnboardingDeclaration,
    certify_product_onboarding,
    validate_product_mutation_preflight,
)
from kordena_fiscal.domain import FiscalDocumentKind
from kordena_fiscal.operations import FiscalOperationKind


def _synthetic_pack() -> DeclarativeProductFiscalContractPack:
    return DeclarativeProductFiscalContractPack(
        ProductContractPackDescriptor(
            pack_id="synthetic-product",
            host_namespace="fm.synthetic-product",
            version="1",
            use_cases=(
                ProductUseCaseDescriptor(
                    use_case_id="taxable-sale",
                    operation_kinds=frozenset({FiscalOperationKind.SALE}),
                    document_kinds=frozenset({FiscalDocumentKind.NFCE}),
                    fiscal_actions=frozenset(
                        {
                            FiscalActionCapability.ISSUE,
                            FiscalActionCapability.QUERY,
                        }
                    ),
                    outbound_event_types=("synthetic.sale.settled",),
                    inbound_event_types=("fiscal.document.authorized",),
                ),
            ),
        )
    )


def _valid_preflight() -> ProductMutationPreflight:
    return ProductMutationPreflight(
        pack_id="synthetic-product",
        host_namespace="fm.synthetic-product",
        use_case_id="taxable-sale",
        operation_kind=FiscalOperationKind.SALE,
        document_kind=FiscalDocumentKind.NFCE,
        fiscal_action=FiscalActionCapability.ISSUE,
        scope_headers={
            "X-FM-Host-Namespace": "fm.synthetic-product",
            "X-FM-Tenant-Id": "tenant-test",
            "X-FM-Unit-Id": "unit-test",
            "X-FM-Environment": "HOMOLOGATION",
            "X-Correlation-Id": "corr-test",
        },
        idempotency_key="synthetic:sale:1:nfce:v1",
        fiscal_binding_resolved=True,
        capability_granted=True,
        readiness_granted=True,
    )


def test_synthetic_future_product_can_be_structurally_certified_without_readiness_grant() -> None:
    pack = _synthetic_pack()
    certification = certify_product_onboarding(
        ProductOnboardingDeclaration(
            product_id="synthetic-product",
            contract_pack=pack,
            commercial_authority="synthetic.sale.settled",
            idempotency_strategy="one key per settled sale and document family",
        )
    )

    assert certification.pack_id == "synthetic-product"
    assert certification.host_namespace == "fm.synthetic-product"
    assert certification.use_case_ids == ("taxable-sale",)
    assert certification.catalog_registration_required is True
    assert certification.fiscal_binding_required is True
    assert certification.readiness_required_before_mutation is True
    assert certification.readiness_granted is False


def test_onboarding_requires_explicit_commercial_authority_and_idempotency_strategy() -> None:
    pack = _synthetic_pack()
    with pytest.raises(ProductOnboardingCertificationError):
        ProductOnboardingDeclaration(
            product_id="synthetic-product",
            contract_pack=pack,
            commercial_authority="",
            idempotency_strategy="one key per settlement",
        )

    with pytest.raises(ProductOnboardingCertificationError):
        ProductOnboardingDeclaration(
            product_id="synthetic-product",
            contract_pack=pack,
            commercial_authority="synthetic.sale.settled",
            idempotency_strategy="",
        )


def test_valid_registered_pack_passes_only_with_authoritative_gates_green() -> None:
    pack = _synthetic_pack()
    registry = ProductContractPackRegistry((pack,))
    validate_product_mutation_preflight(_valid_preflight(), registry=registry)


@pytest.mark.parametrize(
    ("field", "value", "expected_error"),
    [
        ("host_namespace", "fm.other", ProductContractPackNotFoundError),
        ("use_case_id", "unknown-use-case", ProductUseCaseNotFoundError),
        ("operation_kind", FiscalOperationKind.SERVICE, ProductMutationPreflightError),
        ("document_kind", FiscalDocumentKind.NFE, ProductMutationPreflightError),
        ("fiscal_action", FiscalActionCapability.CANCEL, ProductMutationPreflightError),
        ("idempotency_key", "", ProductMutationPreflightError),
        ("fiscal_binding_resolved", False, ProductMutationPreflightError),
        ("capability_granted", False, ProductMutationPreflightError),
        ("readiness_granted", False, ProductMutationPreflightError),
    ],
)
def test_invalid_mutation_preflight_fails_closed(
    field: str,
    value: object,
    expected_error: type[Exception],
) -> None:
    pack = _synthetic_pack()
    registry = ProductContractPackRegistry((pack,))
    request = _valid_preflight()
    values = {
        "pack_id": request.pack_id,
        "host_namespace": request.host_namespace,
        "use_case_id": request.use_case_id,
        "operation_kind": request.operation_kind,
        "document_kind": request.document_kind,
        "fiscal_action": request.fiscal_action,
        "scope_headers": request.scope_headers,
        "idempotency_key": request.idempotency_key,
        "fiscal_binding_resolved": request.fiscal_binding_resolved,
        "capability_granted": request.capability_granted,
        "readiness_granted": request.readiness_granted,
    }
    values[field] = value
    with pytest.raises(expected_error):
        candidate = ProductMutationPreflight(**values)  # type: ignore[arg-type]
        validate_product_mutation_preflight(candidate, registry=registry)


def test_incomplete_scope_fails_closed() -> None:
    registry = ProductContractPackRegistry((_synthetic_pack(),))
    request = _valid_preflight()
    headers = dict(request.scope_headers)
    headers.pop("X-FM-Unit-Id")
    invalid = ProductMutationPreflight(
        pack_id=request.pack_id,
        host_namespace=request.host_namespace,
        use_case_id=request.use_case_id,
        operation_kind=request.operation_kind,
        document_kind=request.document_kind,
        fiscal_action=request.fiscal_action,
        scope_headers=headers,
        idempotency_key=request.idempotency_key,
        fiscal_binding_resolved=True,
        capability_granted=True,
        readiness_granted=True,
    )
    with pytest.raises(ProductMutationPreflightError, match="fiscal scope is incomplete"):
        validate_product_mutation_preflight(invalid, registry=registry)


def test_unregistered_pack_fails_closed() -> None:
    registry = ProductContractPackRegistry()
    with pytest.raises(ProductContractPackNotFoundError):
        validate_product_mutation_preflight(_valid_preflight(), registry=registry)
