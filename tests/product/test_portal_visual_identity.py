from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PORTAL = ROOT / "portal"


def read(name: str) -> str:
    return (PORTAL / name).read_text(encoding="utf-8")


def test_v1_commercial_identity_is_applied() -> None:
    html = read("index.html")
    css = read("styles.css")

    assert "FM Fiscal V1.0" in html
    assert "Infraestrutura fiscal. Sob controle." in html
    assert "Commercial Launch Edition · V1.0" in html
    assert "--brand-primary: #2e6ae6" in css
    assert "--brand-cyan: #5ee8ff" in css


def test_brand_color_is_not_operational_success_color() -> None:
    css = read("styles.css")

    assert "--brand-primary: #2e6ae6" in css
    assert "--success: #34d399" in css
    assert "background: var(--success)" in css


def test_standalone_surface_does_not_expose_internal_product_names() -> None:
    app = read("app.js")

    for internal_name in ("Kordena", "Iron Fit", "Vendedor IA", "CampaIA"):
        assert internal_name not in app


def test_commercial_surface_does_not_claim_internal_release_language() -> None:
    html = read("index.html")
    app = read("app.js")

    assert "Release Candidate interno" not in html
    assert "DEMO INTERNA" not in app
    assert "Dados exibidos nesta superfície são sintéticos" in html


def test_v1_scope_is_explicit_and_does_not_advertise_v2_documents() -> None:
    app = read("app.js")

    assert "NF-e" in app
    assert "NFC-e" in app
    assert "NFS-e" in app
    assert "CT-e" not in app
    assert "MDF-e" not in app


def test_accessibility_guards_remain_present() -> None:
    html = read("index.html")
    css = read("styles.css")

    assert 'class="skip-link"' in html
    assert 'aria-live="polite"' in html
    assert "prefers-reduced-motion" in css
    assert ":focus-visible" in css
