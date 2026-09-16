from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PREFLIGHT = ROOT / "scripts" / "ci" / "staging_preflight.sh"
DEPLOY = ROOT / "scripts" / "ci" / "run_staging_deploy.sh"
DRIVER = "scripts/deploy/drivers/unconfigured.sh"


def _env() -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "NFCORE_STAGING_BASE_URL": "https://api.staging.example.invalid",
            "NFCORE_STAGING_PORTAL_URL": "https://portal.staging.example.invalid",
            "NFCORE_STAGING_DEPLOY_DRIVER": DRIVER,
            "DATABASE_URL": "postgresql://nfcore@localhost/nfcore",
            "NFCORE_ENVIRONMENT": "staging",
            "NFCORE_PERSISTENCE_BACKEND": "postgres",
            "NFCORE_SECRET_BACKEND": "external",
            "NFCORE_REQUIRE_HTTPS": "true",
        }
    )
    return env


def test_staging_preflight_accepts_only_complete_fail_closed_contract() -> None:
    result = subprocess.run(
        ["sh", str(PREFLIGHT)],
        cwd=ROOT,
        env=_env(),
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert result.stdout.strip() == "staging preflight: PASS"


def test_staging_preflight_reports_missing_external_portal_url() -> None:
    env = _env()
    env.pop("NFCORE_STAGING_PORTAL_URL")

    result = subprocess.run(
        ["sh", str(PREFLIGHT)],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 42
    assert "BLOCKED_EXTERNAL missing=NFCORE_STAGING_PORTAL_URL" in result.stdout


def test_unconfigured_driver_advertises_contract_but_refuses_real_operations() -> None:
    contract = subprocess.run(
        ["sh", DRIVER, "contract"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    deploy = subprocess.run(
        ["sh", DRIVER, "deploy", "0" * 40],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert contract.returncode == 0
    assert contract.stdout.strip() == "nfcore-staging-driver-v1"
    assert deploy.returncode == 42
    assert "BLOCKED_EXTERNAL" in deploy.stdout


def test_staging_deploy_rejects_mutable_or_malformed_revision_before_backup() -> None:
    env = _env()
    env["NFCORE_DEPLOY_REVISION"] = "main"

    result = subprocess.run(
        ["sh", str(DEPLOY)],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    assert "immutable 40-hex revision is required" in result.stdout
