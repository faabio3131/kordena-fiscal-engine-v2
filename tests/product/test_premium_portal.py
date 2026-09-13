from pathlib import Path


PORTAL_ROOT = Path(__file__).resolve().parents[2] / "portal"


def _read(name: str) -> str:
    return (PORTAL_ROOT / name).read_text(encoding="utf-8")


def test_portal_has_accessible_shell_and_critical_confirmation() -> None:
    html = _read("index.html")
    assert 'lang="pt-BR"' in html
    assert 'href="#main"' in html
    assert 'aria-label="Navegação principal"' in html
    assert 'aria-live="polite"' in html
    assert '<dialog id="confirm-dialog"' in html
    assert 'aria-labelledby="dialog-title"' in html
    assert 'script src="app.js" defer' in html


def test_portal_covers_required_premium_product_surfaces() -> None:
    script = _read("app.js")
    required = {
        "onboarding",
        "companies",
        "units",
        "environments",
        "capabilities",
        "documents",
        "issuances",
        "errors",
        "reconciliation",
        "webhooks",
        "integrations",
        "certificates",
        "providers",
        "usage",
        "billing",
        "plans",
        "audit",
        "support",
        "settings",
    }
    for surface in required:
        assert f'["{surface}",' in script


def test_portal_preserves_production_and_secret_boundaries() -> None:
    html = _read("index.html")
    script = _read("app.js")
    combined = html + script
    assert "PROD BLOQUEADA" in script
    assert "HUMAN_APPROVAL_REQUIRED" in script
    assert "BLOCKED_EXTERNAL" in script
    assert "Sem segredo em tela" in script
    assert "Nenhuma ação desta superfície ativa produção" in html
    assert "BEGIN PRIVATE KEY" not in combined
    assert "PRODUCTION_APPROVED" not in combined
    assert "window.localStorage" not in combined
    assert "document.cookie" not in combined
    assert "fetch(" not in combined


def test_portal_supports_responsive_and_reduced_motion_modes() -> None:
    css = _read("styles.css")
    assert "@media (max-width: 1050px)" in css
    assert "@media (max-width: 760px)" in css
    assert "@media (max-width: 480px)" in css
    assert "@media (prefers-reduced-motion: reduce)" in css
    assert ":focus-visible" in css
