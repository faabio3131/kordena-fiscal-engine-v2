"""Quota guards require canonical subscription and durable usage snapshot."""
import pytest

from kordena_fiscal.product.commercial_entitlement_guards import resolve_plan_quota
from kordena_fiscal.product.pricing import CommercialPricingError


@pytest.mark.parametrize("plan,docs,cnpjs,rpm", [
    ("starter", 1000, 1, 120), ("pro", 5000, 3, 600),
    ("business", 25000, 15, 2400), ("enterprise", None, None, None),
])
def test_four_plan_limits(plan: str, docs: int | None, cnpjs: int | None,
                          rpm: int | None) -> None:
    quota = resolve_plan_quota(plan_id=plan, catalog_version=2, status="active")
    assert (quota.monthly_documents, quota.max_cnpjs, quota.rpm) == (docs, cnpjs, rpm)
    if docs is not None:
        quota.require_document_reservation(used_documents=docs-1, in_flight_reservations=0)
        with pytest.raises(CommercialPricingError, match="document quota"):
            quota.require_document_reservation(used_documents=docs-1, in_flight_reservations=1)
    if cnpjs is not None:
        quota.require_cnpj_registration(distinct_cnpjs=cnpjs, new_cnpj=False)
        with pytest.raises(CommercialPricingError, match="CNPJ limit"):
            quota.require_cnpj_registration(distinct_cnpjs=cnpjs, new_cnpj=True)
    if rpm is not None:
        quota.require_request_reservation(observed_last_60_seconds=rpm-1, in_flight_reservations=0)
        with pytest.raises(CommercialPricingError, match="RPM limit"):
            quota.require_request_reservation(observed_last_60_seconds=rpm-1, in_flight_reservations=1)


def test_trial_uses_50_document_hard_limit() -> None:
    quota = resolve_plan_quota(plan_id="enterprise", catalog_version=2, status="trial")
    quota.require_document_reservation(used_documents=49, in_flight_reservations=0)
    with pytest.raises(CommercialPricingError, match="document quota"):
        quota.require_document_reservation(used_documents=49, in_flight_reservations=1)


@pytest.mark.parametrize("plan,version,status", [
    ("unknown",2,"active"),("starter",1,"active"),("starter",2,"cancelled"),
    ("essencial",2,"active"),("enterprise",0,"trial"),
])
def test_no_legacy_plan_wrong_version_or_suspended_subscription(
    plan: str, version: int, status: str,
) -> None:
    with pytest.raises(CommercialPricingError):
        resolve_plan_quota(plan_id=plan, catalog_version=version, status=status)


@pytest.mark.parametrize("invalid", [-1, None, 1.2, True])
def test_untrusted_or_missing_counters_fail_closed(invalid: object) -> None:
    quota = resolve_plan_quota(plan_id="starter", catalog_version=2, status="active")
    with pytest.raises(CommercialPricingError):
        quota.require_document_reservation(
            used_documents=invalid, in_flight_reservations=0  # type: ignore[arg-type]
        )
    with pytest.raises(CommercialPricingError):
        quota.require_cnpj_registration(
            distinct_cnpjs=invalid, new_cnpj=True  # type: ignore[arg-type]
        )
