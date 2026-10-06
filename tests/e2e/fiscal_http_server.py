"""Loopback-only internal browser fixture; never a deployable fiscal/provider runtime."""

from __future__ import annotations

import importlib.util
import ipaddress
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

import uvicorn
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from fastapi import HTTPException
from fastapi.staticfiles import StaticFiles

from kordena_fiscal.application.service import FiscalApplicationService
from kordena_fiscal.lifecycle import IdempotencyKey
from kordena_fiscal.persistence import SqliteFiscalDatabase
from kordena_fiscal.runtime.fiscal_runtime import (
    CanonicalFiscalOperationPath,
    CanonicalPortalOperationExecutor,
)
from kordena_fiscal.web import create_app
from kordena_fiscal.web.portal_runtime import DurableHumanPortalExecutor

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "p02_fixture", ROOT / "tests/support/p02_fiscal_fixture.py"
)
assert spec and spec.loader
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)


def build_app(database):
    fixture.seed(database)
    service = FiscalApplicationService(database)

    def reserve_internal(scope, payload, idempotency_key):
        """Persist a reservation, not an emission; inject a post-commit fault once."""
        key = IdempotencyKey(fixture.digest(idempotency_key))
        reservation = service.reserve_issuance(
            scope=scope,
            key=key,
            request_fingerprint=fixture.digest(json.dumps(dict(payload), sort_keys=True)),
            document_id="HTTP-RESERVATION-" + key.value[:12],
            created_at=datetime.now(UTC),
        )
        if not reservation.reservation.replay:
            raise HTTPException(
                503,
                detail={
                    "code": "SYNTHETIC_POST_COMMIT_FAILURE",
                    "message": (
                        "Synthetic response loss after durable reservation; retry the same request"
                    ),
                },
            )
        return {
            "status": "reserved_internal_replay",
            "document_id": reservation.lifecycle.document_id,
        }

    path = CanonicalFiscalOperationPath(service, handlers={"issueFiscalDocument": reserve_internal})
    portal = DurableHumanPortalExecutor(
        database,
        operation_executor=CanonicalPortalOperationExecutor(
            unit_of_work_factory=database,
            path=path,
        ),
    )
    app = create_app(human_identity=fixture.identity(), portal_executor=portal)
    app.mount("/", StaticFiles(directory=ROOT / "portal", html=True), name="test-portal")
    return app


if __name__ == "__main__":
    with TemporaryDirectory(prefix="nfcore-p02-e2e-") as folder:
        directory = Path(folder)
        database = SqliteFiscalDatabase(directory / "internal.sqlite3")
        database.initialize()
        # Test TLS only: generated locally, never uploaded or used for staging/production.
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "synthetic-loopback-test")])
        now = datetime.now(UTC)
        certificate = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(subject)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(minutes=1))
            .not_valid_after(now + timedelta(hours=1))
            .add_extension(
                x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]),
                critical=False,
            )
            .sign(key, hashes.SHA256())
        )
        cert_path = directory / "test.crt"
        key_path = directory / "test.key"
        cert_path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
        key_path.write_bytes(
            key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            )
        )
        uvicorn.run(
            build_app(database),
            host="127.0.0.1",
            port=4174,
            ssl_certfile=str(cert_path),
            ssl_keyfile=str(key_path),
            log_level="warning",
        )
