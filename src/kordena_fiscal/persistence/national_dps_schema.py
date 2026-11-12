"""Additive migration 22: National DPS legal-issuer numbering authority.

This is a *new* sequence store, not a migration of fm_fiscal_sequences.
The table intentionally omits tenant/unit from its natural uniqueness key:
a legal CNPJ cannot reuse a DPS number because it changed tenant or unit.
Authorization remains bound to the session-scoped issuance and archive.
"""

NATIONAL_DPS_SEQUENCE_VERSION = 22
NATIONAL_DPS_SEQUENCE_NAME = "national_dps_issuer_numbering_v1"
NATIONAL_DPS_SEQUENCE_SCHEMA = (
    """
    CREATE TABLE fm_nfse_dps_sequences (
        host_namespace TEXT NOT NULL,
        environment TEXT NOT NULL,
        issuer_cnpj TEXT NOT NULL,
        series INTEGER NOT NULL,
        first_number INTEGER NOT NULL,
        max_number INTEGER,
        last_reserved INTEGER NOT NULL,
        PRIMARY KEY (host_namespace, environment, issuer_cnpj, series)
    )
    """,
)
