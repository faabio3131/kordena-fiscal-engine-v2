"""Fail-closed Bling OAuth composition using deployment-owned secret files.

One canonical PostgreSQL database holds encrypted token envelopes; never create
a second secret store or infer any tenant from environment credentials.
"""
from __future__ import annotations

import os
import stat
from collections.abc import Mapping
from pathlib import Path

from kordena_fiscal.connectors.bling_api import verify_company
from kordena_fiscal.connectors.bling_oauth import BlingOAuthClient
from kordena_fiscal.persistence.bling_installations import (
    BlingInstallationRepository,
    Database,
)

from .bling_oauth_service import BlingOAuthService, BlingTokenCipher
from .config import RuntimeConfigurationError


def _confidential_file(source: Mapping[str, str], key: str) -> str:
    path = source.get("NFCORE_BLING_" + key + "_FILE", "").strip()
    if not path:
        raise RuntimeConfigurationError("Bling secret file is not configured")
    p = Path(path)
    try:
        details = p.lstat()
        if p.is_symlink() or not stat.S_ISREG(details.st_mode):
            raise ValueError("not a regular secret file")
        # Only the intended container service account may read each file.
        if details.st_mode & 0o077:
            raise ValueError("secret file permissions are too broad")
        with p.open("rb") as reader:
            raw = reader.read(8193)
        if len(raw) > 8192 or not raw:
            raise ValueError("invalid confidential material")
        value = raw.decode("ascii").strip()
        if not value or any(ord(c) < 33 or ord(c) > 126 for c in value):
            raise ValueError("invalid confidential material")
        return value
    except (OSError, ValueError, UnicodeDecodeError):
        raise RuntimeConfigurationError("Bling secret is unavailable") from None


def build_bling_oauth_service(
    database: Database,
    source: Mapping[str, str] | None = None,
) -> tuple[BlingInstallationRepository, BlingOAuthService]:
    source = os.environ if source is None else source
    if source.get("NFCORE_BLING_INSTALLATIONS_ENABLED") != "true":
        raise RuntimeConfigurationError("Bling multi-installation mode is disabled")
    if source.get("NFCORE_SECRET_BACKEND") != "external":
        raise RuntimeConfigurationError("Bling requires production-safe secret backend")
    client_id = source.get("NFCORE_BLING_CLIENT_ID", "").strip()
    scopes = frozenset(source.get("NFCORE_BLING_APPROVED_SCOPES", "").split())
    if not client_id or not scopes or any(
        len(value) > 128 or not value.isascii() for value in scopes
    ):
        raise RuntimeConfigurationError("Bling approved OAuth app/scopes unavailable")
    cipher = BlingTokenCipher.from_base64(
        _confidential_file(source, "TOKEN_MASTER_KEY"),
    )
    client = BlingOAuthClient(
        client_id=client_id,
        client_secret=_confidential_file(source, "CLIENT_SECRET"),
    )
    installations = BlingInstallationRepository(database)
    oauth = BlingOAuthService(
        database,
        installations,
        cipher,
        client,
        verify_company,
        required_scopes=scopes,
        webhook_secret=_confidential_file(source, "WEBHOOK_SECRET"),
    )
    return installations, oauth
