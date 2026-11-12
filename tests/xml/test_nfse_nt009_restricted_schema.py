"""Pinned offline NT009 Release 1 homologation schemas (mirrored source)."""
from __future__ import annotations

import hashlib
from importlib.resources import files

import pytest

from kordena_fiscal.domain import FiscalValidationError
from kordena_fiscal.xml.nfse_nacional_schema import (
    _NT009_HASHES,
    NT009_RESTRICTED_PROFILE,
    national_dps_validator,
    national_event_validator,
    national_restricted_validator,
)
from kordena_fiscal.xml.schema import SchemaIntegrityError, SchemaResource


@pytest.mark.parametrize("root", [
    "DPS_v1.01.xsd",
    "pedRegEvento_v1.01.xsd",
    "evento_v1.01.xsd",
    "NFSe_v1.01.xsd",
])
def test_nt009_compiles_pinned_schema_set_offline(root: str) -> None:
    validator = national_restricted_validator(root)
    assert validator is national_restricted_validator(root)


def test_restricted_dps_is_separate_from_production_february_xsd() -> None:
    prod = national_dps_validator("1.01")
    restricted = national_dps_validator(
        "1.01", profile=NT009_RESTRICTED_PROFILE,
    )
    assert restricted is national_restricted_validator("DPS_v1.01.xsd")
    assert restricted is not prod
    assert national_event_validator() is national_restricted_validator(
        "pedRegEvento_v1.01.xsd"
    )


def test_restricted_schema_rejects_missing_unknown_profile() -> None:
    with pytest.raises(FiscalValidationError, match="Unknown National DPS"):
        national_dps_validator("1.01", profile="unreviewed-download")
    with pytest.raises(FiscalValidationError, match="only permits"):
        national_dps_validator("1.00", profile=NT009_RESTRICTED_PROFILE)
    with pytest.raises(FiscalValidationError, match="Unsupported National NT009"):
        national_restricted_validator("unexpected.xsd")


def test_nt009_all_sources_match_independent_immutable_sha256() -> None:
    directory = files("kordena_fiscal.xml").joinpath(
        "official", "NFSE_NACIONAL_1.01_NT009_20261020",
    )
    assert len(_NT009_HASHES) == 10
    for name, digest in _NT009_HASHES.items():
        raw = directory.joinpath(name).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == digest
        assert SchemaResource(name, raw, digest).content == raw
        with pytest.raises(SchemaIntegrityError):
            SchemaResource(name, raw + b"\x20", digest)


def test_nt009_restricted_schema_has_mandatory_fin_nfse() -> None:
    raw = files("kordena_fiscal.xml").joinpath(
        "official", "NFSE_NACIONAL_1.01_NT009_20261020",
        "tiposComplexos_v1.01.xsd",
    ).read_bytes()
    assert b'name="finNFSe"' in raw
    assert b'name="vAjusteBC"' in raw
    assert b'name="vDedRed"' not in raw
