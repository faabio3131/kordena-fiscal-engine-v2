"""Public portal forwards only the scoped Bling webhook with its signature."""

from __future__ import annotations

import http.client
import importlib.util
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

# CI installs the wheel with src/ on sys.path; load the deployment script
# from its exact repo path without relying on namespace-package import paths.
_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "serve_portal.py"
_SPEC = importlib.util.spec_from_file_location("nfcore_portal_server", _SCRIPT)
if _SPEC is None or _SPEC.loader is None:
    raise RuntimeError("canonical portal server module unavailable")
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
SecurePortalHandler = _MODULE.SecurePortalHandler


class RecordingUpstream(BaseHTTPRequestHandler):
    calls: list[tuple[str, bytes, str | None]] = []

    def do_POST(self) -> None:  # noqa: N802
        size = int(self.headers["Content-Length"])
        self.calls.append((
            self.path,
            self.rfile.read(size),
            self.headers.get("X-Bling-Signature-256"),
        ))
        body = b'{"status":"accepted"}'
        self.send_response(202)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path.startswith("/v1/portal/integrations/bling/oauth/callback?"):
            self.send_response(303)
            self.send_header("Location", "/?bling=connected")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        self.send_response(404)
        self.end_headers()

    def log_message(self, *_args: object) -> None:
        return


def test_webhook_proxy_restricts_method_and_installation_path(
    monkeypatch, tmp_path: Path,
) -> None:
    RecordingUpstream.calls = []
    with (
        ThreadingHTTPServer(("127.0.0.1", 0), RecordingUpstream) as upstream,
        ThreadingHTTPServer(
            ("127.0.0.1", 0),
            partial(SecurePortalHandler, directory=str(tmp_path)),
        ) as portal,
    ):
        monkeypatch.setenv(
            "NFCORE_PORTAL_API_UPSTREAM",
            f"http://127.0.0.1:{upstream.server_port}",
        )
        threads = [
            Thread(target=upstream.serve_forever, daemon=True),
            Thread(target=portal.serve_forever, daemon=True),
        ]
        for thread in threads:
            thread.start()
        try:
            def request(method: str, path: str) -> tuple[int, bytes, str | None, str | None]:
                client = http.client.HTTPConnection(
                    "127.0.0.1", portal.server_port, timeout=3,
                )
                try:
                    client.request(
                        method, path, body=b'{"eventId":"synthetic"}',
                        headers={
                            "Content-Type": "application/json",
                            "X-Bling-Signature-256": "sha256=" + "a" * 64,
                        },
                    )
                    response = client.getresponse()
                    return (
                        response.status, response.read(),
                        response.getheader("Location"),
                        response.getheader("Referrer-Policy"),
                    )
                finally:
                    client.close()

            exact = "/webhooks/bling/installations/" + "a" * 32
            assert request("POST", exact)[0] == 202
            assert RecordingUpstream.calls == [
                (exact, b'{"eventId":"synthetic"}', "sha256=" + "a" * 64),
            ]
            for method, path in [
                ("PUT", exact),
                ("GET", exact),
                ("POST", "/webhooks/bling/installations/short"),
                ("POST", exact + "/more"),
                ("POST", "/webhooks/other/installations/" + "a" * 32),
            ]:
                assert request(method, path)[0] == 404
            assert len(RecordingUpstream.calls) == 1
            oauth = request(
                "GET", "/v1/portal/integrations/bling/oauth/callback"
                "?state=synthetic&code=synthetic",
            )
            assert oauth[0] == 303
            assert oauth[2] == "/?bling=connected"
            assert oauth[3] == "no-referrer"
            assert len(RecordingUpstream.calls) == 1
        finally:
            for server in (portal, upstream):
                server.shutdown()
            for thread in threads:
                thread.join(timeout=3)
