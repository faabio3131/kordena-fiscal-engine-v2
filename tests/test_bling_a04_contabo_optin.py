"""A-04: static deployment gates; overlay is NEVER loaded by routine deploy."""
from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_bling_worker_overlay_has_explicit_opt_in_and_no_public_ingress() -> None:
    path = ROOT / "deploy/contabo/compose.bling.worker.opt-in.yml"
    overlay = yaml.safe_load(path.read_text(encoding="utf-8"))
    services = overlay["services"]
    assert list(services) == ["nfcore-bling-worker"]
    worker = services["nfcore-bling-worker"]
    assert worker["profiles"] == ["bling-worker-authorized"]
    assert worker["restart"] == "no"
    assert worker["read_only"] is True
    assert worker["cap_drop"] == ["ALL"]
    assert worker["security_opt"] == ["no-new-privileges:true"]
    assert worker["user"] == "10001:10001"
    assert "ports" not in worker
    assert "expose" not in worker
    assert "proxy-net" not in worker["networks"]
    assert worker["depends_on"]["nfcore-db"]["condition"] == "service_healthy"
    assert worker["environment"]["NFCORE_WORKER_CONNECTOR"] == "bling-multi"
    assert worker["environment"]["NFCORE_BLING_INSTALLATIONS_ENABLED"] == "true"
    assert worker["volumes"][0]["read_only"] is True
    assert worker["volumes"][0]["bind"]["create_host_path"] is False
    assert worker["healthcheck"]["test"][2:4] == [
        "-m", "kordena_fiscal.runtime.worker_health",
    ]


def test_bling_worker_never_participates_in_auto_deploy() -> None:
    deployment = (ROOT / "deploy/contabo/deploy.sh").read_text(encoding="utf-8")
    base = (ROOT / "deploy/contabo/compose.prod.yml").read_text(encoding="utf-8")
    installer = (ROOT / "deploy/contabo/install.sh").read_text(encoding="utf-8")
    for content in (deployment, base, installer):
        assert "compose.bling.worker.opt-in.yml" not in content
        assert "nfcore-bling-worker" not in content
    assert "nfcore-bling-worker" not in yaml.safe_load(base)["services"]
    assert "compose.bling.worker.opt-in.yml" in (
        ROOT / "docs/integrations/bling-a03-a05-runbook.md"
    ).read_text(encoding="utf-8")


def test_example_secret_config_contains_no_actual_provider_credentials() -> None:
    template = (ROOT / "deploy/contabo/.env.bling.worker.example").read_text(
        encoding="utf-8",
    )
    assert "NFCORE_BLING_INSTALLATIONS_ENABLED=true" in template
    assert "NFCORE_WORKER_CONNECTOR=bling-multi" in template
    assert "NFCORE_BLING_CLIENT_ID=\n" in template
    assert "NFCORE_BLING_APPROVED_SCOPES=\n" in template
    assert "NFCORE_BLING_COMPANY_ID=" not in template
