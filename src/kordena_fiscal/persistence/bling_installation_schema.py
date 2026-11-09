"""Additive Bling installation registry and encrypted OAuth envelope (migration 20).

The canonical fiscal binding remains the only tenant/unit authority.
No credentials are stored in plaintext in these tables.
"""

BLING_INSTALLATION_VERSION = 20
BLING_INSTALLATION_NAME = "bling_installations_and_credentials"
BLING_INSTALLATION_SCHEMA = (
    """CREATE TABLE fm_bling_installations (
        installation_id TEXT PRIMARY KEY,
        company_id TEXT NOT NULL,
        external_tenant_id TEXT NOT NULL,
        external_unit_id TEXT NOT NULL,
        tenant_id TEXT NOT NULL,
        unit_id TEXT NOT NULL,
        environment TEXT NOT NULL CHECK(environment IN ('homologation', 'production')),
        state TEXT NOT NULL CHECK(
            state IN ('not_configured', 'connected', 'needs_reauth', 'paused', 'error')
        ),
        revision INTEGER NOT NULL CHECK(revision > 0),
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        UNIQUE(company_id, external_tenant_id, external_unit_id, environment)
    )""",
    """CREATE INDEX fm_bling_installations_scope_idx
       ON fm_bling_installations(tenant_id, unit_id, environment)""",
    """CREATE TABLE fm_bling_oauth_flows (
        state_sha256 TEXT PRIMARY KEY,
        installation_id TEXT NOT NULL REFERENCES fm_bling_installations(installation_id),
        actor_id TEXT NOT NULL,
        session_id TEXT NOT NULL,
        verifier_ciphertext TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        consumed INTEGER NOT NULL CHECK(consumed IN (0, 1))
    )""",
    """CREATE INDEX fm_bling_oauth_flows_installation_idx
       ON fm_bling_oauth_flows(installation_id, expires_at)""",
    """CREATE TABLE fm_bling_credentials (
        installation_id TEXT PRIMARY KEY REFERENCES fm_bling_installations(installation_id),
        access_ciphertext TEXT NOT NULL,
        refresh_ciphertext TEXT NOT NULL,
        webhook_secret_ciphertext TEXT,
        access_expires_at TEXT NOT NULL,
        refresh_expires_at TEXT,
        scopes_json TEXT NOT NULL,
        token_revision INTEGER NOT NULL CHECK(token_revision > 0),
        updated_at TEXT NOT NULL
    )""",
)
