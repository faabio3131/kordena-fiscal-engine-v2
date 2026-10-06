"""Additive scope metadata on the existing lifecycle; never infer legacy ownership."""

FISCAL_SCOPE_VERSION = 13
FISCAL_SCOPE_NAME = "p02_t02_scoped_fiscal_projections"
FISCAL_SCOPE_SCHEMA = (
    "ALTER TABLE fm_fiscal_lifecycle ADD COLUMN host_namespace TEXT",
    "ALTER TABLE fm_fiscal_lifecycle ADD COLUMN tenant_id TEXT",
    "ALTER TABLE fm_fiscal_lifecycle ADD COLUMN unit_id TEXT",
    "ALTER TABLE fm_fiscal_lifecycle ADD COLUMN environment TEXT",
    """CREATE INDEX fm_fiscal_lifecycle_scope_idx ON fm_fiscal_lifecycle
       (host_namespace, tenant_id, unit_id, environment, updated_at, document_id)""",
    """CREATE INDEX fm_fiscal_outbox_scope_idx ON fm_fiscal_outbox
       (host_namespace, tenant_id, unit_id, environment, created_at, entry_id)""",
    """CREATE INDEX fm_fiscal_archive_scope_idx ON fm_fiscal_archive
       (host_namespace, tenant_id, unit_id, environment, archived_at, entry_id)""",
)
