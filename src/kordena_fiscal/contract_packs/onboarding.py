"""Reusable, fail-closed onboarding certification for future FM products.

The helpers in this module do not decide tax, jurisdiction, binding or readiness.
They certify that a product declares a complete integration contract and enforce
that authoritative runtime prerequisites have already been resolved before a
mutating fiscal call is allowed.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from kordena_fiscal.compliance import FiscalActionCapability
from kordena_fiscal.domain import FiscalDocumentKind, FiscalValidationError
from kordena_fiscal.operations import FiscalOperationKind
from kordena_fiscal.verticals import VerticalModuleRegistry

from .base import (
    ProductContractPackRegistry,
    ProductFiscalContractPack,
    ProductOperationContractError,
)

_REQUIRED_SCOPE_HEADERS = (
    "X-FM-Host-Namespace",
    "X-FM-Tenant-Id",
    "X-FM-Unit-Id",
    "X-FM-Environment",
    "X-Correlation-Id",
)


class ProductOnboardingCertificationError(FiscalValidationError):
    """Raised when a product cannot be certified for the integration boundary."""


class ProductMutationPreflightError(ProductOperationContractError):
    """Raised when runtime prerequisites for a fiscal mutation are incomplete."""


@dataclass(frozen=True, slots=True)
class ProductOnboardingDeclaration:
    """Minimum non-fiscal facts a future FM product must declare."""

    product_id: str
    contract_pack: ProductFiscalContractPack
    commercial_authority: str
    idempotency_strategy: str

    def __post_init__(self) -> None:
        if not self.product_id.strip():
            raise ProductOnboardingCertificationError("product_id must not be blank")
        if not self.commercial_authority.strip():
            raise ProductOnboardingCertificationError(
                "commercial_authority must identify the authoritative business fact"
            )
        if not self.idempotency_strategy.strip():
            raise ProductOnboardingCertificationError(
                "idempotency_strategy must be explicitly documented"
            )


@dataclass(frozen=True, slots=True)
class ProductOnboardingCertification:
    product_id: str
    pack_id: str
    pack_version: str
    host_namespace: str
    use_case_ids: tuple[str, ...]
    commercial_authority: str
    idempotency_strategy: str
    catalog_registration_required: bool = True
    fiscal_binding_required: bool = True
    readiness_required_before_mutation: bool = True
    readiness_granted: bool = False


def certify_product_onboarding(
    declaration: ProductOnboardingDeclaration,
    *,
    vertical_registry: VerticalModuleRegistry | None = None,
) -> ProductOnboardingCertification:
    """Certify the structural contract without granting fiscal readiness.

    A temporary registry proves that pack/host identity is unambiguous. Vertical
    declarations are validated when present and require an authoritative vertical
    registry rather than being silently ignored.
    """

    descriptor = declaration.contract_pack.descriptor
    ProductContractPackRegistry((declaration.contract_pack,))

    requires_verticals = any(
        use_case.vertical_module_id is not None for use_case in descriptor.use_cases
    )
    if requires_verticals and vertical_registry is None:
        raise ProductOnboardingCertificationError(
            "vertical_registry is required when the pack declares vertical capabilities"
        )
    if vertical_registry is not None:
        descriptor.validate_vertical_contracts(vertical_registry)

    return ProductOnboardingCertification(
        product_id=declaration.product_id.strip(),
        pack_id=descriptor.pack_id,
        pack_version=descriptor.version,
        host_namespace=descriptor.host_namespace,
        use_case_ids=tuple(use_case.use_case_id for use_case in descriptor.use_cases),
        commercial_authority=declaration.commercial_authority.strip(),
        idempotency_strategy=declaration.idempotency_strategy.strip(),
    )


@dataclass(frozen=True, slots=True)
class ProductMutationPreflight:
    pack_id: str
    host_namespace: str
    use_case_id: str
    operation_kind: FiscalOperationKind
    document_kind: FiscalDocumentKind
    fiscal_action: FiscalActionCapability
    scope_headers: Mapping[str, str]
    idempotency_key: str
    fiscal_binding_resolved: bool
    capability_granted: bool
    readiness_granted: bool


def validate_product_mutation_preflight(
    request: ProductMutationPreflight,
    *,
    registry: ProductContractPackRegistry,
) -> None:
    """Fail closed before mutation; authoritative systems still decide the facts."""

    pack = registry.require(request.pack_id)
    host_pack = registry.require_for_host(request.host_namespace)
    if host_pack.descriptor.pack_id != pack.descriptor.pack_id:
        raise ProductMutationPreflightError("host namespace does not belong to requested pack")

    use_case = pack.descriptor.require_use_case(request.use_case_id)
    if request.operation_kind not in use_case.operation_kinds:
        raise ProductMutationPreflightError("operation kind is not declared by product use case")
    if request.document_kind not in use_case.document_kinds:
        raise ProductMutationPreflightError("document kind is not declared by product use case")
    if request.fiscal_action not in use_case.fiscal_actions:
        raise ProductMutationPreflightError("fiscal action is not declared by product use case")

    missing_headers = tuple(
        header
        for header in _REQUIRED_SCOPE_HEADERS
        if not request.scope_headers.get(header, "").strip()
    )
    if missing_headers:
        raise ProductMutationPreflightError(
            "fiscal scope is incomplete: " + ", ".join(missing_headers)
        )
    if request.scope_headers["X-FM-Host-Namespace"].strip().lower() != request.host_namespace:
        raise ProductMutationPreflightError("scope host namespace does not match request")
    if not request.idempotency_key.strip():
        raise ProductMutationPreflightError("idempotency key is required for mutation")
    if not request.fiscal_binding_resolved:
        raise ProductMutationPreflightError("fiscal binding must be resolved before mutation")
    if not request.capability_granted:
        raise ProductMutationPreflightError("authoritative capability is not granted")
    if not request.readiness_granted:
        raise ProductMutationPreflightError("authoritative readiness is not granted")


__all__ = [
    "ProductMutationPreflight",
    "ProductMutationPreflightError",
    "ProductOnboardingCertification",
    "ProductOnboardingCertificationError",
    "ProductOnboardingDeclaration",
    "certify_product_onboarding",
    "validate_product_mutation_preflight",
]
