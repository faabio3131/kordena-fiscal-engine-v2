"""Hash-pinned National DPS schemas, loaded offline."""
from functools import lru_cache
from importlib.resources import files

from kordena_fiscal.domain import FiscalValidationError

from .schema import SchemaIntegrityError, SchemaResource, SchemaSet, XmlSchemaValidator

_SOURCE = (
    "https://www.gov.br/nfse/pt-br/biblioteca/documentacao-tecnica/documentacao-atual/"
    "nfse-esquemas_xsd-v1-01-20260209.zip"
)
_HASHES = {
    "1.00": {
        "DPS_v1.00.xsd": "a4d99ccff95b86378958692e68f8011333eee650956f7592f4b5b70799741dc6",
        "tiposComplexos_v1.00.xsd":
            "f26aa6110ca7e40fe9ee51c28ef4690e7d7a1c29436fac090f998523a0761d24",
        "tiposSimples_v1.00.xsd":
            "c709e5ee8e7bf6582e29f17fe49d4bbedb531361b5c3d4f7a725fc2f3bd463fd",
        "xmldsig-core-schema.xsd":
            "adbfc03b4d0b3ee8a18198383f81ec7b7857a5285f480717dfafd4696ce9f9be",
    },
    "1.01": {
        "DPS_v1.01.xsd": "8e1aab58d3850d654f119a0274e5d8f1826f39007d272d925fe5bf23fcd38ca3",
        "tiposComplexos_v1.01.xsd":
            "658f91cb16793cf814ae6c4d7a69ddda7820507ad2cbe70382bc979fedd2cecf",
        "tiposSimples_v1.01.xsd":
            "41df4fd084b80d86200e0edb1d7d8df4adbc7fb6d19b93f35014a9dcbb8a2fa9",
        "xmldsig-core-schema.xsd":
            "58dede7aaeb706b5c681302353567e6abd973f2110d3349187d62ca8f1b807d2",
    },
}


# The untouched official 2026-02-09 v1.01 archive embeds a malformed
# TSSerieDPS regular expression. XSD regexes are implicitly anchored: "^"
# and "$" are *literal characters*, so normal numeric series are rejected.
# A later National NFS-e restricted-production layout corrected this field
# to the bounded form below. We do NOT modify the SHA-pinned source asset.
# The exact, auditable normalization exists ONLY in memory, after verifying
# the original asset's official SHA-256; all other XSD rules remain intact.
# This compatibility profile is NOT a claim of homologation against the
# complete 2026-10-20 restricted-production NT009 XSD release.
_V101_BAD_SERIE_PATTERN = br'<xs:pattern value="^0{0,4}\d{1,5}$"/>'
_V101_CORRECTED_SERIE_PATTERN = (
    b'<xs:pattern value="[0-9]{1,4}|[0-8][0-9]{4}"/>'
)
_V101_COMPAT_SOURCE_SUFFIX = "#nfcore-verified-serie-compat-20261020"


def _pinned_national_schema_resource(
    name: str, content: bytes, digest: str, *, version: str,
) -> SchemaResource:
    # Integrity check precedes any conversion so altered/unknown downloads
    # cannot be laundered into a seemingly certified in-memory XSD.
    original = SchemaResource(name, content, digest)
    if version != "1.01" or name != "tiposSimples_v1.01.xsd":
        return original
    if original.content.count(_V101_BAD_SERIE_PATTERN) != 1:
        raise SchemaIntegrityError("Pinned v1.01 serie pattern is not the reviewed source")
    normalized = original.content.replace(
        _V101_BAD_SERIE_PATTERN, _V101_CORRECTED_SERIE_PATTERN,
    )
    return SchemaResource.from_bytes(name, normalized)


@lru_cache(maxsize=2)
def national_dps_validator(version: str) -> XmlSchemaValidator:
    if version not in _HASHES:
        raise FiscalValidationError("Unsupported National DPS schema version")
    directory = files("kordena_fiscal.xml").joinpath("official", f"NFSE_NACIONAL_{version}")
    return XmlSchemaValidator(SchemaSet(
        version=version,
        root_schema=f"DPS_v{version}.xsd",
        resources=tuple(
            _pinned_national_schema_resource(
                name, directory.joinpath(name).read_bytes(), digest, version=version,
            )
            for name, digest in _HASHES[version].items()
        ),
        source_uri=(
            _SOURCE + _V101_COMPAT_SOURCE_SUFFIX
            if version == "1.01" else _SOURCE
        ),
    ))
