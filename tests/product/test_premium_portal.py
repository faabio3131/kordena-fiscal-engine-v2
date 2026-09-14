from pathlib import Path

PORTAL_ROOT = Path(__file__).resolve().parents[2] / "portal"


def _read(name: str) -> str:
    return (PORTAL_ROOT / name).read_text(encoding="utf-8")


def test_portal_has_accessible_authenticated_shell_and_governed_operation_dialog() -> None:
    html = _read("index.html")
    assert 'lang="pt-BR"' in html
    assert 'href="#main"' in html
    assert 'aria-label="Navegação principal"' in html
    assert 'aria-live="polite"' in html
    assert 'id="login-form"' in html
    assert 'id="logout-action"' in html
    assert '<dialog id="operation-dialog"' in html
    assert 'aria-labelledby="operation-dialog-title"' in html
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
        "users",
        "usage",
        "billing",
        "plans",
        "audit",
        "support",
        "settings",
    }
    for surface in required:
        assert f'["{surface}",' in script


def test_portal_is_connected_to_authenticated_backend_without_local_authority() -> None:
    html = _read("index.html")
    script = _read("app.js")
    combined = html + script

    assert 'fetch(path' in script
    assert '/v1/auth/login' in script
    assert '/v1/auth/logout' in script
    assert '/v1/portal/bootstrap' in script
    assert '/v1/portal/surfaces/' in script
    assert '/v1/portal/operations/' in script
    assert 'credentials: "same-origin"' in script
    assert 'X-CSRF-Token' in script
    assert 'Idempotency-Key' in script
    assert "window.localStorage" not in combined
    assert "window.sessionStorage" not in combined
    assert "X-FM-Tenant-Id" not in script
    assert "X-FM-Unit-Id" not in script
    assert "BEGIN PRIVATE KEY" not in combined
    assert "PRODUCTION_APPROVED" not in combined


def test_portal_preserves_production_and_secret_boundaries() -> None:
    html = _read("index.html")
    script = _read("app.js")
    combined = html + script
    assert "HUMAN_APPROVAL_REQUIRED" in script
    assert "Produção permanece bloqueada" in script
    assert "material secreto nunca é exibido" in script
    assert "O navegador nunca é autoridade" in html
    assert "BEGIN PRIVATE KEY" not in combined
    assert "PRIVATE KEY-----" not in combined
    assert "CSC real" not in combined


def test_portal_supports_responsive_and_reduced_motion_modes() -> None:
    css = _read("styles.css")
    assert "@media (max-width: 1050px)" in css
    assert "@media (max-width: 760px)" in css
    assert "@media (max-width: 480px)" in css
    assert "@media (prefers-reduced-motion: reduce)" in css
    assert ":focus-visible" in css
