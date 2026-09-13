from __future__ import annotations

import pytest

from kordena_fiscal.convergence import (
    AuthorityAssignment,
    ConvergenceValidationError,
    CutoverNotReadyError,
    CutoverReadinessMatrix,
    CutoverReadinessStatus,
    CutoverRequirement,
    FiscalAuthorityDomain,
    LegacyAuthorityMode,
    SingleFiscalAuthorityPlan,
)


def _current_readiness() -> CutoverReadinessMatrix:
    return CutoverReadinessMatrix(
        requirements=(
            CutoverRequirement(
                "functional-equivalence",
                CutoverReadinessStatus.READY_INTERNAL,
                "V2-00 equivalence and cumulative regression certified",
            ),
            CutoverRequirement(
                "multi-product-certified",
                CutoverReadinessStatus.READY_INTERNAL,
                "V2-16.7 cross-product closure certified",
            ),
            CutoverRequirement(
                "kordena-operating-on-v2",
                CutoverReadinessStatus.BLOCKED_PRODUCT,
                "Kordena PR #118 remains functionally partial; FISC-20 is not released",
            ),
            CutoverRequirement(
                "full-fiscal-regression",
                CutoverReadinessStatus.READY_INTERNAL,
                "V2-16.7 full regression is green",
            ),
            CutoverRequirement(
                "state-document-migration-defined",
                CutoverReadinessStatus.BLOCKED_PRODUCT,
                "V2-17.2 has not executed at the V2-17.1 checkpoint",
            ),
            CutoverRequirement(
                "migration-tested",
                CutoverReadinessStatus.BLOCKED_PRODUCT,
                "migration rehearsal belongs to V2-17.2",
            ),
            CutoverRequirement(
                "rollback-documented",
                CutoverReadinessStatus.BLOCKED_PRODUCT,
                "rollback rehearsal belongs to V2-17.2",
            ),
            CutoverRequirement(
                "external-operational-evidence",
                CutoverReadinessStatus.BLOCKED_EXTERNAL,
                "V2-15 official external homologation evidence remains pending",
            ),
            CutoverRequirement(
                "director-cutover-approval",
                CutoverReadinessStatus.HUMAN_APPROVAL_REQUIRED,
                "real cutover requires an explicit future human approval",
            ),
        )
    )


def _single_authority_plan() -> SingleFiscalAuthorityPlan:
    return SingleFiscalAuthorityPlan(
        future_authority="fm-fiscal-core-v2",
        assignments=tuple(
            AuthorityAssignment(
                domain=domain,
                current_authority="legacy-fiscal-baseline",
                future_authority="fm-fiscal-core-v2",
                legacy_mode_after_cutover=LegacyAuthorityMode.READ_ONLY,
            )
            for domain in FiscalAuthorityDomain
        ),
    )


def test_current_readiness_fails_closed_and_names_real_blockers() -> None:
    matrix = _current_readiness()

    assert matrix.cutover_allowed is False
    assert {item.requirement_id for item in matrix.blocking_requirements} == {
        "kordena-operating-on-v2",
        "state-document-migration-defined",
        "migration-tested",
        "rollback-documented",
        "external-operational-evidence",
        "director-cutover-approval",
    }
    with pytest.raises(CutoverNotReadyError, match="cutover prerequisites are not satisfied"):
        matrix.require_cutover_ready()


def test_readiness_matrix_rejects_duplicate_requirements() -> None:
    duplicated = CutoverRequirement(
        "same",
        CutoverReadinessStatus.READY_INTERNAL,
        "synthetic internal evidence",
    )
    with pytest.raises(ConvergenceValidationError, match="must be unique"):
        CutoverReadinessMatrix(requirements=(duplicated, duplicated))


def test_single_authority_plan_covers_every_domain_and_has_no_future_dual_writer() -> None:
    plan = _single_authority_plan()

    assert {item.domain for item in plan.assignments} == set(FiscalAuthorityDomain)
    assert {item.future_authority for item in plan.assignments} == {"fm-fiscal-core-v2"}
    assert plan.has_future_dual_writer is False
    assert all(
        item.legacy_mode_after_cutover is LegacyAuthorityMode.READ_ONLY
        for item in plan.assignments
    )


def test_single_authority_plan_rejects_legacy_read_write_after_cutover() -> None:
    assignments = tuple(
        AuthorityAssignment(
            domain=domain,
            current_authority="legacy-fiscal-baseline",
            future_authority="fm-fiscal-core-v2",
            legacy_mode_after_cutover=(
                LegacyAuthorityMode.READ_WRITE
                if domain is FiscalAuthorityDomain.SEQUENCE
                else LegacyAuthorityMode.READ_ONLY
            ),
        )
        for domain in FiscalAuthorityDomain
    )

    with pytest.raises(ConvergenceValidationError, match="cannot remain read-write"):
        SingleFiscalAuthorityPlan(
            future_authority="fm-fiscal-core-v2",
            assignments=assignments,
        )


def test_single_authority_plan_rejects_split_future_authority() -> None:
    assignments = tuple(
        AuthorityAssignment(
            domain=domain,
            current_authority="legacy-fiscal-baseline",
            future_authority=(
                "another-writer"
                if domain is FiscalAuthorityDomain.IDEMPOTENCY
                else "fm-fiscal-core-v2"
            ),
            legacy_mode_after_cutover=LegacyAuthorityMode.READ_ONLY,
        )
        for domain in FiscalAuthorityDomain
    )

    with pytest.raises(ConvergenceValidationError, match="same future authority"):
        SingleFiscalAuthorityPlan(
            future_authority="fm-fiscal-core-v2",
            assignments=assignments,
        )
