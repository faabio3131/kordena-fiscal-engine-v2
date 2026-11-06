"""Shared fiscal transport controls, independent of document layout."""
from __future__ import annotations

import os
import ssl
import tempfile
from email.message import Message
from pathlib import Path
from typing import Any
from urllib.request import HTTPRedirectHandler, Request

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import pkcs12

from kordena_fiscal.domain import FiscalValidationError
from kordena_fiscal.vault import EphemeralCertificateMaterial


def build_fiscal_tls_context(material: EphemeralCertificateMaterial) -> ssl.SSLContext:
    """Materialize mTLS keypair only inside a private temporary directory."""
    key, cert, chain = pkcs12.load_key_and_certificates(
        material.pkcs12_bytes, material.password
    )
    if key is None or cert is None:
        raise FiscalValidationError("Invalid or incomplete fiscal A1")
    context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    with tempfile.TemporaryDirectory(prefix="nfcore-mtls-") as directory:
        key_file = Path(directory) / "key.pem"
        cert_file = Path(directory) / "cert.pem"
        key_file.write_bytes(key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ))
        cert_file.write_bytes(cert.public_bytes(serialization.Encoding.PEM) + b"".join(
            item.public_bytes(serialization.Encoding.PEM) for item in (chain or [])
        ))
        os.chmod(key_file, 0o600)
        os.chmod(cert_file, 0o600)
        context.load_cert_chain(str(cert_file), str(key_file))
    return context


class RejectFiscalRedirects(HTTPRedirectHandler):
    """Never forward an mTLS fiscal request to a redirected destination."""

    def redirect_request(
        self, req: Request, fp: Any, code: int, msg: str,
        headers: Message, newurl: str,
    ) -> None:
        return None
