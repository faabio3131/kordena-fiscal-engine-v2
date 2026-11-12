"""Auditable fail-closed normalization of the pinned National DPS 1.01 serie XSD."""

from __future__ import annotations

import hashlib
from importlib.resources import files

import pytest

from kordena_fiscal.xml.nfse_nacional_schema import (
    _HASHES,
    _V101_BAD_SERIE_PATTERN,
    _V101_CORRECTED_SERIE_PATTERN,
    _pinned_national_schema_resource,
    national_dps_validator,
)
from kordena_fiscal.xml.schema import SchemaIntegrityError

_RESOURCE_NAME = "tiposSimples_v1.01.xsd"


def _official_bytes() -> bytes:
    return files("kordena_fiscal.xml").joinpath(
        "official", "NFSE_NACIONAL_1.01", _RESOURCE_NAME
    ).read_bytes()


def test_official_xsd_source_is_untouched_and_compatibility_is_in_memory() -> None:
    raw = _official_bytes()
    original_sha256 = _HASHES["1.01"][_RESOURCE_NAME]
    assert hashlib.sha256(raw).hexdigest() == original_sha256
    assert raw.count(_V101_BAD_SERIE_PATTERN) == 1
    patched = _pinned_national_schema_resource(
        _RESOURCE_NAME, raw, original_sha256, version="1.01",
    )
    assert patched.content.count(_V101_BAD_SERIE_PATTERN) == 0
    assert patched.content.count(_V101_CORRECTED_SERIE_PATTERN) == 1
    assert raw.count(_V101_BAD_SERIE_PATTERN) == 1  # no write to original XSD
    assert patched.sha256 != original_sha256
    # The compiled digest must be attributable to the normalized variant,
    # never the falsely claimed unmodified government package.
    validator = national_dps_validator("1.01")
    assert validator is national_dps_validator("1.01")


def test_modified_official_schema_is_rejected_before_compatibility() -> None:
    raw = _official_bytes()
    with pytest.raises(SchemaIntegrityError, match="digest mismatch"):
        _pinned_national_schema_resource(
            _RESOURCE_NAME, raw + b" ", _HASHES["1.01"][_RESOURCE_NAME],
            version="1.01",
        )


def test_unknown_xsd_series_regex_is_not_silently_normalized() -> None:
    altered = _official_bytes().replace(
        _V101_BAD_SERIE_PATTERN,
        b'<xs:pattern value="[0-9]{1,5}"/>',
    )
    with pytest.raises(SchemaIntegrityError, match="reviewed source"):
        _pinned_national_schema_resource(
            _RESOURCE_NAME, altered, hashlib.sha256(altered).hexdigest(),
            version="1.01",
        )
