from __future__ import annotations

import runpy
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.request import urlopen


def _secure_portal_handler():
    script = Path(__file__).resolve().parents[2] / "scripts" / "serve_portal.py"
    namespace = runpy.run_path(str(script))
    return namespace["SecurePortalHandler"]


def test_portal_server_emits_browser_security_headers(tmp_path) -> None:
    (tmp_path / "index.html").write_text(
        "<!doctype html><title>NFCORE</title>", encoding="utf-8"
    )
    handler = partial(_secure_portal_handler(), directory=str(tmp_path))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        host, port = server.server_address
        with urlopen(f"http://{host}:{port}/", timeout=2) as response:  # noqa: S310
            assert response.status == 200
            assert response.headers["X-Content-Type-Options"] == "nosniff"
            assert response.headers["X-Frame-Options"] == "DENY"
            assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
            assert "connect-src 'self'" in response.headers["Content-Security-Policy"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
