"""Additive control metadata; configuration remains in the existing canonical tables."""

CUSTOMER_CONFIGURATION_VERSION = 14
CUSTOMER_CONFIGURATION_NAME = "customer_configuration_commands_and_egress"
CUSTOMER_CONFIGURATION_SCHEMA = (
    """CREATE TABLE fm_configuration_revisions (
        tenant_id TEXT NOT NULL, unit_id TEXT NOT NULL, environment TEXT NOT NULL,
        target_type TEXT NOT NULL, target_key TEXT NOT NULL, version INTEGER NOT NULL,
        PRIMARY KEY (tenant_id, unit_id, environment, target_type, target_key)
    )""",
    """CREATE TABLE fm_configuration_commands (
        tenant_id TEXT NOT NULL, unit_id TEXT NOT NULL, environment TEXT NOT NULL,
        command_key TEXT NOT NULL, fingerprint TEXT NOT NULL, result_json TEXT,
        PRIMARY KEY (tenant_id, unit_id, environment, command_key)
    )""",
    (
        "ALTER TABLE fm_commercial_webhook_destinations "
        "ADD COLUMN approval_status TEXT NOT NULL DEFAULT 'pending'"
    ),
    "ALTER TABLE fm_commercial_webhook_destinations ADD COLUMN approved_version INTEGER",
    "ALTER TABLE fm_commercial_webhook_destinations ADD COLUMN approved_until TEXT",
    "ALTER TABLE fm_commercial_webhook_destinations ADD COLUMN approved_url_sha256 TEXT",
    (
        "ALTER TABLE fm_commercial_webhook_destinations "
        "ADD COLUMN requested_by TEXT NOT NULL DEFAULT ''"
    ),
    "ALTER TABLE fm_commercial_webhook_destinations ADD COLUMN approved_by TEXT",
)
