"""Actual official XSD bytes, compiled offline; no official emission claims."""
import hashlib
from importlib.resources import files

import pytest

import kordena_fiscal.xml.official_nfe_schema as official
from kordena_fiscal.xml.schema import SchemaIntegrityError, XmlSchemaValidationError


def test_official_package_compiles_offline_and_preserves_provenance():
    schema = official.load_official_nfe_schema()
    assert schema.version == "PL_010g_v1.03"
    assert schema.root_schema == "nfe_v4.00.xsd"
    assert len(schema.resources) == 5
    for resource in schema.resources:
        assert hashlib.sha256(resource.content).hexdigest() == resource.sha256
    assert schema.source_uri.startswith("https://www.nfe.fazenda.gov.br/")
    validator = official.OfficialNfeEnvelopeValidator()
    with pytest.raises(XmlSchemaValidationError):
        validator(b"<invalid/>")


def test_changed_manifest_is_denied_before_schema_compilation(tmp_path, monkeypatch):
    directory = tmp_path / "official" / "PL_010g_v1.03"
    directory.mkdir(parents=True)
    (directory / "manifest.json").write_bytes(b"{}")
    monkeypatch.setattr(official, "files", lambda _package: tmp_path)
    with pytest.raises(SchemaIntegrityError, match="manifest digest"):
        official.load_official_nfe_schema()


def test_modified_xsd_is_denied_even_with_original_manifest(tmp_path, monkeypatch):
    source = files("kordena_fiscal.xml").joinpath("official", "PL_010g_v1.03")
    directory = tmp_path / "official" / "PL_010g_v1.03"
    directory.mkdir(parents=True)
    schema = official.load_official_nfe_schema()
    for name in ["manifest.json"] + [entry.name for entry in schema.resources]:
        (directory / name).write_bytes(source.joinpath(name).read_bytes())
    (directory / "nfe_v4.00.xsd").write_bytes(b"<forged/>")
    monkeypatch.setattr(official, "files", lambda _package: tmp_path)
    with pytest.raises(SchemaIntegrityError, match="digest mismatch"):
        official.load_official_nfe_schema()
