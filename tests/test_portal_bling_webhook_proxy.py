"""Public portal forwards only the scoped Bling webhook with its signature."""

from __future__ import annotations

import http.client
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

from scripts.serve_portal import SecurePortalHandler


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
            def request(method: str, path: str) -> tuple[int, bytes]:
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
                    return response.status, response.read()
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
        finally:
            for server in (portal, upstream):
                server.shutdown()
            for thread in threads:
                thread.join(timeout=3)
