"""Isolation and integrity of host-owned fiscal policies in Bling multi-company mode."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from kordena_fiscal.application.bling_orders import BlingOrders
from kordena_fiscal.domain import ExecutionScope, FiscalEnvironment, FiscalValidationError
from kordena_fiscal.runtime.bling_preparation import BlingSalePreparer


def _orders(
    tenant: str,
    unit: str,
    company: str,
    *,
    correlation: str = "request",
    namespace: str | None = "bling",
) -> BlingOrders:
    scope = ExecutionScope(
        tenant_id=tenant,
        unit_id=unit,
        environment=FiscalEnvironment.HOMOLOGATION,
        correlation_id=correlation,
        host_namespace=namespace,
    )
    return cast(BlingOrders, SimpleNamespace(scope=scope, company_id=company))


def _fixture(orders: BlingOrders) -> dict[str, object]:
    return {
        "schema_version": 1,
        "policy_id": "fiscal-policy-" + orders.company_id,
        "version": 1,
        "company_id": orders.company_id,
        "tenant_id": orders.scope.tenant_id,
        "unit_id": orders.scope.unit_id,
        "environment": orders.scope.environment.value,
        "issuer_profile_id": "issuer",
        "issuer_profile_version": 1,
        "products": {"SKU": {"product_id": "product", "version": 1}},
        "payment_methods": {"1": "pix"},
        "series": 1,
        "sale_options": {},
        "rules": [{}],
    }


def _install(root: Path, orders: BlingOrders) -> tuple[Path, Path, str]:
    payload = json.dumps(
        _fixture(orders), ensure_ascii=True, separators=(",", ":")
    ).encode("utf-8")
    fingerprint = hashlib.sha256(payload).hexdigest()
    name = BlingSalePreparer.policy_scope_digest(orders.scope, orders.company_id)
    artifact = root / f"{name}.json"
    pin = root / f"{name}.sha256"
    artifact.write_bytes(payload)
    pin.write_text(fingerprint + "\n", encoding="ascii")
    return artifact, pin, fingerprint


def _preparer(root: Path) -> BlingSalePreparer:
    return BlingSalePreparer({
        "NFCORE_BLING_INSTALLATIONS_ENABLED": "true",
        "NFCORE_BLING_FISCAL_POLICY_ROOT": str(root),
    })


def test_policy_selection_isolated_by_tenant_unit_company(tmp_path: Path) -> None:
    instances = (
        _orders("tenant-A", "unit-A", "company-A"),
        _orders("tenant-B", "unit-A", "company-A"),
        _orders("tenant-A", "unit-B", "company-A"),
        _orders("tenant-A", "unit-A", "company-B"),
    )
    fingerprints = [_install(tmp_path, orders)[2] for orders in instances]
    assert len({
        BlingSalePreparer.policy_scope_digest(item.scope, item.company_id) for item in instances
    }) == len(instances)
    preparer = _preparer(tmp_path)
    for orders, fingerprint in zip(instances, fingerprints, strict=True):
        policy, digest = preparer.policy(orders)
        assert digest == fingerprint
        assert policy["company_id"] == orders.company_id
        assert policy["tenant_id"] == orders.scope.tenant_id
        assert policy["unit_id"] == orders.scope.unit_id


def test_policy_key_ignores_correlation_but_not_host_namespace() -> None:
    before = _orders("t", "u", "c", correlation="before")
    after = _orders("t", "u", "c", correlation="after")
    assert BlingSalePreparer.policy_scope_digest(before.scope, before.company_id) == (
        BlingSalePreparer.policy_scope_digest(after.scope, after.company_id)
    )
    with pytest.raises(FiscalValidationError, match="canonical host scope"):
        BlingSalePreparer.policy_scope_digest(
            _orders("t", "u", "c", namespace=None).scope, "c"
        )


def test_multi_mode_never_falls_back_to_global_policy(tmp_path: Path) -> None:
    orders = _orders("tenant-A", "unit-A", "company-A")
    artifact, _pin, fingerprint = _install(tmp_path, orders)
    preparer = BlingSalePreparer({
        "NFCORE_BLING_INSTALLATIONS_ENABLED": "true",
        "NFCORE_BLING_FISCAL_POLICY_FILE": str(artifact),
        "NFCORE_BLING_FISCAL_POLICY_SHA256": fingerprint,
    })
    with pytest.raises(FiscalValidationError, match="global policy is forbidden"):
        preparer.policy(orders)
    with pytest.raises(FiscalValidationError, match="directory unavailable"):
        BlingSalePreparer({"NFCORE_BLING_INSTALLATIONS_ENABLED": "true"}).policy(
            orders
        )
    # A directory containing only another tenant's policy must not be a fallback.
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(FiscalValidationError, match="digest unavailable"):
        _preparer(empty).policy(orders)


def test_policy_digest_and_content_must_match_per_partition(tmp_path: Path) -> None:
    orders = _orders("tenant", "unit", "company")
    artifact, pin, _digest = _install(tmp_path, orders)
    preparer = _preparer(tmp_path)
    assert preparer.policy(orders)[0]["policy_id"] == "fiscal-policy-company"

    artifact.write_bytes(artifact.read_bytes() + b" ")
    with pytest.raises(FiscalValidationError, match="integrity mismatch"):
        preparer.policy(orders)

    artifact, pin, _digest = _install(tmp_path, orders)
    pin.write_text("0" * 64 + "\n", encoding="ascii")
    with pytest.raises(FiscalValidationError, match="integrity mismatch"):
        preparer.policy(orders)

    pin.write_bytes(b"invalid\n")
    with pytest.raises(FiscalValidationError, match="digest invalid"):
        preparer.policy(orders)


def test_policy_cross_scope_payload_rejected_even_with_correct_pin(tmp_path: Path) -> None:
    target = _orders("tenant-A", "unit-A", "company-A")
    foreign = _orders("tenant-B", "unit-B", "company-B")
    artifact, pin, _ = _install(tmp_path, target)
    payload = json.dumps(_fixture(foreign)).encode()
    artifact.write_bytes(payload)
    pin.write_text(hashlib.sha256(payload).hexdigest() + "\n", encoding="ascii")
    with pytest.raises(FiscalValidationError, match="scope mismatch"):
        _preparer(tmp_path).policy(target)


def test_policy_symlink_and_oversized_payload_fail_closed(tmp_path: Path) -> None:
    orders = _orders("tenant", "unit", "company")
    artifact, pin, digest = _install(tmp_path, orders)
    preparer = _preparer(tmp_path)
    artifact.unlink()
    source = tmp_path / "other.json"
    source.write_bytes(b"synthetic")
    artifact.symlink_to(source)
    with pytest.raises(FiscalValidationError, match="symlink"):
        preparer.policy(orders)
    artifact.unlink()
    artifact.write_bytes(b"x" * 1_048_577)
    with pytest.raises(FiscalValidationError, match="integrity mismatch"):
        preparer.policy(orders)
    assert pin.read_text().strip() == digest


def test_legacy_single_company_pinned_policy_is_preserved(tmp_path: Path) -> None:
    orders = _orders("tenant", "unit", "company")
    artifact, _pin, digest = _install(tmp_path, orders)
    preparer = BlingSalePreparer({
        "NFCORE_BLING_FISCAL_POLICY_FILE": str(artifact),
        "NFCORE_BLING_FISCAL_POLICY_SHA256": digest,
    })
    assert preparer.policy(orders)[1] == digest
    with pytest.raises(FiscalValidationError, match="requires multi-installation"):
        BlingSalePreparer({
            "NFCORE_BLING_FISCAL_POLICY_ROOT": str(tmp_path),
        }).policy(orders)
