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



# Offline working copy of the 20/10/2026 restricted-production NT009 Release 1.
# Source mirrors are pinned by commit+blob SHA in the attached engineering
# dossier; official gov.br ZIP byte-for-byte provenance remains an external
# comparison gate. Never relabel this as an official municipality homologation.
NT009_RESTRICTED_PROFILE = "nt009-prodrest-20261020"
_NT009_MIRRORED_SOURCE = (
    "https://github.com/Gomes343/PyNFSeNacional/tree/"
    "e48919df29cbc8dc5f635d212ca10fc54b59cf85/tests/xsd/20261020"
)
_NT009_HASHES = {
    "CNC_v1.00.xsd": "26961f705970ccb1dede1b6bb0ab544ca1d089137c22e93371d789c1e15ef0c4",
    "DPS_v1.01.xsd": "fe45e5250a48e519aba89fc6a472863b8e602ed957778fb64692804933a00d0c",
    "NFSe_v1.01.xsd": "1dd8f543060a4ba6f355693f1fa5d79a269acae7c3dfe42d621f62911cfebac0",
    "evento_v1.01.xsd": "dd14062174d439a67a11266d82e822cb9021db1595a41bd876a16560a38f6aec",
    "pedRegEvento_v1.01.xsd": "186c83f33752a195845300af61ffbe7136547f84cab032b35238c78f9d78f7c6",
    "tiposCnc_v1.00.xsd": "c1cc33f1007251075b1fff7766bf881bba6a8ad7f1f36d149e54ae98090c77f8",
    "tiposComplexos_v1.01.xsd": "4f66f7c15bd3b05b3a16cbe5fa671b90c10e4c9c74276038730be1c8c794b721",
    "tiposEventos_v1.01.xsd": "6c9ae744b1cb886607c1138c32eeb76cd410b856ce7301197b95d48d63f7b40b",
    "tiposSimples_v1.01.xsd": "562e326724f85cd7c41176d35e67c542376784d4c950ec1719704d480a8af226",
    "xmldsig-core-schema.xsd": "8c9792a056aedcadfc95bf16f2d7448a35da40df71533e20aea37d0329980c48",
}


@lru_cache(maxsize=4)
def national_restricted_validator(root_schema: str) -> XmlSchemaValidator:
    approved_roots = frozenset({
        "DPS_v1.01.xsd",
        "pedRegEvento_v1.01.xsd",
        "evento_v1.01.xsd",
        "NFSe_v1.01.xsd",
    })
    if root_schema not in approved_roots:
        raise FiscalValidationError("Unsupported National NT009 schema root")
    directory = files("kordena_fiscal.xml").joinpath(
        "official", "NFSE_NACIONAL_1.01_NT009_20261020",
    )
    return XmlSchemaValidator(SchemaSet(
        version=NT009_RESTRICTED_PROFILE,
        root_schema=root_schema,
        resources=tuple(
            SchemaResource(name, directory.joinpath(name).read_bytes(), sha)
            for name, sha in _NT009_HASHES.items()
        ),
        source_uri=_NT009_MIRRORED_SOURCE,
    ))


def national_event_validator() -> XmlSchemaValidator:
    """Signed national event-request schema, pinned to restricted NT009 source."""
    return national_restricted_validator("pedRegEvento_v1.01.xsd")


@lru_cache(maxsize=4)
def national_dps_validator(
    version: str, *, profile: str = "production",
) -> XmlSchemaValidator:
    if profile == NT009_RESTRICTED_PROFILE:
        if version != "1.01":
            raise FiscalValidationError("NT009 restricted profile only permits DPS v1.01")
        return national_restricted_validator("DPS_v1.01.xsd")
    if profile != "production":
        raise FiscalValidationError("Unknown National DPS schema profile")
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
