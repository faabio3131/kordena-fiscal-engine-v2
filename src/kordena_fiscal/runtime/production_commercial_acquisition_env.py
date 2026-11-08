"""Lightweight production commercial-acquisition security resolver via env var.

Mirrors production_cakto_webhook_env.py's pattern: a deployment-owned HMAC
secret is supplied out of band via a single base64-encoded environment
variable, never committed to git, never derived or guessed. This is the
production-environment counterpart to the development (development_commercial_
ingress.py) and staging (staging_commercial_ingress.py, GSM-backed) builders
for `commercial_acquisition_security` -- production does not use GSM, so this
mirrors the simpler, already-proven env-var pattern instead of the GSM scheme.

Fail-closed: absent configuration returns None, and the public commercial
offer continues to withhold `purchase_enabled`/`checkout_url` (the first-party
offer must not advertise a purchase without the signed acquisition route),
exactly like the Cakto webhook secret resolver.
"""

from __future__ import annotations

import base64
import binascii
import os
from collections.abc import Mapping

from ..security.s2s import InMemoryWebhookKeyRing, WebhookSecurity
from .config import RuntimeConfigurationError

_ENV_VAR = "NFCORE_PRODUCTION_COMMERCIAL_ACQUISITION_SECRET_BASE64"
_KEY_ID = "production-commercial-acquisition-key"


def production_commercial_acquisition_security_from_env(
    environ: Mapping[str, str] | None = None,
) -> WebhookSecurity | None:
    """Resolve the production commercial-acquisition signing authority from env.

    Absent configuration returns None (the signed acquisition route, and the
    public offer's purchase_enabled/checkout_url it gates, stay disabled). A
    configured value must be valid base64 decoding to at least 32 bytes; any
    malformed or too-short value raises rather than silently disabling or
    guessing.
    """
    source = os.environ if environ is None else environ
    key_string = source.get(_ENV_VAR, "")
    if not key_string:
        return None
    try:
        secret_bytes = base64.b64decode(key_string, validate=True)
    except (ValueError, binascii.Error):
        raise RuntimeConfigurationError(
            "production commercial acquisition env secret has invalid base64 encoding"
        ) from None
    if len(secret_bytes) < 32:
        raise RuntimeConfigurationError(
            "production commercial acquisition env secret is too short (min 32 bytes)"
        )
    return WebhookSecurity(
        key_resolver=InMemoryWebhookKeyRing(
            active_key_id=_KEY_ID,
            keys={_KEY_ID: secret_bytes},
        ),
        signing_key_id=_KEY_ID,
    )
