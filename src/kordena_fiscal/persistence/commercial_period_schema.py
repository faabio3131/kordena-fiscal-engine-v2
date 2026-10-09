"""Additive invoice/contract metadata; no provider payload, credentials or PII."""
COMMERCIAL_PERIOD_VERSION = 16
COMMERCIAL_PERIOD_NAME = "commercial_contracted_periods"
COMMERCIAL_PERIOD_SCHEMA = (
    "ALTER TABLE fm_commercial_event_receipts ADD COLUMN payment_reference TEXT",
    """CREATE TABLE fm_commercial_contracts (
        purchase_id TEXT PRIMARY KEY REFERENCES fm_commercial_purchases(purchase_id),
        contract_json TEXT NOT NULL
    )""",
)
