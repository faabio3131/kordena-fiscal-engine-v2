"""Deterministic NF-e calculations from explicit versioned fiscal rules.

No statutory tax rates are embedded here. Unsupported regimes/groups fail closed.
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
    fcp_rate: Decimal | None = None
    ipi_rate: Decimal | None = None
    ipi_enquiry_code: str | None = None
    ipi_calculation_mode: str | None = None
    ipi_cst: str | None = None
    ipi_unit_amount: Decimal | None = None
    st_rate: Decimal | None = None
    st_mva_rate: Decimal | None = None
    st_base_mode: str | None = None
    fcp_st_rate: Decimal | None = None
    difal_destination_rate: Decimal | None = None
    difal_interstate_rate: Decimal | None = None
    difal_destination_share: Decimal | None = None
    fcp_destination_rate: Decimal | None = None
    rtc_uf_rate: Decimal | None = None
    rtc_municipal_rate: Decimal | None = None
    rtc_cbs_rate: Decimal | None = None
    rtc_base_mode: str | None = None
    rtc_financial_mode: str | None = None

    def __post_init__(self) -> None:
        rates: tuple[Decimal, ...] = (self.icms_rate, self.pis_rate, self.cofins_rate)
        for candidate in (
            self.fcp_rate,
            self.ipi_rate,
            self.st_rate,
            self.fcp_st_rate,
            self.difal_destination_rate,
            self.difal_interstate_rate,
            self.difal_destination_share,
            self.fcp_destination_rate,
            self.rtc_uf_rate,
            self.rtc_municipal_rate,
            self.rtc_cbs_rate,
        ):
            if candidate is not None:
                rates += (candidate,)
        for rate in rates:
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
        if self.ipi_rate is not None and self.ipi_unit_amount is not None:
            raise FiscalValidationError("IPI cannot mix ad valorem and per-unit modes")
        ipi_taxed = self.ipi_rate is not None or self.ipi_unit_amount is not None
        ipi_non_taxed = self.ipi_cst in {"51", "52", "53", "54", "55"}
        if ipi_taxed:
            if self.ipi_enquiry_code is None:
                raise FiscalValidationError("IPI rate and legal framing must be specified together")
            expected_mode = "net_icms_excluded" if self.ipi_rate is not None else "per_taxable_unit"
            if self.ipi_calculation_mode != expected_mode:
                raise FiscalValidationError("IPI calculation mode must be explicitly reviewed")
            if self.ipi_cst not in {None, "50"}:
                raise FiscalValidationError("taxed output IPI requires CST 50")
        elif ipi_non_taxed:
            if self.ipi_enquiry_code is None or self.ipi_calculation_mode != "non_taxed":
                raise FiscalValidationError(
                    "non-taxed IPI requires approved legal framing and mode"
                )
        elif any(
            v is not None for v in (self.ipi_cst, self.ipi_enquiry_code, self.ipi_calculation_mode)
        ):
            raise FiscalValidationError("IPI configuration must select a supported output CST")
        if self.ipi_unit_amount is not None and (
            not isinstance(self.ipi_unit_amount, Decimal)
            or not self.ipi_unit_amount.is_finite()
            or not 0 <= self.ipi_unit_amount <= Decimal("9999999.9999")
            or self.ipi_unit_amount != self.ipi_unit_amount.quantize(Decimal("0.0001"))
        ):
            raise FiscalValidationError("IPI per-unit amount must have 4 decimal precision")
        if self.ipi_enquiry_code is not None and (
            not isinstance(self.ipi_enquiry_code, str)
            or len(self.ipi_enquiry_code) != 3
            or not self.ipi_enquiry_code.isascii()
            or not self.ipi_enquiry_code.isdigit()
        ):
            raise FiscalValidationError("IPI legal framing must have three digits")
        st_facts = (self.st_rate, self.st_mva_rate, self.st_base_mode)
        if any(v is not None for v in st_facts) and not all(v is not None for v in st_facts):
            raise FiscalValidationError("ICMS ST requires explicit rate, MVA and base mode")
        if self.st_base_mode is not None and self.st_base_mode not in {
            "net_mva",
            "net_plus_ipi_mva",
        }:
            raise FiscalValidationError("unsupported ICMS ST calculation base")
        if self.st_mva_rate is not None and (
            not isinstance(self.st_mva_rate, Decimal)
            or not self.st_mva_rate.is_finite()
            or not 0 <= self.st_mva_rate <= 1000
            or self.st_mva_rate != self.st_mva_rate.quantize(Decimal("0.0001"))
        ):
            raise FiscalValidationError("ICMS ST MVA must be an explicit valid percentage")
        if self.fcp_st_rate is not None and self.st_rate is None:
            raise FiscalValidationError("FCP-ST requires approved ICMS ST calculation")
        difal_facts = (
            self.difal_destination_rate,
            self.difal_interstate_rate,
            self.difal_destination_share,
        )
        if any(v is not None for v in difal_facts) and not all(v is not None for v in difal_facts):
            raise FiscalValidationError(
                "DIFAL requires complete destination, origin and share rates"
            )
        if self.fcp_destination_rate is not None and self.difal_destination_rate is None:
            raise FiscalValidationError("destination FCP requires an approved DIFAL policy")
        if self.difal_interstate_rate is not None and self.difal_interstate_rate not in {
            Decimal("4"),
            Decimal("7"),
            Decimal("12"),
        }:
            raise FiscalValidationError("DIFAL interstate rate must match an authorized XML value")
        if self.difal_destination_share is not None and self.difal_destination_share != 100:
            raise FiscalValidationError("DIFAL 2026 requires full destination share")
        rtc_facts = (
            self.rtc_uf_rate,
            self.rtc_municipal_rate,
            self.rtc_cbs_rate,
            self.rtc_base_mode,
            self.rtc_financial_mode,
        )
        if any(v is not None for v in rtc_facts) and not all(v is not None for v in rtc_facts):
            raise FiscalValidationError("RTC requires complete explicit 2026 calculation policy")
        if self.rtc_base_mode is not None and self.rtc_base_mode not in {
            "net",
            "net_less_icms_pis_cofins",
        }:
            raise FiscalValidationError("unsupported RTC base mode")
        if self.rtc_financial_mode is not None and self.rtc_financial_mode != "informational_2026":
            raise FiscalValidationError("RTC financial mode requires a 2026 authoritative rule")


@dataclass(frozen=True, slots=True)
class NfeCalculatedTaxes:
    icms_base: Decimal
    icms_amount: Decimal
    pis_base: Decimal
    pis_amount: Decimal
    cofins_base: Decimal
    cofins_amount: Decimal
    fcp_amount: Decimal = Decimal("0.00")
    ipi_amount: Decimal = Decimal("0.00")
    ipi_base: Decimal = Decimal("0.00")
    ipi_taxable_quantity: Decimal = Decimal("0.0000")
    st_base: Decimal = Decimal("0.00")
    st_amount: Decimal = Decimal("0.00")
    fcp_st_amount: Decimal = Decimal("0.00")
    difal_base: Decimal = Decimal("0.00")
    difal_amount: Decimal = Decimal("0.00")
    fcp_destination_amount: Decimal = Decimal("0.00")
    rtc_base: Decimal = Decimal("0.00")
    rtc_ibs_uf_amount: Decimal = Decimal("0.00")
    rtc_ibs_municipal_amount: Decimal = Decimal("0.00")
    rtc_cbs_amount: Decimal = Decimal("0.00")


def calculate_nfe_line(
    decision: TaxDecision,
    *,
    net_amount: Decimal,
    regime: TaxRegimeCode,
    interstate_final_consumer: bool = False,
    taxable_quantity: Decimal | None = None,
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
    rtc_fields = (
        outcome.ibs_cbs_classification_code,
        outcome.ibs_cbs_cst_code,
        outcome.ibs_cbs_classification_table_version,
    )
    if any(v is not None for v in rtc_fields) and not all(v is not None for v in rtc_fields):
        raise FiscalValidationError("RTC classification, CST and table version are mandatory")
    if (policy.rtc_uf_rate is None) != (outcome.ibs_cbs_cst_code is None):
        raise FiscalValidationError("RTC tax rule and calculation parameters must agree")
    if policy.rtc_uf_rate is not None:
        classification = outcome.ibs_cbs_classification_code
        if (
            outcome.ibs_cbs_cst_code != "000"
            or classification is None
            or len(classification) != 6
            or not classification.isascii()
            or not classification.isdigit()
        ):
            raise FiscalValidationError("only explicitly classified RTC CST 000 is supported")
    code = outcome.icms_code
    simple = regime in {TaxRegimeCode.SIMPLES_NACIONAL, TaxRegimeCode.MEI}
    if simple and code not in {"102", "103", "300", "400"}:
        raise FiscalValidationError("unsupported Simples NF-e calculation group")
    if not simple and code not in {"00", "10", "40", "41", "50"}:
        raise FiscalValidationError("unsupported regular NF-e calculation group")
    taxable_icms = code in {"00", "10"}
    if policy.fcp_rate is not None and not taxable_icms:
        raise FiscalValidationError("FCP configuration requires supported ICMS 00/10 group")
    if (policy.st_rate is None) != (code != "10"):
        raise FiscalValidationError("ICMS 10 requires ST policy and other groups forbid it")
    if interstate_final_consumer and (code != "00" or policy.difal_destination_rate is None):
        raise FiscalValidationError("interstate final consumer requires approved DIFAL for ICMS 00")
    if not interstate_final_consumer and policy.difal_destination_rate is not None:
        raise FiscalValidationError("DIFAL policy requires interstate final consumer")
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
    fcp = (icms_base * (policy.fcp_rate or 0) / 100).quantize(_CENT, rounding=ROUND_HALF_UP)
    ipi = (net_amount * (policy.ipi_rate or 0) / 100).quantize(_CENT, rounding=ROUND_HALF_UP)
    if policy.ipi_unit_amount is not None:
        if (
            not isinstance(taxable_quantity, Decimal)
            or not taxable_quantity.is_finite()
            or taxable_quantity <= 0
            or taxable_quantity != taxable_quantity.quantize(Decimal("0.0001"))
        ):
            raise FiscalValidationError("IPI per-unit calculation requires exact taxable quantity")
        ipi = (taxable_quantity * policy.ipi_unit_amount).quantize(_CENT, rounding=ROUND_HALF_UP)
    st_base = st_amount = fcp_st = Decimal("0.00")
    if policy.st_rate is not None:
        st_net = net_amount + (ipi if policy.st_base_mode == "net_plus_ipi_mva" else 0)
        assert policy.st_mva_rate is not None
        st_base = (st_net * (Decimal(1) + policy.st_mva_rate / 100)).quantize(
            _CENT, rounding=ROUND_HALF_UP
        )
        gross_st = (st_base * policy.st_rate / 100).quantize(_CENT, rounding=ROUND_HALF_UP)
        st_amount = gross_st - icms
        if st_amount < 0:
            raise FiscalValidationError("ICMS ST cannot be negative; review the approved rule")
        fcp_st = (st_base * (policy.fcp_st_rate or 0) / 100).quantize(_CENT, rounding=ROUND_HALF_UP)
    difal_base = difal_amount = fcp_destination = Decimal("0.00")
    if interstate_final_consumer:
        assert policy.difal_destination_rate is not None
        assert policy.difal_interstate_rate is not None
        difal_base = net_amount
        difference = policy.difal_destination_rate - policy.difal_interstate_rate
        if difference < 0:
            raise FiscalValidationError("DIFAL destination rate below interstate rate")
        difal_amount = (difal_base * difference / 100).quantize(_CENT, rounding=ROUND_HALF_UP)
        fcp_destination = (difal_base * (policy.fcp_destination_rate or 0) / 100).quantize(
            _CENT, rounding=ROUND_HALF_UP
        )
    rtc_base = rtc_ibs_uf = rtc_ibs_mun = rtc_cbs = Decimal("0.00")
    if policy.rtc_uf_rate is not None:
        rtc_base = (
            net_amount - icms - pis - cofins
            if policy.rtc_base_mode == "net_less_icms_pis_cofins"
            else net_amount
        )
        if rtc_base < 0:
            raise FiscalValidationError("RTC base became negative under approved exclusions")
        assert policy.rtc_municipal_rate is not None and policy.rtc_cbs_rate is not None
        rtc_ibs_uf = (rtc_base * policy.rtc_uf_rate / 100).quantize(_CENT, rounding=ROUND_HALF_UP)
        rtc_ibs_mun = (rtc_base * policy.rtc_municipal_rate / 100).quantize(
            _CENT, rounding=ROUND_HALF_UP
        )
        rtc_cbs = (rtc_base * policy.rtc_cbs_rate / 100).quantize(_CENT, rounding=ROUND_HALF_UP)
    return NfeCalculatedTaxes(
        icms_base=icms_base,
        icms_amount=icms,
        pis_base=pis_base,
        pis_amount=pis,
        cofins_base=cofins_base,
        cofins_amount=cofins,
        fcp_amount=fcp,
        ipi_amount=ipi,
        ipi_base=net_amount if policy.ipi_rate is not None else Decimal("0.00"),
        ipi_taxable_quantity=(
            taxable_quantity
            if policy.ipi_unit_amount is not None and taxable_quantity is not None
            else Decimal("0.0000")
        ),
        st_base=st_base,
        st_amount=st_amount,
        fcp_st_amount=fcp_st,
        difal_base=difal_base,
        difal_amount=difal_amount,
        fcp_destination_amount=fcp_destination,
        rtc_base=rtc_base,
        rtc_ibs_uf_amount=rtc_ibs_uf,
        rtc_ibs_municipal_amount=rtc_ibs_mun,
        rtc_cbs_amount=rtc_cbs,
    )
