"""Additive PostgreSQL metadata only: no raw payload or secret material."""

COMMAND_COMMERCIAL_VERSION = 15
COMMAND_COMMERCIAL_NAME = "command_commercial_ingress"
COMMAND_COMMERCIAL_SCHEMA = (
    """CREATE TABLE fm_command_bindings (
        key_id TEXT PRIMARY KEY, binding_json TEXT NOT NULL, revision INTEGER NOT NULL
    )""",
    """CREATE TABLE fm_command_binding_audit (
        key_id TEXT NOT NULL, revision INTEGER NOT NULL, actor_id TEXT NOT NULL,
        binding_json TEXT NOT NULL, changed_at TEXT NOT NULL,
        PRIMARY KEY (key_id, revision)
    )""",
    """CREATE TABLE fm_command_commercial_inbox (
        product_id TEXT NOT NULL, environment TEXT NOT NULL, event_id TEXT NOT NULL,
        binding_id TEXT NOT NULL, fingerprint TEXT NOT NULL,
        purchase_id TEXT NOT NULL, received_at TEXT NOT NULL,
        processed_at TEXT,
        PRIMARY KEY (product_id, environment, event_id)
    )""",
    """CREATE TABLE fm_command_commercial_correlations (
        product_id TEXT NOT NULL, environment TEXT NOT NULL,
        command_subscription_id TEXT NOT NULL, command_customer_id TEXT NOT NULL,
        acquisition_id TEXT NOT NULL, opening_invoice_id TEXT NOT NULL,
        purchase_id TEXT NOT NULL,
        PRIMARY KEY (product_id, environment, command_subscription_id),
        UNIQUE (product_id, environment, acquisition_id), UNIQUE (purchase_id)
    )""",
)
