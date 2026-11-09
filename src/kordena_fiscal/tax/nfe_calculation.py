"""Deterministic arithmetic for explicit, versioned NF-e rate parameters.

No statutory rate or tax exemption is supplied by this module. Parameters must
come from the winning canonical rule, with its legal source and effective dates.
Unsupported calculation groups fail closed instead of being converted to zero.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING, Literal

from kordena_fiscal.domain import FiscalValidationError, TaxRegimeCode

if TYPE_CHECKING:
    from .models import TaxDecision

_CENT = Decimal("0.01")


@dataclass(frozen=True, slots=True)
class NfeRateParameters:
    icms_rate: Decimal
    pis_rate: Decimal
    cofins_rate: Decimal
    pis_base: Literal["net", "net_less_icms"]
    cofins_base: Literal["net", "net_less_icms"]

    def __post_init__(self) -> None:
        for rate in (self.icms_rate, self.pis_rate, self.cofins_rate):
            if (
                not isinstance(rate, Decimal)
                or not rate.is_finite()
                or not 0 <= rate <= 100
                or rate != rate.quantize(Decimal("0.0001"))
            ):
                raise FiscalValidationError("explicit NF-e rates require 0 to 100 with 4 decimals")
        if self.pis_base not in {"net", "net_less_icms"} or self.cofins_base not in {
            "net",
            "net_less_icms",
        }:
            raise FiscalValidationError("explicit NF-e contribution base policy is required")


@dataclass(frozen=True, slots=True)
class NfeCalculatedTaxes:
    icms_base: Decimal
    icms_amount: Decimal
    pis_base: Decimal
    pis_amount: Decimal
    cofins_base: Decimal
    cofins_amount: Decimal


def calculate_nfe_line(
    decision: TaxDecision,
    *,
    net_amount: Decimal,
    regime: TaxRegimeCode,
) -> NfeCalculatedTaxes:
    outcome = decision.outcome
    policy = outcome.nfe_rates
    if policy is None:
        raise FiscalValidationError(
            "winning fiscal rule has no approved NF-e calculation parameters"
        )
    if not isinstance(net_amount, Decimal) or not net_amount.is_finite() or net_amount < 0:
        raise FiscalValidationError("NF-e tax base must be finite and non-negative")
    if net_amount != net_amount.quantize(_CENT):
        raise FiscalValidationError("NF-e tax base must use cent precision")
    if outcome.ibs_cbs_classification_code is not None or outcome.ibs_cbs_cst_code is not None:
        raise FiscalValidationError(
            "RTC calculation requires its own authoritative calculation path"
        )
    code = outcome.icms_code
    simple = regime in {TaxRegimeCode.SIMPLES_NACIONAL, TaxRegimeCode.MEI}
    if simple and code not in {"102", "103", "300", "400"}:
        raise FiscalValidationError("unsupported Simples NF-e calculation group")
    if not simple and code not in {"00", "40", "41", "50"}:
        raise FiscalValidationError("unsupported regular NF-e calculation group")
    taxable_icms = code == "00"
    if not taxable_icms and policy.icms_rate != 0:
        raise FiscalValidationError("non-taxed ICMS group conflicts with nonzero rate")
    icms_base = net_amount if taxable_icms else Decimal("0.00")
    icms = (icms_base * policy.icms_rate / 100).quantize(_CENT, rounding=ROUND_HALF_UP)

    def contribution(code: str, rate: Decimal, base_policy: str) -> tuple[Decimal, Decimal]:
        if code in {"01", "02"}:
            base = net_amount - icms if base_policy == "net_less_icms" else net_amount
            return base, (base * rate / 100).quantize(_CENT, rounding=ROUND_HALF_UP)
        if code not in {"04", "06", "07", "08", "09"}:
            raise FiscalValidationError("unsupported NF-e contribution calculation group")
        if rate != 0:
            raise FiscalValidationError("non-taxed contribution group conflicts with nonzero rate")
        return Decimal("0.00"), Decimal("0.00")

    pis_base, pis = contribution(outcome.pis_cst, policy.pis_rate, policy.pis_base)
    cofins_base, cofins = contribution(outcome.cofins_cst, policy.cofins_rate, policy.cofins_base)
    return NfeCalculatedTaxes(icms_base, icms, pis_base, pis, cofins_base, cofins)
