"""Additive metadata-only external binding migration; no material column."""

SECRET_BINDING_VERSION = 17
SECRET_BINDING_NAME = "external_secret_bindings"
SECRET_BINDING_SCHEMA = (
    """CREATE TABLE fm_secret_bindings (
        reference_id TEXT PRIMARY KEY, revision INTEGER NOT NULL,
        metadata_json TEXT NOT NULL
    )""",
)
