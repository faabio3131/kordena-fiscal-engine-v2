"""Fail-closed operator procedure gates; no real CLI/API operation."""
from __future__ import annotations

import importlib.util
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "sealed_operator", Path(__file__).parents[2] /
    "scripts/deploy/provision_worker_sealed_identity.py",
)
operator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(operator)


@pytest.mark.parametrize("values", [[], ["unlimited"], ["721h"], ["0h"], ["168h", "7200h"]])
def test_expiry_policy_blocks_unsafe_creation(values):
    with pytest.raises(operator.Blocked):
        operator.expiry_limit({"listPolicy": {"allowedValues": values}})


def test_expiry_policy_is_google_enforced():
    assert operator.expiry_limit({"listPolicy": {"allowedValues": ["168h"]}}) == 168


@pytest.mark.parametrize("sealed", [False, None])
def test_seal_required_before_google_key_creation(monkeypatch, sealed):
    monkeypatch.setattr(operator, "railway", lambda *_: {
        "environment": {"variables": {"pageInfo": {"hasNextPage": False}, "edges": [
            {"node": {"name": operator.VARIABLE, "serviceId": operator.SERVICE,
                      "isSealed": sealed}},
        ]}},
    })
    with pytest.raises(operator.Blocked, match="already be SEALED"):
        operator.sealed("synthetic-never-transmitted")


@pytest.mark.parametrize("days", [-1, 31, 36500])
def test_actual_iam_expiry_not_operator_invented(days):
    now = datetime.now(UTC)
    key = {"name": "projects/p/serviceAccounts/s/keys/" + "a" * 40,
           "validAfterTime": (now - timedelta(hours=1)).isoformat(),
           "validBeforeTime": (now + timedelta(days=days)).isoformat()}
    with pytest.raises(operator.Blocked):
        operator.rotation_metadata(key, "a" * 40, now)


def test_receipt_uses_actual_iam_times():
    now = datetime.now(UTC)
    key = {"name": "projects/p/serviceAccounts/s/keys/" + "a" * 40,
           "validAfterTime": (now - timedelta(hours=1)).isoformat(),
           "validBeforeTime": (now + timedelta(days=7)).isoformat()}
    receipt = operator.rotation_metadata(key, "a" * 40, now)
    assert receipt["NFCORE_WORKER_GSM_KEY_NOT_AFTER"] == key["validBeforeTime"]


def test_no_redirect_with_auth_headers():
    with pytest.raises(operator.Blocked, match="redirect"):
        operator.NoRedirect().redirect_request(None, None, 302, "", {}, "https://evil.invalid")
