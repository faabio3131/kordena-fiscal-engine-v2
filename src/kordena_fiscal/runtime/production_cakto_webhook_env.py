"""Lightweight production Cakto webhook secret resolver via environment variable.

Mirrors the EncryptedA1Vault.from_environ() pattern already used in production
for fiscal certificate material: a deployment-owned secret is supplied out of
band via an env var (base64-encoded), never committed to git, never derived
or guessed. This is an alternative to the full GSM-backed resolver in
production_cakto_ingress.py for deployments that have not yet bootstrapped a
dedicated Google Cloud Secret Manager project. Fail-closed: absent config
returns None and leaves the /webhooks/cakto route disabled, exactly like the
GSM resolver.
"""

from __future__ import annotations

import base64
import binascii
import os
from collections.abc import Mapping

from .config import RuntimeConfigurationError

_ENV_VAR = "NFCORE_PRODUCTION_CAKTO_WEBHOOK_SECRET_BASE64"


def production_cakto_webhook_secret_from_env(
    environ: Mapping[str, str] | None = None,
) -> bytes | None:
    """Resolve the production Cakto webhook signature secret from env, fail-closed.

    Absent configuration returns None (route stays disabled). A configured
    value must be valid base64 decoding to at least 32 bytes; any malformed
    or too-short value raises rather than silently disabling or guessing.
    """
    source = os.environ if environ is None else environ
    key_string = source.get(_ENV_VAR, "")
    if not key_string:
        return None
    try:
        secret_bytes = base64.b64decode(key_string, validate=True)
    except (ValueError, binascii.Error):
        raise RuntimeConfigurationError(
            "production Cakto webhook env secret has invalid base64 encoding"
        ) from None
    if len(secret_bytes) < 32:
        raise RuntimeConfigurationError(
            "production Cakto webhook env secret is too short (min 32 bytes)"
        )
    return secret_bytes
