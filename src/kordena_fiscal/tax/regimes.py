"""Versioned federal tax-regime classification, separate from NF-e/NFC-e CRT.

A declaration is an input/snapshot only; it does not modify FiscalProfile,
calculate taxes, persist data or grant fiscal production authority.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from zoneinfo import ZoneInfo

from kordena_fiscal.domain import (
    ExecutionScope,
    FiscalProfile,
    FiscalValidationError,
    TaxRegimeCode,
)


class FederalIncomeTaxRegime(StrEnum):
    SIMPLES_NACIONAL = "simples_nacional"
    LUCRO_PRESUMIDO = "lucro_presumido"
    LUCRO_REAL = "lucro_real"


@dataclass(frozen=True, slots=True)
class FederalRegimeDeclaration:
    """Explicit, effective-dated and scope-bound corporate regime evidence.

    The CRT alone cannot distinguish Lucro Real from Lucro Presumido.
    Source authority and persistence integration remain subject to RTC-02 review.
    """

    scope: ExecutionScope
    crt: TaxRegimeCode
    federal_income_tax_regime: FederalIncomeTaxRegime
    effective_from: datetime
    source_reference: str
    version: int = 1
    effective_to: datetime | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.scope, ExecutionScope):
            raise FiscalValidationError("scope must be ExecutionScope")
        if not isinstance(self.crt, TaxRegimeCode):
            raise FiscalValidationError("crt must be TaxRegimeCode")
        if not isinstance(self.federal_income_tax_regime, FederalIncomeTaxRegime):
            raise FiscalValidationError("federal_income_tax_regime must be explicit")
        # The two dimensions remain separate, but inconsistent declarations
        # cannot authorize an impossible issuer fiscal combination. CRT=2 and
        # CRT=4 retain their distinct document treatment elsewhere.
        simple_crts = {
            TaxRegimeCode.SIMPLES_NACIONAL,
            TaxRegimeCode.SIMPLES_NACIONAL_EXCESS_SUBLIMIT,
            TaxRegimeCode.MEI,
        }
        if self.crt in simple_crts:
            if self.federal_income_tax_regime is not FederalIncomeTaxRegime.SIMPLES_NACIONAL:
                raise FiscalValidationError(
                    "Simples/MEI CRT is inconsistent with federal income-tax regime"
                )
        elif self.crt is TaxRegimeCode.NORMAL:
            if self.federal_income_tax_regime is FederalIncomeTaxRegime.SIMPLES_NACIONAL:
                raise FiscalValidationError(
                    "normal CRT is inconsistent with Simples Nacional federal regime"
                )
        if self.effective_from.tzinfo is None or self.effective_from.utcoffset() is None:
            raise FiscalValidationError("effective_from must be timezone-aware")
        if self.effective_to is not None:
            if self.effective_to.tzinfo is None or self.effective_to.utcoffset() is None:
                raise FiscalValidationError("effective_to must be timezone-aware")
            if self.effective_to <= self.effective_from:
                raise FiscalValidationError("effective_to must follow effective_from")
        if not isinstance(self.version, int) or isinstance(self.version, bool) or self.version < 1:
            raise FiscalValidationError("version must be an integer >= 1")
        if not isinstance(self.source_reference, str) or not self.source_reference.strip():
            raise FiscalValidationError("source_reference is required")
        if len(self.source_reference.strip()) > 1000:
            raise FiscalValidationError("source_reference exceeds length limit")
        object.__setattr__(self, "source_reference", self.source_reference.strip())

    def assert_effective_in_scope(self, scope: ExecutionScope, instant: datetime) -> None:
        """Raise on scope/time mismatch instead of selecting an unsafe fallback."""
        if not isinstance(scope, ExecutionScope) or scope.identity_partition_key != self.scope.identity_partition_key:
            raise FiscalValidationError("federal regime scope mismatch")
        if instant.tzinfo is None or instant.utcoffset() is None:
            raise FiscalValidationError("instant must be timezone-aware")
        if instant < self.effective_from or (
            self.effective_to is not None and instant >= self.effective_to
        ):
            raise FiscalValidationError("federal regime declaration is not effective")


def resolve_federal_regime_for_profile(
    profile: FiscalProfile,
    declaration: FederalRegimeDeclaration,
    instant: datetime,
) -> FederalIncomeTaxRegime:
    """Validate a declaration against the existing issuer fiscal authority.

    This is a pure, fail-closed lookup: it never infers the federal regime
    from CRT and does not persist or activate the declaration.
    """
    if not isinstance(profile, FiscalProfile):
        raise FiscalValidationError("profile must be FiscalProfile")
    if not isinstance(declaration, FederalRegimeDeclaration):
        raise FiscalValidationError("federal regime declaration is required")
    declaration.assert_effective_in_scope(profile.scope, instant)
    if not profile.is_effective_at(instant):
        raise FiscalValidationError("issuer fiscal profile is not effective")
    if profile.tax_regime != declaration.crt:
        raise FiscalValidationError("federal regime CRT does not match issuer profile")
    return declaration.federal_income_tax_regime


def resolve_federal_regime_timeline(
    profile: FiscalProfile,
    declarations: Iterable[FederalRegimeDeclaration],
    instant: datetime,
) -> FederalIncomeTaxRegime:
    """Select one effective corporate regime, rejecting overlaps and foreign scopes.

    The caller must supply the authoritative declarations for one fiscal scope.
    Gaps, overlap and scope leakage never receive a default classification.
    """
    if not isinstance(profile, FiscalProfile):
        raise FiscalValidationError("profile must be FiscalProfile")
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise FiscalValidationError("instant must be timezone-aware")
    items = tuple(declarations)
    if not items:
        raise FiscalValidationError("no federal regime declarations were supplied")
    for declaration in items:
        if not isinstance(declaration, FederalRegimeDeclaration):
            raise FiscalValidationError("invalid federal regime declaration in timeline")
        if declaration.scope.identity_partition_key != profile.scope.identity_partition_key:
            raise FiscalValidationError("federal regime timeline scope mismatch")
    ordered = sorted(items, key=lambda item: item.effective_from)
    for previous, current in zip(ordered, ordered[1:], strict=False):
        if previous.effective_to is None or previous.effective_to > current.effective_from:
            raise FiscalValidationError("federal regime effective periods overlap")
    effective = [
        item for item in ordered
        if item.effective_from <= instant
        and (item.effective_to is None or instant < item.effective_to)
    ]
    if len(effective) != 1:
        raise FiscalValidationError("no unambiguous federal regime effective at instant")
    return resolve_federal_regime_for_profile(profile, effective[0], instant)


class SimplesIbsCbsMode(StrEnum):
    """Evidence-backed IBS/CBS collection mode, NOT a tax calculation authority."""

    NOT_EFFECTIVE_IN_SIMPLES_2026 = "not_effective_in_simples_2026"
    SIMPLES_UNIFIED = "simples_unified"
    REGULAR_SEPARATE = "regular_separate"


@dataclass(frozen=True, slots=True)
class SimplesIbsCbsElection:
    """Versioned, issuer-bound proof of the Simples IBS/CBS collection choice.

    An option is not inferred from CRT. Its declared period and source must be
    independently checked by the caller against the competent authority; this
    model never opts in, sends a declaration, or enables tax calculation.
    """

    scope: ExecutionScope
    profile_id: str
    profile_version: int
    crt: TaxRegimeCode
    mode: SimplesIbsCbsMode
    effective_from: datetime
    source_reference: str
    version: int = 1
    effective_to: datetime | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.scope, ExecutionScope):
            raise FiscalValidationError("Simples election requires canonical scope")
        if not isinstance(self.profile_id, str) or not self.profile_id.strip():
            raise FiscalValidationError("Simples election requires profile_id")
        if not isinstance(self.profile_version, int) or isinstance(
            self.profile_version, bool
        ) or self.profile_version < 1:
            raise FiscalValidationError("Simples election requires profile_version")
        if not isinstance(self.crt, TaxRegimeCode) or self.crt not in (
            TaxRegimeCode.SIMPLES_NACIONAL,
            TaxRegimeCode.SIMPLES_NACIONAL_EXCESS_SUBLIMIT,
        ):
            raise FiscalValidationError("Simples election must be for CRT=1 or CRT=2")
        if not isinstance(self.mode, SimplesIbsCbsMode) or self.mode not in (
            SimplesIbsCbsMode.SIMPLES_UNIFIED, SimplesIbsCbsMode.REGULAR_SEPARATE
        ):
            raise FiscalValidationError("invalid Simples IBS/CBS election mode")
        if not isinstance(self.effective_from, datetime) or (
            self.effective_from.tzinfo is None or
            self.effective_from.utcoffset() is None
        ):
            raise FiscalValidationError("Simples election effective_from must be timezone-aware")
        if self.effective_to is not None and (
            not isinstance(self.effective_to, datetime)
            or self.effective_to.tzinfo is None
            or self.effective_to.utcoffset() is None
            or self.effective_to <= self.effective_from
        ):
            raise FiscalValidationError("invalid Simples election effective_to")
        if (
            not isinstance(self.version, int)
            or isinstance(self.version, bool)
            or self.version < 1
        ):
            raise FiscalValidationError("invalid Simples election version")
        if (
            not isinstance(self.source_reference, str)
            or not self.source_reference.strip()
            or len(self.source_reference.strip()) > 1000
        ):
            raise FiscalValidationError("Simples election requires source_reference")
        object.__setattr__(self, "profile_id", self.profile_id.strip())
        object.__setattr__(self, "source_reference", self.source_reference.strip())


def resolve_simples_ibs_cbs_mode(
    profile: FiscalProfile,
    elections: Iterable[SimplesIbsCbsElection],
    instant: datetime,
) -> SimplesIbsCbsMode:
    """Resolve fiscal-period applicability without calculating IBS/CBS amounts.

    Source: LC 214/2025 art. 41 §§2–4; CGSN resolutions 190/191 (2026)
    and RFB clarifications of 12–14 Aug 2026. Simples IBS/CBS rules begin
    01/01/2027; before then this result NEVER waives other fiscal duties,
    notably national NFS-e from 01/11/2026 for affected ME/EPP.

    Both CRT=1 and CRT=2 belong to Simples for this option declaration;
    CRT=2 retains its distinct ICMS/ISS treatment outside this resolver.
    This is a scoped eligibility guard, not a second TaxRuleEngine or evidence
    of a formally registered option. Missing/overlapping/future elections fail
    closed; caller must verify the competent authority and the option's term.
    """
    if not isinstance(profile, FiscalProfile):
        raise FiscalValidationError("Simples mode requires canonical FiscalProfile")
    if not isinstance(instant, datetime) or instant.tzinfo is None or (
        instant.utcoffset() is None
    ):
        raise FiscalValidationError("Simples mode instant must be timezone-aware")
    if not profile.is_effective_at(instant):
        raise FiscalValidationError("Simples mode requires effective FiscalProfile")
    if profile.tax_regime not in (
        TaxRegimeCode.SIMPLES_NACIONAL,
        TaxRegimeCode.SIMPLES_NACIONAL_EXCESS_SUBLIMIT,
    ):
        raise FiscalValidationError(
            "Simples IBS/CBS mode requires explicitly confirmed CRT=1 or CRT=2"
        )
    entries = tuple(elections)
    for entry in entries:
        if not isinstance(entry, SimplesIbsCbsElection):
            raise FiscalValidationError("invalid Simples election evidence")
        if entry.scope.identity_partition_key != profile.scope.identity_partition_key:
            raise FiscalValidationError("Simples election scope mismatch")
        if (entry.profile_id, entry.profile_version) != profile.snapshot_key:
            raise FiscalValidationError("Simples election profile snapshot mismatch")
        if entry.crt is not profile.tax_regime:
            raise FiscalValidationError("Simples election CRT mismatch")
        if entry.effective_from.astimezone(ZoneInfo("America/Sao_Paulo")).date() < date(
            2027, 1, 1
        ):
            raise FiscalValidationError("Simples IBS/CBS election cannot predate 2027")
    ordered = sorted(entries, key=lambda item: item.effective_from)
    for prior, following in zip(ordered, ordered[1:], strict=False):
        if prior.effective_to is None or prior.effective_to > following.effective_from:
            raise FiscalValidationError("overlapping Simples IBS/CBS election periods")
    local_date = instant.astimezone(ZoneInfo("America/Sao_Paulo")).date()
    if local_date < date(2027, 1, 1):
        return SimplesIbsCbsMode.NOT_EFFECTIVE_IN_SIMPLES_2026
    matching = [
        entry for entry in ordered
        if entry.effective_from <= instant and (
            entry.effective_to is None or instant < entry.effective_to
        )
    ]
    if len(matching) != 1:
        raise FiscalValidationError(
            "explicit effective Simples IBS/CBS election is required from 2027"
        )
    return matching[0].mode
