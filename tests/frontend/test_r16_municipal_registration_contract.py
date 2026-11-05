"""Issuer IM field flows through the one canonical Portal contract."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_issuer_form_exposes_municipal_registration() -> None:
    script = (ROOT / "portal" / "app.js").read_text(encoding="utf-8")
    assert '["municipal_registration", "Inscrição municipal (IM, se aplicável)", ""]' in script
    assert "municipal_registration: fields.municipal_registration.value.trim()" in script


def test_canonical_server_persists_municipal_registration() -> None:
    code = (
        ROOT / "src/kordena_fiscal/web/portal_runtime.py"
    ).read_text(encoding="utf-8")
    assert 'optional = {"municipal_registration"}' in code
    assert 'MunicipalRegistration(payload["municipal_registration"])' in code
    assert "existing.municipal_registration != profile.municipal_registration" in code
