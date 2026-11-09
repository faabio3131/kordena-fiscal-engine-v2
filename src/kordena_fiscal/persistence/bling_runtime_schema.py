"""Additive per-installation Bling return-code and fiscal-policy metadata (v21).

This table is a configuration projection only. Tenant authority stays with
fm_fiscal_bindings and fm_bling_installations; no secret/plaintext/token columns.
"""

BLING_RUNTIME_VERSION = 21
BLING_RUNTIME_NAME = "bling_per_installation_operability"
BLING_RUNTIME_SCHEMA = (
    """CREATE TABLE fm_bling_installation_runtime (
        installation_id TEXT PRIMARY KEY
            REFERENCES fm_bling_installations(installation_id),
        authorized_status_id INTEGER,
        rejected_status_id INTEGER,
        fiscal_policy_sha256 TEXT,
        revision INTEGER NOT NULL CHECK(revision > 0),
        updated_at TEXT NOT NULL,
        CHECK(
            (authorized_status_id IS NULL AND rejected_status_id IS NULL)
            OR (authorized_status_id > 0 AND rejected_status_id > 0
                AND authorized_status_id <> rejected_status_id)
        )
    )""",
)
