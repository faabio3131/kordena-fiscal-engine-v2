"""Additive Bling worker policy: one active OAuth binding per fiscal partition.

Migration 21 intentionally never drops/rebuilds historical tables. Multiple
connected installations sharing an outbox partition would allow wrong-company
claims; the partial unique index makes such unsafe activation impossible.
"""

BLING_WORKER_POLICY_VERSION = 21
BLING_WORKER_POLICY_NAME = "bling_worker_partition_policy"
BLING_WORKER_POLICY_SCHEMA = (
    """ALTER TABLE fm_bling_installations
       ADD COLUMN authorized_status_id INTEGER""",
    """ALTER TABLE fm_bling_installations
       ADD COLUMN rejected_status_id INTEGER""",
    """CREATE UNIQUE INDEX fm_bling_active_partition_unique
       ON fm_bling_installations(tenant_id, unit_id, environment)
       WHERE state = 'connected'""",
)
