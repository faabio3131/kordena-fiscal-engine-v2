from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_api_image_contains_governed_staging_test_account_command() -> None:
    dockerfile = (ROOT / "Dockerfile.api").read_text(encoding="utf-8")

    assert (
        "COPY scripts/admin/provision_staging_test_account.py "
        "./scripts/admin/provision_staging_test_account.py"
    ) in dockerfile
