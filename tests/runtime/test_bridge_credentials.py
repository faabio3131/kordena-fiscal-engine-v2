import hashlib
import json
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from kordena_fiscal.domain import FiscalEnvironment
from kordena_fiscal.runtime.bridge_credentials import load_bridge_credentials
from kordena_fiscal.runtime.config import RuntimeConfigurationError
from kordena_fiscal.security.s2s import WorkloadAuthenticationError, WorkloadAuthenticator


class BridgeCredentialsTest(unittest.TestCase):
    def test_deployment_snapshot_and_authentication(self) -> None:
        token = "synthetic-token-" * 3
        record = {
            "credential_id": "test-bridge",
            "caller_id": "test-erp",
            "host_namespace": "test-erp",
            "capabilities": ["fiscal.capabilities.read"],
            "scope_grants": [{"tenant_id": "test-tenant", "unit_id": "test-unit"}],
            "environments": ["homologation"],
            "secret_sha256": hashlib.sha256(token.encode()).hexdigest(),
            "valid_from": "2026-01-01T00:00:00+00:00",
            "expires_at": "2027-01-01T00:00:00+00:00",
            "revoked": False,
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "credentials.json"
            environ = {"NFCORE_BRIDGE_CREDENTIALS_FILE": str(path)}
            self.assertEqual(load_bridge_credentials({}), ())
            with self.assertRaises(RuntimeConfigurationError):
                load_bridge_credentials(environ)

            path.write_text(json.dumps([record]), encoding="utf-8")
            credentials = load_bridge_credentials(environ)
            authenticator = WorkloadAuthenticator(credentials)
            identity = authenticator.authenticate(
                credential_id="test-bridge",
                presented_secret=token,
                now=datetime(2026, 6, 1, tzinfo=UTC),
            ).identity
            self.assertEqual(identity.environments, frozenset({FiscalEnvironment.HOMOLOGATION}))
            with self.assertRaises(WorkloadAuthenticationError):
                authenticator.authenticate(
                    credential_id="test-bridge",
                    presented_secret=token,
                    now=datetime(2027, 1, 1, tzinfo=UTC),
                )

            path.write_text(json.dumps([record, record]), encoding="utf-8")
            with self.assertRaises(RuntimeConfigurationError):
                load_bridge_credentials(environ)
