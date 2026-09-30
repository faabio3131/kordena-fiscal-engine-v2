from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "ci" / "commercial_channel_validation.py"


def _run(
    *args: str,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def _ready_env() -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "NFCORE_STAGING_STATE": "STAGING_DEPLOYED_AND_E2E_VALIDATED",
            "NFCORE_COMMERCIAL_CHANNEL_REAL_VALIDATION_ENABLED": "true",
            "NFCORE_COMMERCIAL_CHANNEL_PROVIDER": "cakto",
            "NFCORE_COMMERCIAL_CHANNEL_CALLBACK_URL": (
                "https://staging.nfcore.example.com/webhooks/cakto"
            ),
            "NFCORE_COMMERCIAL_CHANNEL_CHECKOUT_URL": (
                "https://checkout.example.com/offer?product=growth"
            ),
        }
    )
    return env


def test_cl16a_contract_is_provider_neutral() -> None:
    result = _run("--contract")

    assert result.returncode == 0
    assert result.stdout.strip() == "nfcore-commercial-channel-validation-v1"


def test_cl16a_preflight_blocks_until_staging_is_really_validated() -> None:
    result = _run(env=os.environ.copy())

    assert result.returncode == 42
    assert "BLOCKED_EXTERNAL reason=staging_not_validated" in result.stdout


def test_cl16a_preflight_never_promotes_channel_readiness_by_itself() -> None:
    result = _run(env=_ready_env())

    assert result.returncode == 0
    assert "READY_FOR_REAL_VALIDATION" in result.stdout
    assert "COMMERCIAL_CHANNEL_READY" not in result.stdout


def test_cl16a_preflight_rejects_non_https_or_credentialed_urls() -> None:
    env = _ready_env()
    env["NFCORE_COMMERCIAL_CHANNEL_CALLBACK_URL"] = "http://staging.example.com/callback"
    insecure = _run(env=env)
    assert insecure.returncode == 1
    assert "FAIL" in insecure.stdout

    env = _ready_env()
    env["NFCORE_COMMERCIAL_CHANNEL_CALLBACK_URL"] = (
        "https://user:password@staging.example.com/callback"
    )
    credentialed = _run(env=env)
    assert credentialed.returncode == 1
    assert "FAIL" in credentialed.stdout


def test_cl16a_evidence_contract_requires_real_lifecycle_set(tmp_path: Path) -> None:
    evidence_path = tmp_path / "evidence.json"
    evidence_path.write_text(
        json.dumps(
            {
                "provider_id": "cakto",
                "environment": "staging",
                "evidence": {
                    "account_kyc": "evidence:kyc/sha256-a1",
                    "product_plan_configuration": "evidence:product/sha256-b2",
                    "checkout": "evidence:checkout/sha256-c3",
                    "webhook_registration": "evidence:webhook/sha256-d4",
                    "authenticated_event": "evidence:event/sha256-e5",
                    "controlled_purchase": "evidence:purchase/sha256-f6",
                    "refund_or_cancel": "evidence:refund/sha256-g7",
                    "reconciliation": "evidence:reconcile/sha256-h8",
                },
            }
        ),
        encoding="utf-8",
    )

    result = _run("--evidence", str(evidence_path))

    assert result.returncode == 0
    assert "EVIDENCE_SET_COMPLETE" in result.stdout
    assert "COMMERCIAL_CHANNEL_READY" not in result.stdout


def test_cl16a_evidence_contract_blocks_when_refund_or_reconciliation_is_missing(
    tmp_path: Path,
) -> None:
    evidence_path = tmp_path / "evidence.json"
    evidence_path.write_text(
        json.dumps(
            {
                "provider_id": "cakto",
                "environment": "staging",
                "evidence": {
                    "account_kyc": "evidence:kyc/a1",
                    "product_plan_configuration": "evidence:product/b2",
                    "checkout": "evidence:checkout/c3",
                    "webhook_registration": "evidence:webhook/d4",
                    "authenticated_event": "evidence:event/e5",
                    "controlled_purchase": "evidence:purchase/f6",
                },
            }
        ),
        encoding="utf-8",
    )

    result = _run("--evidence", str(evidence_path))

    assert result.returncode == 42
    assert "missing_evidence_refund_or_cancel" in result.stdout
