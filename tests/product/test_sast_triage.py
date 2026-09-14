from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_commercial_profile_query_only_interpolates_static_column_constant() -> None:
    source = _read("src/kordena_fiscal/persistence/sqlite_commercial.py")
    assert '_PRODUCT_SELECT = """' in source
    assert "SELECT {_PRODUCT_SELECT}" in source
    assert "WHERE tenant_id = ? AND unit_id = ? AND environment = ?" in source
    assert "AND product_id = ? AND effective_from <= ?" in source
    assert "(tenant, unit, environment.value, product, instant_iso, instant_iso)" in source


def test_control_plane_profile_queries_bind_all_runtime_values() -> None:
    source = _read("src/kordena_fiscal/persistence/sqlite_control_plane.py")
    assert '_PROFILE_SELECT = """' in source
    assert source.count("SELECT {_PROFILE_SELECT}") >= 2
    assert "WHERE profile_id = ? AND version = ?" in source
    assert "WHERE host_namespace = ? AND tenant_id = ? AND unit_id = ?" in source
    assert "AND environment = ? AND effective_from <= ?" in source


def test_sast_static_select_constants_contain_only_identifier_material() -> None:
    commercial = _read("src/kordena_fiscal/persistence/sqlite_commercial.py")
    control_plane = _read("src/kordena_fiscal/persistence/sqlite_control_plane.py")
    for source, name in (
        (commercial, "_PRODUCT_SELECT"),
        (control_plane, "_PROFILE_SELECT"),
    ):
        value = source.split(f'{name} = """', maxsplit=1)[1].split('"""', maxsplit=1)[0]
        compact = value.replace("_", "").replace(",", "").replace("\n", "").replace(" ", "")
        assert compact.isalnum()
        assert "{" not in value
        assert "}" not in value
        assert ";" not in value
        assert "?" not in value
