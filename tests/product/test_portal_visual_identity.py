from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PORTAL = ROOT / "portal"


def read(name: str) -> str:
    return (PORTAL / name).read_text(encoding="utf-8")


def test_v1_commercial_identity_is_applied() -> None:
    html = read("index.html")
    css = read("styles.css")

    assert "FM NFCORE V1.0" in html
    assert "Infraestrutura fiscal. Sob controle." in html
    assert "FM NFCORE · Commercial Launch Edition · V1.0" in html
    assert "--brand-primary: #2563ff" in css
    assert "--brand-cyan: #00e5ff" in css
    assert html.count('src="assets/fm-nfcore-mark.svg"') >= 3
    assert 'class="product-banner-mark"' in html
    assert 'alt="FM NFCORE"' in html
    assert 'href="assets/favicon.svg"' in html


def test_brand_color_is_not_operational_success_color() -> None:
    css = read("styles.css")

    assert "--brand-primary: #2563ff" in css
    assert "--success: #22c55e" in css
    assert "background: var(--success)" in css
    assert "button.primary" in css
    assert "background: linear-gradient(135deg, #2563ff, #174bd6)" in css


def test_standalone_surface_does_not_expose_internal_product_names() -> None:
    app = read("app.js")

    for internal_name in ("Kordena", "Iron Fit", "Vendedor IA", "CampaIA"):
        assert internal_name not in app


def test_commercial_surface_uses_nfcore_name_only() -> None:
    html = read("index.html")
    app = read("app.js")

    assert "FM Fiscal V1.0" not in html
    assert "FM Fiscal V1.0" not in app
    assert "FM NFCORE" in html
    assert "FM NFCORE" in app


def test_commercial_surface_is_real_api_connected_without_internal_release_language() -> None:
    html = read("index.html")
    app = read("app.js")

    assert "Release Candidate interno" not in html
    assert "DEMO INTERNA" not in app
    assert "Dados operacionais carregados da API autenticada" in html
    assert "Dados exibidos nesta superfície são sintéticos" not in html
    assert "/v1/portal/bootstrap" in app


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


def test_mobile_navigation_is_compact_and_horizontally_scrollable() -> None:
    css = read("styles.css")

    assert "@media (max-width: 760px)" in css
    assert "overflow-x: auto" in css
    assert ".nav-group-label { display: none; }" in css
    assert ".product-banner-mark { width: 62px; height: 62px; }" in css
